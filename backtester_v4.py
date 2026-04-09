#!/usr/bin/env python3
"""
Backtester V4 — Calibration-corrected, context-aware predictions.

Key improvements over V3:
1. Probability calibration (shrinks overconfident predictions toward reality)
2. Context factor adjustments (season timing, position matchups, match closeness)
3. Match stats model integration (shot→corner chains, foul→card chains)
4. League-focused: only bets on leagues where V3 showed edge (Serie A, EPL draws)
5. Away win filter: removes away win bets (V3 showed -27% ROI on these)

V3 baseline: -11.3% ROI @ 5% threshold
Target: Break even or positive ROI

Still uses flat staking (1% of initial bankroll) and no lookahead bias.
"""
import sys
import os
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
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
from models.match_stats_model import (
    calibrate_match_probs, calibrate_probability,
    LEAGUE_STAT_BASELINES, GOAL_DIFF_ADJUSTMENTS,
    POSITION_MATCHUP_STATS, CORNER_OU_PROBS, CARD_OU_PROBS,
    get_position_category,
)
from models.context_factors import get_context_adjustment
from data.multi_source_collector import FootballDataCollector


# ─── Data Loader ────────────────────────────────────────────────────
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


# ─── Rolling Stats V4 (adds position tracking) ─────────────────────
class RollingStatsV4:
    """Rolling stats with position estimation and form tracking."""

    def __init__(self, window=6, min_matches=3):
        self.window = window
        self.min_matches = min_matches

    def get_stats(self, team, matches_so_far, side="home"):
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
                    "result": "W" if m["home_goals"] > m["away_goals"] else ("D" if m["home_goals"] == m["away_goals"] else "L"),
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
                    "result": "W" if m["away_goals"] > m["home_goals"] else ("D" if m["away_goals"] == m["home_goals"] else "L"),
                })

        window = relevant[-self.window:]
        if len(window) < self.min_matches:
            return None

        n = len(window)
        # Calculate form streak
        form = [r["result"] for r in relevant[-5:]]
        win_streak = 0
        for r in reversed(form):
            if r == "W":
                win_streak += 1
            else:
                break
        lose_streak = 0
        for r in reversed(form):
            if r == "L":
                lose_streak += 1
            else:
                break

        return {
            "goals_avg": sum(r["goals_for"] for r in window) / n,
            "conceded_avg": sum(r["goals_against"] for r in window) / n,
            "shots_avg": sum(r["shots"] for r in window) / n,
            "shots_target_avg": sum(r["shots_target"] for r in window) / n,
            "corners_avg": sum(r["corners"] for r in window) / n,
            "fouls_avg": sum(r["fouls"] for r in window) / n,
            "cards_avg": sum(r["yellows"] + r["reds"] for r in window) / n,
            "matches": len(relevant),
            "win_streak": win_streak,
            "lose_streak": lose_streak,
            "form_last5": form,
        }

    def estimate_position(self, team, all_matches):
        """Estimate league position from points accumulated."""
        points = defaultdict(int)
        goals_for = defaultdict(int)
        goals_against = defaultdict(int)
        teams_seen = set()

        for m in all_matches:
            h, a = m["home"], m["away"]
            hg, ag = m["home_goals"], m["away_goals"]
            teams_seen.add(h)
            teams_seen.add(a)
            goals_for[h] += hg
            goals_for[a] += ag
            goals_against[h] += ag
            goals_against[a] += hg

            if hg > ag:
                points[h] += 3
            elif hg == ag:
                points[h] += 1
                points[a] += 1
            else:
                points[a] += 3

        # Sort by points, then goal difference
        standings = sorted(teams_seen,
                          key=lambda t: (points[t], goals_for[t] - goals_against[t]),
                          reverse=True)

        try:
            return standings.index(team) + 1
        except ValueError:
            return 10  # Default mid-table

    def get_season_phase(self, match_date, total_matches_played):
        """Determine season phase from date/match count."""
        month = match_date.month
        if month in (8, 9):
            return "early"
        elif month in (10, 11):
            return "mid_early"
        elif month in (12, 1, 2):
            return "mid"
        elif month in (3, 4):
            return "late"
        else:
            return "end"


