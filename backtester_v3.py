#!/usr/bin/env python3
"""
Backtester V3 — Uses league-specific models from 6,714-match analysis.

Key improvements over V2 backtester:
1. League-specific goal scaling (Bundesliga 13% more goals than global average)
2. Corners from shots (r=+0.33), not goals
3. Cards from fouls + closeness (r=+0.38)
4. Elo blended with Dixon-Coles (60/40)
5. Separate results per league to show where the model has edge

Still uses flat staking (1% of initial bankroll) and no lookahead bias.
"""
import sys
import os
import csv
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.dixon_coles import (
    dixon_coles_match_probs, prob_over_goals, prob_btts,
    strength_adjusted_xg, EloRating
)
from models.league_profiles import (
    get_league_profile, predict_corners, predict_cards,
    LEAGUE_PROFILES, GLOBAL_AVERAGES,
)
from data.multi_source_collector import FootballDataCollector


# ─── Data Loader (same as V2) ────────────────────────────────────────
class RealOddsDataLoader:
    LEAGUES = {
        "Premier League": "E0",
        "La Liga": "SP1",
        "Bundesliga": "D1",
        "Serie A": "I1",
        "Ligue 1": "F1",
    }

    def __init__(self, cache_dir="/tmp/football_data"):
        self.collector = FootballDataCollector(cache_dir)
        self._cache = {}

    def load_season(self, league, season="2526"):
        key = f"{league}_{season}"
        if key in self._cache:
            return self._cache[key]
        matches = self.collector.get_historical_matches(league, season)
        for m in matches:
            try:
                m["datetime"] = datetime.strptime(m["date"], "%d/%m/%Y")
            except:
                m["datetime"] = datetime.now()
        matches.sort(key=lambda m: m["datetime"])
        self._cache[key] = matches
        return matches


# ─── Rolling Stats (V3: includes shots, fouls for corners/cards model) ─
class RollingStatsV3:
    """Rolling stats with shots and fouls for V3 corners/cards models."""

    def __init__(self, window=6, min_matches=3):
        self.window = window
        self.min_matches = min_matches

    def get_stats(self, team, matches_so_far, side="home"):
        """Get rolling stats for a team. side='home' or 'away'."""
        relevant = []
        for m in matches_so_far:
            if side == "home" and m["home"] == team:
                relevant.append({
                    "goals_for": m["home_goals"],
                    "goals_against": m["away_goals"],
                    "shots": m.get("home_shots", 12),
                    "shots_target": m.get("home_shots_target", 5),
                    "corners": m.get("home_corners", 5),
                    "fouls": m.get("home_fouls", 11),
                    "yellows": m.get("home_yellows", 2),
                    "reds": m.get("home_reds", 0),
                })
            elif side == "away" and m["away"] == team:
                relevant.append({
                    "goals_for": m["away_goals"],
                    "goals_against": m["home_goals"],
                    "shots": m.get("away_shots", 10),
                    "shots_target": m.get("away_shots_target", 4),
                    "corners": m.get("away_corners", 4),
                    "fouls": m.get("away_fouls", 12),
                    "yellows": m.get("away_yellows", 2),
                    "reds": m.get("away_reds", 0),
                })

        window = relevant[-self.window:]
        if len(window) < self.min_matches:
            return None

        n = len(window)
        return {
            "goals_avg": sum(r["goals_for"] for r in window) / n,
            "conceded_avg": sum(r["goals_against"] for r in window) / n,
            "shots_avg": sum(r["shots"] for r in window) / n,
            "shots_target_avg": sum(r["shots_target"] for r in window) / n,
            "corners_avg": sum(r["corners"] for r in window) / n,
            "fouls_avg": sum(r["fouls"] for r in window) / n,
            "cards_avg": sum(r["yellows"] + r["reds"] for r in window) / n,
            "matches": len(relevant),
        }


