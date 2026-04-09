#!/usr/bin/env python3
"""
Real Historical Backtester — Tests model edge against REAL historical odds.

Strategy:
1. Load match data from football-data.co.uk CSVs (contains real closing odds)
2. For each historical match, reconstruct pre-match state WITHOUT lookahead bias
3. Calculate rolling stats from all PREVIOUS matches only
4. Feed rolling stats to Dixon-Coles model to get predicted probabilities
5. Compare model prob vs implied prob from real closing odds
6. Only "bet" when model has edge > threshold (e.g., 3%)
7. Track results with flat staking (% of bankroll)
8. Generate HTML dashboard with calibration charts + metrics

This answers: "Does our model actually have an edge against real bookmaker odds?"
"""
import sys
import os
import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.dixon_coles import (
    dixon_coles_match_probs, prob_over_goals, prob_btts,
    strength_adjusted_xg, EloRating
)
from data.multi_source_collector import FootballDataCollector


# ─── Result Tracking ──────────────────────────────────────────────────
@dataclass
class BetResult:
    """Tracks a single bet and its outcome."""
    match_id: str
    match_date: str
    home_team: str
    away_team: str
    league: str
    market: str
    outcome: str
    model_prob: float
    odds: float
    bookmaker: str
    stake_amount: float
    confidence: float
    edge_pct: float
    # Actual result
    won: bool = False
    actual_outcome: str = ""
    pnl: float = 0.0  # Profit/loss from this bet
    running_bankroll: float = 0.0


@dataclass
class BacktestSummary:
    """Overall backtest results."""
    total_matches: int = 0
    total_bets_placed: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_staked: float = 0.0
    total_pnl: float = 0.0
    roi: float = 0.0
    roi_percent: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_bankroll: float = 0.0
    final_bankroll: float = 0.0
    starting_bankroll: float = 0.0
    # By market
    market_breakdown: Dict = field(default_factory=dict)
    # By league
    league_breakdown: Dict = field(default_factory=dict)
    # Calibration bins
    calibration_bins: Dict = field(default_factory=dict)


# ─── Data Loader ──────────────────────────────────────────────────────
class RealOddsDataLoader:
    """Loads historical match data with real closing odds from football-data.co.uk."""

    LEAGUES = {
        "Premier League": "E0",
        "La Liga": "SP1",
        "Bundesliga": "D1",
        "Serie A": "I1",
        "Ligue 1": "F1",
    }

    def __init__(self, cache_dir: str = "/tmp/football_data"):
        self.collector = FootballDataCollector(cache_dir)
        self._matches_cache = {}

    def load_season(self, league: str, season: str = "2526") -> List[Dict]:
        """Load all matches for a league/season from CSV."""
        cache_key = f"{league}_{season}"
        if cache_key in self._matches_cache:
            return self._matches_cache[cache_key]

        matches = self.collector.get_historical_matches(league, season)

        # Parse dates and sort chronologically
        for m in matches:
            try:
                m["datetime"] = datetime.strptime(m["date"], "%d/%m/%Y")
            except:
                m["datetime"] = datetime.now()

        matches.sort(key=lambda m: m["datetime"])
        self._matches_cache[cache_key] = matches
        return matches

    def load_all_leagues(self, season: str = "2526") -> Dict[str, List[Dict]]:
        """Load all top 5 leagues for a season."""
        all_matches = {}
        for league in self.LEAGUES.keys():
            print(f"Loading {league}...")
            matches = self.load_season(league, season)
            all_matches[league] = matches
            print(f"  {len(matches)} matches loaded")
        return all_matches