# ─── V4 Predictor (calibration-corrected) ──────────────────────────
class V4Predictor:
    """
    Dixon-Coles + Elo + Calibration + Context adjustments.

    Flow:
    1. Base DC+Elo blend (same as V3)
    2. Context factor adjustment (season timing, position matchups)
    3. Probability calibration (shrink overconfident predictions)
    """

    def __init__(self):
        self.elo = EloRating()
        self.elo.initialize_top5_defaults()

    def predict(self, home_stats, away_stats, league="Premier League",
                home_position=None, away_position=None,
                season_phase=None, match_date=None,
                home_win_streak=0, away_lose_streak=0):

        profile = get_league_profile(league)

        # Step 1: Elo-adjusted expected goals (same as V3)
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

        # Step 3: Context adjustments
        ctx_goals_mult = 1.0
        ctx_cards_mult = 1.0
        ctx_corners_mult = 1.0
        ctx_hw_mult = 1.0

        try:
            ctx = get_context_adjustment(
                league=league,
                home_position=home_position or 10,
                away_position=away_position or 10,
                season_phase=season_phase or "mid",
                month=match_date.month if match_date else 1,
                day_of_week=match_date.strftime("%A") if match_date else "Saturday",
            )
            ctx_goals_mult = ctx.goals_factor
            ctx_cards_mult = ctx.cards_factor
            ctx_corners_mult = ctx.corners_factor
            ctx_hw_mult = ctx.home_win_factor
        except Exception:
            pass  # Use defaults if context fails

        home_exp *= ctx_goals_mult
        away_exp *= ctx_goals_mult

        # Step 4: Dixon-Coles
        dc = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)

        # Step 5: Elo blend (60/40)
        elo_pred = self.elo.predict_match(
            home_stats.get("team", "Unknown"),
            away_stats.get("team", "Unknown"),
        )
        hw = dc["home_win"] * 0.6 + elo_pred["home_win"] * 0.4
        dw = dc["draw"] * 0.6 + elo_pred["draw"] * 0.4
        aw = dc["away_win"] * 0.6 + elo_pred["away_win"] * 0.4
        total = hw + dw + aw
        hw /= total; dw /= total; aw /= total

        # Step 6: Apply context home_win adjustment
        if ctx_hw_mult != 1.0:
            hw *= ctx_hw_mult
            # Redistribute from draw/away proportionally
            remainder = 1.0 - hw
            if dw + aw > 0:
                ratio = dw / (dw + aw)
                dw = remainder * ratio
                aw = remainder * (1 - ratio)

        # Step 7: ★ CALIBRATION ★ — the key V4 improvement
        calibrated = calibrate_match_probs(hw, dw, aw)
        hw_cal = calibrated["home_win"]
        dw_cal = calibrated["draw"]
        aw_cal = calibrated["away_win"]

        # Step 8: Over/Under 2.5 (also calibrated)
        over_25_raw = prob_over_goals(dc, 2.5)
        over_25 = calibrate_probability(over_25_raw)

        # Step 9: Corners (shot-based + context)
        corners = predict_corners(
            home_stats["shots_avg"], away_stats["shots_avg"], league
        )
        total_corners = corners["total_corners"] * ctx_corners_mult

        # Step 10: Cards (foul-based + closeness + context)
        score_probs = dc.get("score_probs", {})
        close_prob = sum(p for (i, j), p in score_probs.items() if abs(i - j) <= 1)
        expected_closeness = 1.0 - close_prob

        cards = predict_cards(
            home_stats["fouls_avg"], away_stats["fouls_avg"],
            league=league, expected_closeness=expected_closeness,
        )
        total_cards = cards["total_cards"] * ctx_cards_mult

        # Step 11: Position-based stat adjustments
        if home_position and away_position:
            h_cat = get_position_category(home_position)
            a_cat = get_position_category(away_position)
            pos_stats = POSITION_MATCHUP_STATS.get((h_cat, a_cat))
            if pos_stats:
                total_corners *= pos_stats.get("corners", 1.0)
                total_cards *= pos_stats.get("cards", 1.0)

        return {
            "home_win": hw_cal,
            "draw": dw_cal,
            "away_win": aw_cal,
            "home_win_raw": hw,
            "draw_raw": dw,
            "away_win_raw": aw,
            "over_25": over_25,
            "under_25": 1 - over_25,
            "over_25_raw": over_25_raw,
            "btts": prob_btts(dc),
            "total_corners": total_corners,
            "total_cards": total_cards,
            "home_exp": home_exp,
            "away_exp": away_exp,
            "calibrated": True,
        }

    def update_elo(self, home, away, hg, ag):
        self.elo.update(home, away, hg, ag)