# ─── V3 Predictor (league-adjusted Dixon-Coles + Elo blend) ──────────
class V3Predictor:
    """
    Dixon-Coles + Elo blend with league-specific scaling.

    Key: multiply expected goals by league goals_factor so Bundesliga
    matches predict ~3.18 goals/match while Serie A predicts ~2.55.
    """

    def __init__(self):
        self.elo = EloRating()
        self.elo.initialize_top5_defaults()

    def predict(self, home_stats, away_stats, league="Premier League"):
        profile = get_league_profile(league)

        # Step 1: Elo-adjusted expected goals
        home_exp, away_exp = strength_adjusted_xg(
            home_attack=home_stats["goals_avg"],
            home_defense=home_stats["conceded_avg"],
            away_attack=away_stats["goals_avg"],
            away_defense=away_stats["conceded_avg"],
            elo_system=self.elo,
            home_team=home_stats.get("team", "Unknown"),
            away_team=away_stats.get("team", "Unknown"),
        )

        # Step 2: League-specific scaling
        home_exp *= profile["goals_factor"]
        away_exp *= profile["goals_factor"]

        # Step 3: Dixon-Coles match probs
        dc = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)

        # Step 4: Elo prediction for blend
        elo_pred = self.elo.predict_match(
            home_stats.get("team", "Unknown"),
            away_stats.get("team", "Unknown"),
        )

        # Step 5: Blend DC (60%) + Elo (40%)
        hw = dc["home_win"] * 0.6 + elo_pred["home_win"] * 0.4
        dw = dc["draw"] * 0.6 + elo_pred["draw"] * 0.4
        aw = dc["away_win"] * 0.6 + elo_pred["away_win"] * 0.4
        total = hw + dw + aw
        hw /= total
        dw /= total
        aw /= total

        # Step 6: Over/Under 2.5
        over_25 = prob_over_goals(dc, 2.5)

        # Step 7: Corners prediction (shots-based)
        corners = predict_corners(
            home_stats["shots_avg"], away_stats["shots_avg"], league
        )

        # Step 8: Cards prediction (fouls + closeness)
        # Use DC score probs to estimate match closeness
        score_probs = dc.get("score_probs", {})
        close_prob = sum(p for (i, j), p in score_probs.items() if abs(i - j) <= 1)
        expected_closeness = 1.0 - close_prob  # Inverted for the API

        cards = predict_cards(
            home_stats["fouls_avg"], away_stats["fouls_avg"],
            league=league, expected_closeness=expected_closeness,
        )

        return {
            "home_win": hw,
            "draw": dw,
            "away_win": aw,
            "over_25": over_25,
            "under_25": 1 - over_25,
            "btts": prob_btts(dc),
            "total_corners": corners["total_corners"],
            "total_cards": cards["total_cards"],
            "home_exp": home_exp,
            "away_exp": away_exp,
        }

    def update_elo(self, home, away, hg, ag):
        self.elo.update(home, away, hg, ag)


# ─── Value Detector V3 ──────────────────────────────────────────────
class ValueDetectorV3:
    """Value detection with configurable thresholds per market."""

    def __init__(self, edge_threshold=0.05, min_odds=1.40, max_odds=8.0):
        self.edge_threshold = edge_threshold
        self.min_odds = min_odds
        self.max_odds = max_odds

    def find_value(self, match, predictions, league):
        bets = []

        # 1X2 markets
        markets = [
            ("home_win", f"{match['home']} Win", predictions["home_win"],
             max(match.get("odds_home_pinnacle", 0), match.get("odds_home_bet365", 0), match.get("max_home", 0))),
            ("draw", "Draw", predictions["draw"],
             max(match.get("odds_draw_pinnacle", 0), match.get("odds_draw_bet365", 0), match.get("max_draw", 0))),
            ("away_win", f"{match['away']} Win", predictions["away_win"],
             max(match.get("odds_away_pinnacle", 0), match.get("odds_away_bet365", 0), match.get("max_away", 0))),
        ]

        # O/U 2.5
        o25_odds = match.get("odds_over_25", 0)
        u25_odds = match.get("odds_under_25", 0)
        if o25_odds > 0:
            markets.append(("over_25", "Over 2.5", predictions["over_25"], o25_odds))
        if u25_odds > 0:
            markets.append(("under_25", "Under 2.5", predictions["under_25"], u25_odds))

        for market, outcome, model_prob, odds in markets:
            if not (self.min_odds < odds < self.max_odds):
                continue
            implied = 1.0 / odds
            edge = model_prob - implied
            if edge > self.edge_threshold:
                ev = model_prob * (odds - 1) - (1 - model_prob)
                bets.append({
                    "market": market,
                    "outcome": outcome,
                    "model_prob": model_prob,
                    "odds": odds,
                    "edge": edge,
                    "ev": ev,
                })

        return bets