# ─── Rolling Stats Calculator ──────────────────────────────────────────
class RollingStatsCalculator:
    """
    Calculates rolling team stats WITHOUT lookahead bias.
    For each match, only uses data from ALL PREVIOUS matches.
    """

    def __init__(self, window_size: int = 5, min_matches: int = 3):
        self.window_size = window_size
        self.min_matches = min_matches
        self.stats_db = defaultdict(lambda: {
            "home_matches": [],
            "away_matches": [],
        })

    def get_team_stats(self, team: str, matches_so_far: List[Dict]) -> Dict:
        """
        Calculate rolling stats for a team based on matches played so far.
        Args:
            team: Team name
            matches_so_far: All matches up to (but NOT including) current match
        """
        home_matches = []
        away_matches = []

        for m in matches_so_far:
            if m["home"] == team:
                home_matches.append(m)
            elif m["away"] == team:
                away_matches.append(m)

        # Use only last N matches (rolling window)
        home_window = home_matches[-self.window_size:]
        away_window = away_matches[-self.window_size:]

        # Ensure enough data
        if len(home_window) < self.min_matches or len(away_window) < self.min_matches:
            return self._empty_stats(team)

        # Calculate averages for home matches
        home_goals_avg = sum(m["home_goals"] for m in home_window) / len(home_window)
        home_conceded_avg = sum(m["away_goals"] for m in home_window) / len(home_window)
        home_corners_avg = sum(m["home_corners"] for m in home_window) / len(home_window)
        home_cards_avg = sum(m["home_yellows"] + m["home_reds"] for m in home_window) / len(home_window)
        home_shots_avg = sum(m["home_shots_target"] for m in home_window) / len(home_window)

        # Calculate averages for away matches
        away_goals_avg = sum(m["away_goals"] for m in away_window) / len(away_window)
        away_conceded_avg = sum(m["home_goals"] for m in away_window) / len(away_window)
        away_corners_avg = sum(m["away_corners"] for m in away_window) / len(away_window)
        away_cards_avg = sum(m["home_yellows"] + m["home_reds"] for m in away_window) / len(away_window)
        away_shots_avg = sum(m["away_shots_target"] for m in away_window) / len(away_window)

        return {
            "team": team,
            "matches_home": len(home_matches),
            "matches_away": len(away_matches),
            "home_goals_avg": home_goals_avg,
            "home_conceded_avg": home_conceded_avg,
            "away_goals_avg": away_goals_avg,
            "away_conceded_avg": away_conceded_avg,
            "home_corners_avg": home_corners_avg,
            "away_corners_avg": away_corners_avg,
            "home_cards_avg": home_cards_avg,
            "away_cards_avg": away_cards_avg,
            "home_shots_avg": home_shots_avg,
            "away_shots_avg": away_shots_avg,
            "real_corners_for_avg": home_corners_avg + away_corners_avg,
            "avg_shots_on_target": home_shots_avg + away_shots_avg,
        }

    def _empty_stats(self, team: str) -> Dict:
        """Return neutral stats for teams with insufficient history."""
        return {
            "team": team,
            "matches_home": 0,
            "matches_away": 0,
            "home_goals_avg": 1.4,
            "home_conceded_avg": 1.3,
            "away_goals_avg": 1.1,
            "away_conceded_avg": 1.4,
            "home_corners_avg": 5.0,
            "away_corners_avg": 4.5,
            "home_cards_avg": 2.0,
            "away_cards_avg": 2.1,
            "home_shots_avg": 4.0,
            "away_shots_avg": 3.8,
            "real_corners_for_avg": 9.5,
            "avg_shots_on_target": 7.8,
        }


# ─── Model Predictor ──────────────────────────────────────────────────
class DixonColesPredictor:
    """Uses Dixon-Coles model to predict match probabilities."""

    def __init__(self):
        self.elo = EloRating()
        self.elo.initialize_top5_defaults()

    def predict_match(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """
        Predict match result using Dixon-Coles model.
        Returns dict with probabilities for each outcome.
        """
        home_attack = home_stats["home_goals_avg"]
        home_defense = home_stats["home_conceded_avg"]
        away_attack = away_stats["away_goals_avg"]
        away_defense = away_stats["away_conceded_avg"]

        home_exp, away_exp = strength_adjusted_xg(
            home_attack=home_attack,
            home_defense=home_defense,
            away_attack=away_attack,
            away_defense=away_defense,
            elo_system=self.elo,
            home_team=home_stats.get("team", "Unknown"),
            away_team=away_stats.get("team", "Unknown"),
        )

        # Get match probabilities from Dixon-Coles
        dc_probs = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)

        return {
            "home_win": dc_probs["home_win"],
            "draw": dc_probs["draw"],
            "away_win": dc_probs["away_win"],
            "over_25": prob_over_goals(dc_probs, 2.5),
            "under_25": 1 - prob_over_goals(dc_probs, 2.5),
            "btts": prob_btts(dc_probs),
        }

    def update_elo(self, home_team: str, away_team: str, home_goals: int, away_goals: int):
        """Update Elo ratings after match result."""
        self.elo.update(home_team, away_team, home_goals, away_goals)