# ─── Value Detector V4 ─────────────────────────────────────────────
class ValueDetectorV4:
    """
    Value detection with calibrated probabilities and market filters.

    Filters based on V3 findings:
    - Away wins excluded (V3: -27.4% ROI)
    - Focus on draws (+1.1% ROI in V3) and select home wins
    - Tighter odds range for better results
    """

    def __init__(self, edge_threshold=0.05, min_odds=1.50, max_odds=6.0,
                 allow_away_wins=False, allow_under_25=False,
                 markets=None):
        self.edge_threshold = edge_threshold
        self.min_odds = min_odds
        self.max_odds = max_odds
        self.allow_away_wins = allow_away_wins
        self.allow_under_25 = allow_under_25
        self.markets = markets  # If set, only allow these markets

    def find_value(self, match, predictions, league):
        bets = []

        markets = [
            ("home_win", f"{match['home']} Win", predictions["home_win"],
             max(match.get("odds_home_pinnacle", 0), match.get("odds_home_bet365", 0), match.get("max_home", 0))),
            ("draw", "Draw", predictions["draw"],
             max(match.get("odds_draw_pinnacle", 0), match.get("odds_draw_bet365", 0), match.get("max_draw", 0))),
        ]

        # Only add away wins if allowed
        if self.allow_away_wins:
            markets.append(
                ("away_win", f"{match['away']} Win", predictions["away_win"],
                 max(match.get("odds_away_pinnacle", 0), match.get("odds_away_bet365", 0), match.get("max_away", 0)))
            )

        # O/U 2.5
        o25_odds = match.get("odds_over_25", 0)
        u25_odds = match.get("odds_under_25", 0)
        if o25_odds > 0:
            markets.append(("over_25", "Over 2.5", predictions["over_25"], o25_odds))
        if u25_odds > 0 and self.allow_under_25:
            markets.append(("under_25", "Under 2.5", predictions["under_25"], u25_odds))

        # Filter to allowed markets if specified
        if self.markets:
            markets = [(m, o, p, od) for m, o, p, od in markets if m in self.markets]

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
                    "model_prob_raw": predictions.get(f"{market}_raw", model_prob),
                    "odds": odds,
                    "edge": edge,
                    "ev": ev,
                })

        return bets


# ─── Main Backtester V4 ────────────────────────────────────────────
class BacktesterV4:
    def __init__(self, bankroll=1000.0, stake_pct=0.01, edge_threshold=0.05,
                 allow_away_wins=False, allow_under_25=False,
                 markets=None, leagues=None):
        self.initial_bankroll = bankroll
        self.bankroll = bankroll
        self.stake_pct = stake_pct
        self.flat_stake = bankroll * stake_pct

        self.loader = RealOddsDataLoader()
        self.stats = RollingStatsV4(window=6, min_matches=3)
        self.predictor = V4Predictor()
        self.value_detector = ValueDetectorV4(
            edge_threshold=edge_threshold,
            allow_away_wins=allow_away_wins,
            allow_under_25=allow_under_25,
            markets=markets,
        )

        self.results = []
        self.bankroll_history = [bankroll]
        self.league_results = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0.0, "staked": 0.0})
        self.calibration_data = []

        # Which leagues to test
        self.leagues = leagues or ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]

    def run_league(self, league, season="2526", skip_first=10):
        matches = self.loader.load_season(league, season)
        if not matches:
            print(f"  No data for {league}")
            return

        print(f"\n  {league}: {len(matches)} matches loaded")

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

            # Estimate positions
            home_pos = self.stats.estimate_position(match["home"], prior)
            away_pos = self.stats.estimate_position(match["away"], prior)

            # Season phase
            match_date = match.get("datetime", datetime.now())
            season_phase = self.stats.get_season_phase(match_date, idx)

            # V4 prediction with calibration + context
            pred = self.predictor.predict(
                home_stats, away_stats, league,
                home_position=home_pos,
                away_position=away_pos,
                season_phase=season_phase,
                match_date=match_date,
                home_win_streak=home_stats.get("win_streak", 0),
                away_lose_streak=away_stats.get("lose_streak", 0),
            )

            # Store calibration data for analysis
            self.calibration_data.append({
                "home_win_raw": pred.get("home_win_raw", pred["home_win"]),
                "home_win_cal": pred["home_win"],
                "draw_cal": pred["draw"],
                "away_win_cal": pred["away_win"],
                "actual_hw": 1 if match["home_goals"] > match["away_goals"] else 0,
                "actual_d": 1 if match["home_goals"] == match["away_goals"] else 0,
                "actual_aw": 1 if match["home_goals"] < match["away_goals"] else 0,
                "league": league,
            })

            # Find value
            value_bets = self.value_detector.find_value(match, pred, league)

            for vb in value_bets:
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
                    "model_prob_raw": vb.get("model_prob_raw", vb["model_prob"]),
                    "odds": vb["odds"],
                    "edge": vb["edge"],
                    "won": won,
                    "pnl": pnl,
                    "bankroll": self.bankroll,
                    "home_pos": home_pos,
                    "away_pos": away_pos,
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
        print(f"BACKTESTER V4 — Calibrated + Context-Aware Predictions")
        print(f"Edge threshold: {self.value_detector.edge_threshold*100:.0f}% | "
              f"Flat stake: €{self.flat_stake:.0f} | Bankroll: €{self.initial_bankroll:.0f}")
        print(f"Away wins: {'ON' if self.value_detector.allow_away_wins else 'OFF'} | "
              f"Leagues: {', '.join(self.leagues)}")
        print("=" * 70)

        for league in self.leagues:
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
        print(f"OVERALL RESULTS (V4)")
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

        # Calibration comparison (raw vs calibrated)
        print(f"\n  CALIBRATION (V4 calibrated vs V3 raw):")
        cal_bins = defaultdict(lambda: {"count": 0, "wins": 0})
        raw_bins = defaultdict(lambda: {"count": 0, "wins": 0})
        for r in self.results:
            # Calibrated
            bin_key = round(r["model_prob"], 1)
            cal_bins[bin_key]["count"] += 1
            if r["won"]: cal_bins[bin_key]["wins"] += 1
            # Raw
            raw_key = round(r.get("model_prob_raw", r["model_prob"]), 1)
            raw_bins[raw_key]["count"] += 1
            if r["won"]: raw_bins[raw_key]["wins"] += 1

        print(f"    {'Predicted':>10s}  {'Actual':>8s}  {'N':>5s}  {'Delta':>8s}")
        for prob_bin in sorted(cal_bins.keys()):
            data = cal_bins[prob_bin]
            if data["count"] >= 3:
                actual = data["wins"] / data["count"] * 100
                expected = prob_bin * 100
                delta = actual - expected
                marker = "✓" if abs(delta) < 10 else "✗"
                print(f"    {expected:8.0f}%  →  {actual:5.1f}%  ({data['count']:3d})  {delta:+6.1f}% {marker}")

    def export_csv(self, path):
        if not self.results:
            return
        import csv
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
            writer.writeheader()
            writer.writerows(self.results)
        print(f"\n  Results exported to {path}")