# ─── Main Backtester V3 ──────────────────────────────────────────────
class BacktesterV3:
    def __init__(self, bankroll=1000.0, stake_pct=0.01, edge_threshold=0.05):
        self.initial_bankroll = bankroll
        self.bankroll = bankroll
        self.stake_pct = stake_pct
        self.flat_stake = bankroll * stake_pct  # Fixed flat stake

        self.loader = RealOddsDataLoader()
        self.stats = RollingStatsV3(window=6, min_matches=3)
        self.predictor = V3Predictor()
        self.value_detector = ValueDetectorV3(edge_threshold=edge_threshold)

        self.results = []
        self.bankroll_history = [bankroll]
        self.league_results = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0.0, "staked": 0.0})

    def run_league(self, league, season="2526", skip_first=10):
        matches = self.loader.load_season(league, season)
        if not matches:
            print(f"  No data for {league}")
            return

        print(f"\n  {league}: {len(matches)} matches loaded")
        bets_placed = 0

        for idx in range(skip_first, len(matches)):
            match = matches[idx]
            prior = matches[:idx]

            home_stats = self.stats.get_stats(match["home"], prior, "home")
            away_stats = self.stats.get_stats(match["away"], prior, "away")

            if home_stats is None or away_stats is None:
                self.predictor.update_elo(match["home"], match["away"],
                                          match["home_goals"], match["away_goals"])
                continue

            home_stats["team"] = match["home"]
            away_stats["team"] = match["away"]

            # V3 prediction with league factors
            pred = self.predictor.predict(home_stats, away_stats, league)

            # Find value
            value_bets = self.value_detector.find_value(match, pred, league)

            for vb in value_bets:
                bets_placed += 1
                stake = self.flat_stake
                actual = self._actual_outcome(match, vb["market"])
                won = (actual == vb["outcome"])
                pnl = stake * (vb["odds"] - 1) if won else -stake

                self.bankroll += pnl
                self.bankroll_history.append(self.bankroll)

                self.results.append({
                    "date": match["date"],
                    "home": match["home"],
                    "away": match["away"],
                    "league": league,
                    "market": vb["market"],
                    "outcome": vb["outcome"],
                    "model_prob": vb["model_prob"],
                    "odds": vb["odds"],
                    "edge": vb["edge"],
                    "won": won,
                    "pnl": pnl,
                    "bankroll": self.bankroll,
                })

                self.league_results[league]["bets"] += 1
                self.league_results[league]["staked"] += stake
                if won:
                    self.league_results[league]["wins"] += 1
                self.league_results[league]["pnl"] += pnl

            self.predictor.update_elo(match["home"], match["away"],
                                      match["home_goals"], match["away_goals"])

        wins = self.league_results[league]["wins"]
        total = self.league_results[league]["bets"]
        pnl = self.league_results[league]["pnl"]
        staked = self.league_results[league]["staked"]
        wr = wins / total * 100 if total else 0
        roi = pnl / staked * 100 if staked else 0

        print(f"    Bets: {total} | Wins: {wins} ({wr:.1f}%) | P&L: €{pnl:.2f} | ROI: {roi:.1f}%")

    def _actual_outcome(self, match, market):
        hg, ag = match["home_goals"], match["away_goals"]
        if market in ("home_win", "draw", "away_win"):
            if hg > ag: return f"{match['home']} Win"
            elif hg == ag: return "Draw"
            else: return f"{match['away']} Win"
        elif market == "over_25":
            return "Over 2.5" if hg + ag > 2.5 else "Under 2.5"
        elif market == "under_25":
            return "Under 2.5" if hg + ag < 2.5 else "Over 2.5"
        return ""

    def run_all(self, season="2526"):
        print("=" * 70)
        print(f"BACKTESTER V3 — League-Specific Dixon-Coles + Elo Blend")
        print(f"Edge threshold: {self.value_detector.edge_threshold*100:.0f}% | "
              f"Flat stake: €{self.flat_stake:.0f} | Bankroll: €{self.initial_bankroll:.0f}")
        print("=" * 70)

        for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
            self.run_league(league, season)

        self._print_summary()
        return self.results

    def _print_summary(self):
        if not self.results:
            print("\nNo bets placed!")
            return

        total_bets = len(self.results)
        total_wins = sum(1 for r in self.results if r["won"])
        total_pnl = sum(r["pnl"] for r in self.results)
        total_staked = total_bets * self.flat_stake

        peak = self.initial_bankroll
        max_dd = 0
        for b in self.bankroll_history:
            if b > peak: peak = b
            dd = peak - b
            if dd > max_dd: max_dd = dd

        print(f"\n{'=' * 70}")
        print(f"OVERALL RESULTS")
        print(f"{'=' * 70}")
        print(f"  Total bets:     {total_bets}")
        print(f"  Win rate:       {total_wins}/{total_bets} = {total_wins/total_bets*100:.1f}%")
        print(f"  Total staked:   €{total_staked:.2f}")
        print(f"  Total P&L:      €{total_pnl:.2f}")
        print(f"  ROI:            {total_pnl/total_staked*100:.1f}%")
        print(f"  Max drawdown:   €{max_dd:.2f} ({max_dd/self.initial_bankroll*100:.1f}%)")
        print(f"  Final bankroll: €{self.bankroll:.2f}")

        print(f"\n  BY LEAGUE:")
        for league, data in sorted(self.league_results.items()):
            if data["bets"] > 0:
                wr = data["wins"] / data["bets"] * 100
                roi = data["pnl"] / data["staked"] * 100 if data["staked"] else 0
                print(f"    {league:20s}: {data['bets']:3d} bets | "
                      f"WR {wr:5.1f}% | P&L €{data['pnl']:+8.2f} | ROI {roi:+6.1f}%")

        # Market breakdown
        market_data = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0.0})
        for r in self.results:
            market_data[r["market"]]["bets"] += 1
            if r["won"]: market_data[r["market"]]["wins"] += 1
            market_data[r["market"]]["pnl"] += r["pnl"]

        print(f"\n  BY MARKET:")
        for market, data in sorted(market_data.items()):
            if data["bets"] > 0:
                wr = data["wins"] / data["bets"] * 100
                staked = data["bets"] * self.flat_stake
                roi = data["pnl"] / staked * 100 if staked else 0
                print(f"    {market:20s}: {data['bets']:3d} bets | "
                      f"WR {wr:5.1f}% | P&L €{data['pnl']:+8.2f} | ROI {roi:+6.1f}%")

        # Calibration
        print(f"\n  CALIBRATION (model prob vs actual win rate):")
        cal_bins = defaultdict(lambda: {"count": 0, "wins": 0})
        for r in self.results:
            bin_key = round(r["model_prob"], 1)
            cal_bins[bin_key]["count"] += 1
            if r["won"]:
                cal_bins[bin_key]["wins"] += 1

        for prob_bin in sorted(cal_bins.keys()):
            data = cal_bins[prob_bin]
            actual = data["wins"] / data["count"] * 100 if data["count"] else 0
            expected = prob_bin * 100
            delta = actual - expected
            bar = "█" * int(abs(delta) / 2) if delta > 0 else "░" * int(abs(delta) / 2)
            print(f"    {expected:5.0f}% predicted → {actual:5.1f}% actual ({data['count']:3d} bets) "
                  f"{'↑' if delta > 0 else '↓'}{abs(delta):.1f}% {bar}")

    def export_csv(self, path):
        """Export all results to CSV."""
        if not self.results:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
            writer.writeheader()
            writer.writerows(self.results)
        print(f"\n  Results exported to {path}")


# ─── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test at multiple edge thresholds
    for threshold in [0.05, 0.10, 0.15]:
        print(f"\n\n{'#' * 70}")
        print(f"# THRESHOLD: {threshold*100:.0f}%")
        print(f"{'#' * 70}")

        bt = BacktesterV3(bankroll=1000, stake_pct=0.01, edge_threshold=threshold)
        bt.run_all(season="2526")

        csv_path = f"/tmp/backtest_v3_{int(threshold*100)}pct.csv"
        bt.export_csv(csv_path)