# ─── Value Detector ──────────────────────────────────────────────────
class ValueDetector:
    """Identifies betting value in historical odds."""

    def __init__(self, edge_threshold: float = 0.03, min_odds: float = 1.5, max_odds: float = 10.0):
        self.edge_threshold = edge_threshold
        self.min_odds = min_odds
        self.max_odds = max_odds

    def find_value_bets(self, match: Dict, predictions: Dict, league: str,
                       match_index: int) -> List[Tuple[str, str, float, float, float]]:
        """
        Find bets with positive expected value.
        Returns list of (market, outcome, model_prob, odds, edge_pct) tuples.
        """
        bets = []
        match_id = f"{league}_{match_index}_{match['home']}_{match['away']}"

        # Match result (1X2)
        home_prob = predictions["home_win"]
        draw_prob = predictions["draw"]
        away_prob = predictions["away_win"]

        # Use best available odds
        home_odds = max(
            match.get("odds_home_pinnacle", 0),
            match.get("odds_home_bet365", 0),
            match.get("max_home", 0)
        )
        draw_odds = max(
            match.get("odds_draw_pinnacle", 0),
            match.get("odds_draw_bet365", 0),
            match.get("max_draw", 0)
        )
        away_odds = max(
            match.get("odds_away_pinnacle", 0),
            match.get("odds_away_bet365", 0),
            match.get("max_away", 0)
        )

        if home_odds > self.min_odds and home_odds < self.max_odds:
            implied_prob = 1 / home_odds
            edge = home_prob - implied_prob
            if edge > self.edge_threshold:
                bets.append((
                    "match_result",
                    f"{match['home']} Win",
                    home_prob,
                    home_odds,
                    edge,
                ))

        if draw_odds > self.min_odds and draw_odds < self.max_odds:
            implied_prob = 1 / draw_odds
            edge = draw_prob - implied_prob
            if edge > self.edge_threshold:
                bets.append((
                    "match_result",
                    "Draw",
                    draw_prob,
                    draw_odds,
                    edge,
                ))

        if away_odds > self.min_odds and away_odds < self.max_odds:
            implied_prob = 1 / away_odds
            edge = away_prob - implied_prob
            if edge > self.edge_threshold:
                bets.append((
                    "match_result",
                    f"{match['away']} Win",
                    away_prob,
                    away_odds,
                    edge,
                ))

        # Over/Under 2.5 goals
        over_prob = predictions["over_25"]
        under_prob = predictions["under_25"]

        over_odds = max(match.get("odds_over_25", 0), 1.5)
        under_odds = max(match.get("odds_under_25", 0), 1.5)

        if over_odds > self.min_odds and over_odds < self.max_odds:
            implied_prob = 1 / over_odds
            edge = over_prob - implied_prob
            if edge > self.edge_threshold:
                bets.append((
                    "goals_ou_25",
                    "Over 2.5",
                    over_prob,
                    over_odds,
                    edge,
                ))

        if under_odds > self.min_odds and under_odds < self.max_odds:
            implied_prob = 1 / under_odds
            edge = under_prob - implied_prob
            if edge > self.edge_threshold:
                bets.append((
                    "goals_ou_25",
                    "Under 2.5",
                    under_prob,
                    under_odds,
                    edge,
                ))

        return bets

    def determine_bookmaker(self, match: Dict, market: str, outcome: str) -> str:
        """Identify which bookmaker offered the best odds."""
        if market == "match_result":
            if "Win" in outcome:
                team = outcome.split(" ")[0]
                if match.get("odds_home_pinnacle", 0) > match.get("odds_home_bet365", 0):
                    return "Pinnacle"
                else:
                    return "Bet365"
            else:  # Draw
                if match.get("odds_draw_pinnacle", 0) > match.get("odds_draw_bet365", 0):
                    return "Pinnacle"
                else:
                    return "Bet365"
        return "Average"