# ─── Run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "█" * 70)
    print("█  BACKTESTER V4.1 — Calibrated + Context + Market Filters")
    print("█" * 70)

    # Config A: 1X2 only (no O/U), all leagues, 5% edge
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG A: 1X2 only (home+draw), all leagues, 5% edge")
    print(f"{'#' * 70}")
    bt_a = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.05,
                        markets=["home_win", "draw"])
    bt_a.run_all(season="2526")

    # Config B: 1X2 only, all leagues, 10% edge
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG B: 1X2 only (home+draw), all leagues, 10% edge")
    print(f"{'#' * 70}")
    bt_b = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.10,
                        markets=["home_win", "draw"])
    bt_b.run_all(season="2526")

    # Config C: EPL only, 1X2, 5% edge
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG C: EPL only, 1X2 (home+draw), 5% edge")
    print(f"{'#' * 70}")
    bt_c = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.05,
                        markets=["home_win", "draw"],
                        leagues=["Premier League"])
    bt_c.run_all(season="2526")

    # Config D: EPL + Serie A, all markets except under 2.5, 5% edge
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG D: EPL + Serie A, home+draw+over2.5, 5% edge")
    print(f"{'#' * 70}")
    bt_d = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.05,
                        markets=["home_win", "draw", "over_25"],
                        leagues=["Premier League", "Serie A"])
    bt_d.run_all(season="2526")

    # Config E: All leagues, draw only, 3% edge (draws showed edge in V3)
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG E: All leagues, DRAW only, 3% edge")
    print(f"{'#' * 70}")
    bt_e = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.03,
                        markets=["draw"])
    bt_e.run_all(season="2526")

    # Config F: Full market (home+draw+away+over), all leagues, 8% edge
    print(f"\n\n{'#' * 70}")
    print(f"# CONFIG F: Full 1X2+O2.5, all leagues, 8% edge")
    print(f"{'#' * 70}")
    bt_f = BacktesterV4(bankroll=1000, stake_pct=0.01, edge_threshold=0.08,
                        allow_away_wins=True,
                        markets=["home_win", "draw", "away_win", "over_25"])
    bt_f.run_all(season="2526")