# ─── Main Backtester ──────────────────────────────────────────────────
class RealOddsBacktester:
    """
    Complete backtester using real historical odds from football-data.co.uk.
    """

    def __init__(self, starting_bankroll: float = 1000.0, stake_pct: float = 0.01,
                 edge_threshold: float = 0.03, rolling_window: int = 5):
        self.starting_bankroll = starting_bankroll
        self.current_bankroll = starting_bankroll
        self.stake_pct = stake_pct
        self.edge_threshold = edge_threshold
        self.rolling_window = rolling_window

        self.loader = RealOddsDataLoader()
        self.stats_calc = RollingStatsCalculator(window_size=rolling_window, min_matches=3)
        self.predictor = DixonColesPredictor()
        self.value_detector = ValueDetector(edge_threshold=edge_threshold)

        self.bet_results: List[BetResult] = []
        self.bankroll_history = [starting_bankroll]
        self.matches_processed = 0
        self.bets_placed = 0

    def backtest_league(self, league: str, season: str = "2526", skip_first_n: int = 10) -> Dict:
        """
        Backtest a single league.
        Args:
            league: League name
            season: Season code (e.g., "2526" for 2025/26)
            skip_first_n: Skip first N matchdays to build rolling stats
        """
        print(f"\n{'='*70}")
        print(f"Backtesting {league}")
        print(f"{'='*70}")

        matches = self.loader.load_season(league, season)
        if not matches:
            print(f"  No matches found for {league}")
            return {}

        print(f"  Total matches: {len(matches)}")
        print(f"  Skipping first {skip_first_n} matches to build rolling stats...")

        matches_this_league = 0
        bets_this_league = 0

        for idx, match in enumerate(matches[skip_first_n:], start=skip_first_n):
            self.matches_processed += 1
            matches_this_league += 1

            home = match["home"]
            away = match["away"]

            # Get rolling stats ONLY from previous matches
            matches_so_far = matches[:idx]
            home_stats = self.stats_calc.get_team_stats(home, matches_so_far)
            away_stats = self.stats_calc.get_team_stats(away, matches_so_far)

            if home_stats["matches_home"] < 3 or away_stats["matches_away"] < 3:
                continue

            # Predict match
            predictions = self.predictor.predict_match(home_stats, away_stats)

            # Find value bets
            value_bets = self.value_detector.find_value_bets(
                match, predictions, league, idx
            )

            if not value_bets:
                # Update Elo for next iteration
                self.predictor.update_elo(home, away, match["home_goals"], match["away_goals"])
                continue

            # Place bets
            for market, outcome, model_prob, odds, edge in value_bets:
                bets_this_league += 1
                self.bets_placed += 1

                stake = self.current_bankroll * self.stake_pct
                bookmaker = self.value_detector.determine_bookmaker(match, market, outcome)

                # Determine if bet won
                actual_outcome = self._get_actual_outcome(match, market, outcome)
                won = (actual_outcome == outcome)

                # Calculate P&L
                if won:
                    pnl = stake * (odds - 1)
                else:
                    pnl = -stake

                self.current_bankroll += pnl
                self.bankroll_history.append(self.current_bankroll)

                # Record bet
                bet = BetResult(
                    match_id=f"{league}_{idx}",
                    match_date=match["date"],
                    home_team=home,
                    away_team=away,
                    league=league,
                    market=market,
                    outcome=outcome,
                    model_prob=model_prob,
                    odds=odds,
                    bookmaker=bookmaker,
                    stake_amount=stake,
                    confidence=0.75,  # Simplified
                    edge_pct=edge * 100,
                    won=won,
                    actual_outcome=actual_outcome,
                    pnl=pnl,
                    running_bankroll=self.current_bankroll,
                )
                self.bet_results.append(bet)

            # Update Elo ratings after match
            self.predictor.update_elo(home, away, match["home_goals"], match["away_goals"])

        print(f"  Matches processed: {matches_this_league}")
        print(f"  Bets placed: {bets_this_league}")
        print(f"  Current bankroll: €{self.current_bankroll:.2f}")

        return {"matches": matches_this_league, "bets": bets_this_league}

    def _get_actual_outcome(self, match: Dict, market: str, outcome: str) -> str:
        """Determine actual outcome based on match result."""
        home_goals = match["home_goals"]
        away_goals = match["away_goals"]
        total_goals = home_goals + away_goals

        if market == "match_result":
            if home_goals > away_goals:
                return f"{match['home']} Win"
            elif home_goals == away_goals:
                return "Draw"
            else:
                return f"{match['away']} Win"
        elif market == "goals_ou_25":
            if total_goals > 2.5:
                return "Over 2.5"
            else:
                return "Under 2.5"

        return ""

    def backtest_all_leagues(self, season: str = "2526") -> None:
        """Run backtest across all 5 major leagues."""
        all_matches = self.loader.load_all_leagues(season)

        for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
            if league in all_matches:
                self.backtest_league(league, season)

        self._generate_summary()

    def _generate_summary(self) -> BacktestSummary:
        """Generate overall summary statistics."""
        if not self.bet_results:
            print("No bets placed!")
            return BacktestSummary()

        wins = sum(1 for b in self.bet_results if b.won)
        losses = len(self.bet_results) - wins
        total_pnl = sum(b.pnl for b in self.bet_results)
        total_staked = sum(b.stake_amount for b in self.bet_results)

        # Drawdown calculation
        peak = self.starting_bankroll
        max_dd = 0
        for bankroll in self.bankroll_history:
            if bankroll > peak:
                peak = bankroll
            dd = peak - bankroll
            if dd > max_dd:
                max_dd = dd

        # Market breakdown
        market_breakdown = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0})
        for bet in self.bet_results:
            market_breakdown[bet.market]["bets"] += 1
            if bet.won:
                market_breakdown[bet.market]["wins"] += 1
            market_breakdown[bet.market]["pnl"] += bet.pnl

        # League breakdown
        league_breakdown = defaultdict(lambda: {"bets": 0, "wins": 0, "pnl": 0})
        for bet in self.bet_results:
            league_breakdown[bet.league]["bets"] += 1
            if bet.won:
                league_breakdown[bet.league]["wins"] += 1
            league_breakdown[bet.league]["pnl"] += bet.pnl

        # Calibration bins (prob bins vs actual win rate)
        calibration_bins = defaultdict(lambda: {"count": 0, "wins": 0})
        for bet in self.bet_results:
            prob_bin = int(bet.model_prob * 10) / 10  # 0.0-0.1, 0.1-0.2, etc
            calibration_bins[prob_bin]["count"] += 1
            if bet.won:
                calibration_bins[prob_bin]["wins"] += 1

        summary = BacktestSummary(
            total_matches=self.matches_processed,
            total_bets_placed=len(self.bet_results),
            wins=wins,
            losses=losses,
            win_rate=wins / len(self.bet_results) if self.bet_results else 0,
            total_staked=total_staked,
            total_pnl=total_pnl,
            roi=total_pnl / self.starting_bankroll if self.starting_bankroll else 0,
            roi_percent=100 * total_pnl / self.starting_bankroll if self.starting_bankroll else 0,
            max_drawdown=max_dd,
            max_drawdown_pct=100 * max_dd / self.starting_bankroll if self.starting_bankroll else 0,
            peak_bankroll=max(self.bankroll_history),
            final_bankroll=self.current_bankroll,
            starting_bankroll=self.starting_bankroll,
            market_breakdown=dict(market_breakdown),
            league_breakdown=dict(league_breakdown),
            calibration_bins=dict(calibration_bins),
        )

        self.summary = summary
        return summary

    def export_results_csv(self, filepath: str = "/tmp/backtest_results.csv") -> None:
        """Export all bet results to CSV."""
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "match_id", "match_date", "home_team", "away_team", "league",
                "market", "outcome", "model_prob", "odds", "bookmaker",
                "stake_amount", "edge_pct", "won", "pnl", "running_bankroll"
            ])
            writer.writeheader()
            for bet in self.bet_results:
                writer.writerow({
                    "match_id": bet.match_id,
                    "match_date": bet.match_date,
                    "home_team": bet.home_team,
                    "away_team": bet.away_team,
                    "league": bet.league,
                    "market": bet.market,
                    "outcome": bet.outcome,
                    "model_prob": f"{bet.model_prob:.4f}",
                    "odds": f"{bet.odds:.2f}",
                    "bookmaker": bet.bookmaker,
                    "stake_amount": f"{bet.stake_amount:.2f}",
                    "edge_pct": f"{bet.edge_pct:.2f}",
                    "won": "Yes" if bet.won else "No",
                    "pnl": f"{bet.pnl:.2f}",
                    "running_bankroll": f"{bet.running_bankroll:.2f}",
                })
        print(f"Results exported to {filepath}")

    def generate_html_dashboard(self, filepath: str = "/tmp/backtest_dashboard.html") -> None:
        """Generate comprehensive HTML dashboard with charts."""
        if not hasattr(self, 'summary'):
            self._generate_summary()

        summary = self.summary

        # Prepare data for charts
        bankroll_json = json.dumps(self.bankroll_history)
        market_labels = json.dumps(list(summary.market_breakdown.keys()))
        market_bets = json.dumps([summary.market_breakdown[m]["bets"] for m in summary.market_breakdown.keys()])
        market_wins = json.dumps([summary.market_breakdown[m]["wins"] for m in summary.market_breakdown.keys()])

        league_labels = json.dumps(list(summary.league_breakdown.keys()))
        league_pnl = json.dumps([summary.league_breakdown[l]["pnl"] for l in summary.league_breakdown.keys()])

        cal_bins = sorted(summary.calibration_bins.keys())
        cal_labels = json.dumps([f"{b:.0%}-{b+0.1:.0%}" for b in cal_bins])
        cal_actual_wr = json.dumps([
            100 * summary.calibration_bins[b]["wins"] / summary.calibration_bins[b]["count"]
            if summary.calibration_bins[b]["count"] > 0 else 0
            for b in cal_bins
        ])
        cal_expected = json.dumps([b * 100 for b in cal_bins])

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Football Prediction Model - Backtest Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.1em; opacity: 0.9; }}
        .content {{ padding: 40px; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .metric h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
            opacity: 0.8;
        }}
        .metric .value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .metric .positive {{ color: #10b981; }}
        .metric .negative {{ color: #ef4444; }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin-bottom: 40px;
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .chart-row-full {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }}
        @media (max-width: 768px) {{
            .chart-row {{ grid-template-columns: 1fr; }}
            .header h1 {{ font-size: 1.8em; }}
            .content {{ padding: 20px; }}
        }}
        .footer {{
            background: #f5f7fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #e0e0e0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Real Odds Backtest Results</h1>
            <p>Dixon-Coles Model Performance vs Real Historical Bookmaker Odds</p>
        </div>

        <div class="content">
            <!-- Summary Metrics -->
            <div class="summary-grid">
                <div class="metric">
                    <h3>Total Bets</h3>
                    <div class="value">{summary.total_bets_placed}</div>
                </div>
                <div class="metric">
                    <h3>Win Rate</h3>
                    <div class="value">{summary.win_rate*100:.1f}%</div>
                </div>
                <div class="metric">
                    <h3>Total P&L</h3>
                    <div class="value {'positive' if summary.total_pnl > 0 else 'negative'}">
                        €{summary.total_pnl:.2f}
                    </div>
                </div>
                <div class="metric">
                    <h3>ROI</h3>
                    <div class="value {'positive' if summary.roi_percent > 0 else 'negative'}">
                        {summary.roi_percent:.1f}%
                    </div>
                </div>
                <div class="metric">
                    <h3>Max Drawdown</h3>
                    <div class="value negative">{summary.max_drawdown_pct:.1f}%</div>
                </div>
                <div class="metric">
                    <h3>Final Bankroll</h3>
                    <div class="value">€{summary.final_bankroll:.2f}</div>
                </div>
            </div>

            <!-- Charts -->
            <div class="chart-row-full">
                <div class="chart-container">
                    <canvas id="bankrollChart"></canvas>
                </div>
            </div>

            <div class="chart-row">
                <div class="chart-container">
                    <canvas id="calibrationChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="leagueChart"></canvas>
                </div>
            </div>

            <div class="chart-row">
                <div class="chart-container">
                    <canvas id="marketBetsChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="marketWinsChart"></canvas>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Season: 2025/26 | Starting Bankroll: €{summary.starting_bankroll:.2f} | Stake: {self.stake_pct*100:.1f}% per bet</p>
        </div>
    </div>

    <script>
        // Bankroll over time
        const bankrollCtx = document.getElementById('bankrollChart').getContext('2d');
        new Chart(bankrollCtx, {{
            type: 'line',
            data: {{
                labels: Array.from({{length: {len(self.bankroll_history)}}}, (_, i) => i),
                datasets: [{{
                    label: 'Bankroll (€)',
                    data: {bankroll_json},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{display: true}},
                    title: {{display: true, text: 'Bankroll Evolution'}}
                }},
                scales: {{
                    y: {{beginAtZero: false}}
                }}
            }}
        }});

        // Calibration chart
        const calCtx = document.getElementById('calibrationChart').getContext('2d');
        new Chart(calCtx, {{
            type: 'scatter',
            data: {{
                datasets: [
                    {{
                        label: 'Model Predicted vs Actual Win Rate',
                        data: {cal_labels}.map((label, i) => ({{
                            x: {cal_expected}[i],
                            y: {cal_actual_wr}[i]
                        }})),
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.5)',
                        borderWidth: 2,
                    }},
                    {{
                        label: 'Perfect Calibration',
                        data: Array.from({{length: 11}}, (_, i) => ({{x: i*10, y: i*10}})),
                        borderColor: '#10b981',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        showLine: true,
                        fill: false,
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{display: true}},
                    title: {{display: true, text: 'Calibration Analysis (Predicted vs Actual Win Rate)'}}
                }},
                scales: {{
                    x: {{min: 0, max: 100, title: {{display: true, text: 'Predicted Probability (%)'}} }},
                    y: {{min: 0, max: 100, title: {{display: true, text: 'Actual Win Rate (%)'}} }}
                }}
            }}
        }});

        // League breakdown
        const leagueCtx = document.getElementById('leagueChart').getContext('2d');
        new Chart(leagueCtx, {{
            type: 'bar',
            data: {{
                labels: {league_labels},
                datasets: [{{
                    label: 'P&L (€)',
                    data: {league_pnl},
                    backgroundColor: function(context) {{
                        return context.parsed.y > 0 ? '#10b981' : '#ef4444';
                    }},
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{display: true, text: 'P&L by League'}}
                }},
                scales: {{
                    y: {{beginAtZero: true}}
                }}
            }}
        }});

        // Market bets
        const marketBetsCtx = document.getElementById('marketBetsChart').getContext('2d');
        new Chart(marketBetsCtx, {{
            type: 'doughnut',
            data: {{
                labels: {market_labels},
                datasets: [{{
                    data: {market_bets},
                    backgroundColor: ['#667eea', '#764ba2', '#f59e0b', '#10b981', '#ef4444'],
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{display: true, text: 'Bets by Market Type'}}
                }}
            }}
        }});

        // Market wins
        const marketWinsCtx = document.getElementById('marketWinsChart').getContext('2d');
        new Chart(marketWinsCtx, {{
            type: 'bar',
            data: {{
                labels: {market_labels},
                datasets: [
                    {{
                        label: 'Wins',
                        data: {market_wins},
                        backgroundColor: '#10b981',
                    }},
                    {{
                        label: 'Total Bets',
                        data: {market_bets},
                        backgroundColor: '#cbd5e1',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{display: true, text: 'Win Rate by Market'}}
                }}
            }}
        }});
    </script>
</body>
</html>
        """

        with open(filepath, "w") as f:
            f.write(html)

        print(f"Dashboard generated: {filepath}")


# ─── Main Entry Point ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("Real Odds Backtester")
    print("=" * 70)

    # Configuration
    STARTING_BANKROLL = 1000.0
    STAKE_PCT = 0.01  # 1% of bankroll per bet
    EDGE_THRESHOLD = 0.03  # 3% edge minimum
    ROLLING_WINDOW = 5  # Use last 5 matches for rolling stats
    SEASON = "2526"  # 2025/26 season

    backtester = RealOddsBacktester(
        starting_bankroll=STARTING_BANKROLL,
        stake_pct=STAKE_PCT,
        edge_threshold=EDGE_THRESHOLD,
        rolling_window=ROLLING_WINDOW,
    )

    print(f"\nStarting Bankroll: €{STARTING_BANKROLL}")
    print(f"Stake per Bet: {STAKE_PCT*100}%")
    print(f"Minimum Edge: {EDGE_THRESHOLD*100}%")
    print(f"Rolling Stats Window: {ROLLING_WINDOW} matches\n")

    # Run backtest across all leagues
    backtester.backtest_all_leagues(SEASON)

    # Summary
    summary = backtester.summary
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Total Matches: {summary.total_matches}")
    print(f"Total Bets Placed: {summary.total_bets_placed}")
    print(f"Wins: {summary.wins} | Losses: {summary.losses}")
    print(f"Win Rate: {summary.win_rate*100:.1f}%")
    print(f"Total P&L: €{summary.total_pnl:.2f}")
    print(f"ROI: {summary.roi_percent:.1f}%")
    print(f"Max Drawdown: €{summary.max_drawdown:.2f} ({summary.max_drawdown_pct:.1f}%)")
    print(f"Final Bankroll: €{summary.final_bankroll:.2f}")
    print(f"{'='*70}\n")

    # Export results
    backtester.export_results_csv("/tmp/backtest_results.csv")
    backtester.generate_html_dashboard("/tmp/backtest_dashboard.html")

    print("Backtest complete!")
    print("Results: /tmp/backtest_results.csv")
    print("Dashboard: /tmp/backtest_dashboard.html")
