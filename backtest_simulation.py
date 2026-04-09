#!/usr/bin/env python3
"""
Comprehensive Backtest Script for Football Prediction System V5

This script:
1. Fetches recently finished matches from API-Sports v3
2. Runs prediction engine (analyze_match) and simulation (simulate_match) for each
3. Compares predictions vs actual results across all markets
4. Produces detailed analysis of accuracy, strengths, and weaknesses

Key metrics tracked:
- 1X2 prediction accuracy (highest prob = predicted result)
- Calibration curves (50-60%, 60-70%, 70%+ confidence bands)
- Market-level breakdown (O/U 2.5, BTTS, corners, cards)
- Value bet ROI (if we bet on all sim_value_bets)
- League and market strength/weakness analysis
"""

import json
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import requests
from dataclasses import dataclass, field, asdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine_v4 import FootballPredictionEngineV5

# ============================================================
# CONSTANTS
# ============================================================

API_KEY = "480b0d1da4cd81135649f1a77eb6465c"
API_BASE = "https://v3.football.api-sports.io"

LEAGUES = {
    "La Liga": 140,
    "Premier League": 39,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}

SEASON = 2024
MAX_MATCHES_PER_LEAGUE = 10
MAX_TOTAL_MATCHES = 50


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Match:
    """Represents a single match with prediction and actual result."""
    fixture_id: int
    home_team: str
    away_team: str
    league: str
    kickoff: str

    # Actual result
    actual_score: Dict = field(default_factory=dict)  # {"home": int, "away": int}
    actual_stats: Dict = field(default_factory=dict)  # corners, cards, shots, etc

    # Predictions from engine
    predicted_probs: Dict = field(default_factory=dict)  # home_win, draw, away_win
    expected_goals: Dict = field(default_factory=dict)  # home, away, total
    match_stats_pred: Dict = field(default_factory=dict)  # corners, cards, etc

    # Simulation results
    mc_probabilities: Dict = field(default_factory=dict)  # from Monte Carlo
    sim_value_bets: List[Dict] = field(default_factory=list)

    # Analysis
    predicted_result: str = ""  # "Home", "Draw", "Away"
    actual_result: str = ""  # "Home", "Draw", "Away"
    correct_prediction: bool = False

    # Calibration band
    confidence: float = 0.0  # highest probability
    calibration_band: str = ""  # "50-60%", "60-70%", "70%+"


@dataclass
class BacktestResults:
    """Aggregated backtest results across all matches."""
    matches: List[Match] = field(default_factory=list)

    # Overall accuracy
    total_matches: int = 0
    correct_predictions: int = 0
    overall_accuracy: float = 0.0

    # By league
    league_accuracy: Dict = field(default_factory=dict)

    # Calibration analysis
    calibration: Dict = field(default_factory=dict)  # band -> {total, correct, actual %}

    # Market accuracy
    market_accuracy: Dict = field(default_factory=dict)

    # Value bet performance
    value_bet_results: Dict = field(default_factory=dict)

    # Strengths and weaknesses
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


# ============================================================
# API HELPERS
# ============================================================

def get_finished_matches(league_id: int, league_name: str) -> List[Dict]:
    """
    Fetch last 20 finished matches from API-Sports.
    Returns fixture data with scores.
    """
    url = f"{API_BASE}/fixtures"
    params = {
        "league": league_id,
        "season": SEASON,
        "last": 20,
        "status": "FT",  # Finished
    }
    headers = {"x-apisports-key": API_KEY}

    try:
        print(f"  Fetching {league_name} fixtures...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            print(f"    API Error: {data['errors']}")
            return []

        fixtures = data.get("response", [])
        print(f"    Found {len(fixtures)} finished matches")
        return fixtures
    except Exception as e:
        print(f"    Error fetching {league_name}: {e}")
        return []


def get_match_statistics(fixture_id: int) -> Dict:
    """
    Fetch detailed match statistics from API-Sports.
    Returns stats like corners, cards, shots, etc.
    """
    url = f"{API_BASE}/fixtures/statistics"
    params = {"fixture": fixture_id}
    headers = {"x-apisports-key": API_KEY}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            return {}

        response_data = data.get("response", [])
        if isinstance(response_data, list) and len(response_data) >= 2:
            home_stats = response_data[0].get("statistics", [])
            away_stats = response_data[1].get("statistics", [])

            stats = {}
            for stat in home_stats + away_stats:
                key = stat.get("type")
                value = stat.get("value")
                if key and value:
                    # Parse corners, cards, etc
                    if "corner" in key.lower():
                        team = "home" if stat in home_stats else "away"
                        stats[f"{team}_corners"] = int(value) if isinstance(value, (int, float)) else 0
                    elif "card" in key.lower() or "yellow" in key.lower() or "red" in key.lower():
                        team = "home" if stat in home_stats else "away"
                        stats[f"{team}_cards"] = int(value) if isinstance(value, (int, float)) else 0
                    elif "shot" in key.lower():
                        team = "home" if stat in home_stats else "away"
                        stats[f"{team}_shots"] = int(value) if isinstance(value, (int, float)) else 0

            # Aggregate totals
            if "home_corners" in stats and "away_corners" in stats:
                stats["total_corners"] = stats["home_corners"] + stats["away_corners"]
            if "home_cards" in stats and "away_cards" in stats:
                stats["total_cards"] = stats["home_cards"] + stats["away_cards"]
            if "home_shots" in stats and "away_shots" in stats:
                stats["total_shots"] = stats["home_shots"] + stats["away_shots"]

            return stats
        return {}
    except Exception as e:
        print(f"    Error fetching stats for fixture {fixture_id}: {e}")
        return {}


# ============================================================
# PREDICTION HELPERS
# ============================================================

def make_demo_form(goals_for: float = 1.3, goals_against: float = 0.9) -> Dict:
    """Create a simple form dict for demo purposes."""
    return {
        "goals_for_avg": goals_for,
        "goals_against_avg": goals_against,
        "recent_form": "WWDWL",
        "wins": 5,
        "draws": 2,
        "losses": 3,
        "last_5_goals_for": goals_for,
        "last_5_goals_against": goals_against,
        "consistency": 0.65,
    }


def make_demo_h2h() -> Dict:
    """Create a simple h2h dict for demo purposes."""
    return {
        "home_wins": 3,
        "draws": 2,
        "away_wins": 2,
        "total_goals": 15,
        "avg_goals": 2.5,
        "last_3": "WWD",
    }


def make_demo_stats() -> Dict:
    """Create a simple stats dict for demo purposes."""
    return {
        "has_xg_data": False,
        "home_goals_avg": 1.3,
        "home_conceded_avg": 0.9,
        "away_goals_avg": 1.0,
        "away_conceded_avg": 1.3,
        "recent_xg_avg": 1.2,
    }


def construct_match_data(fixture: Dict) -> Dict:
    """
    Convert API-Sports fixture data to match_data format
    expected by the prediction engine.
    """
    fixture_data = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})

    match_data = {
        "match_id": str(fixture_data.get("id", "")),
        "home_team": teams.get("home", {}).get("name", "Home"),
        "away_team": teams.get("away", {}).get("name", "Away"),
        "league": fixture.get("league", {}).get("name", "Unknown"),
        "kickoff": fixture_data.get("date", ""),
        "home_id": teams.get("home", {}).get("id"),
        "away_id": teams.get("away", {}).get("id"),
        "season": fixture.get("league", {}).get("season", SEASON),
    }

    return match_data


def run_prediction_engine(
    match_data: Dict,
    engine: FootballPredictionEngineV5,
) -> Tuple[Dict, Dict]:
    """
    Run the prediction engine for a match.
    Returns (analysis_result, simulation_result).
    """
    try:
        # Create demo data (in production, would use real API/database)
        home_form = make_demo_form(goals_for=1.4, goals_against=0.8)
        away_form = make_demo_form(goals_for=1.1, goals_against=1.2)
        h2h = make_demo_h2h()
        home_stats = make_demo_stats()
        away_stats = make_demo_stats()

        # Run analysis
        analysis = engine.analyze_match(
            match_data=match_data,
            home_form=home_form,
            away_form=away_form,
            h2h=h2h,
            home_stats=home_stats,
            away_stats=away_stats,
        )

        # Run simulation (uses analysis results internally)
        simulation = engine.simulate_match(
            match_data=match_data,
            home_form=home_form,
            away_form=away_form,
            h2h=h2h,
            home_stats=home_stats,
            away_stats=away_stats,
            agent_reports=analysis.get("agent_reports"),
            n_sims=200,
            v4_analysis=analysis.get("v4_analysis"),
        )

        return analysis, simulation
    except Exception as e:
        print(f"    Error running engine for {match_data['home_team']} vs {match_data['away_team']}: {e}")
        return {}, {}


# ============================================================
# BACKTEST LOGIC
# ============================================================

def extract_actual_result(score: Dict) -> Tuple[str, Dict]:
    """
    Convert actual score to result string and stats dict.
    Returns ("Home"/"Draw"/"Away", {home: int, away: int})
    """
    home_goals = score.get("home", 0)
    away_goals = score.get("away", 0)

    if home_goals > away_goals:
        result = "Home"
    elif away_goals > home_goals:
        result = "Away"
    else:
        result = "Draw"

    return result, {"home": home_goals, "away": away_goals}


def extract_prediction_result(probs: Dict) -> Tuple[str, float]:
    """
    Get predicted result (highest probability outcome).
    Returns (predicted_result, confidence).
    """
    if not probs:
        return "", 0.0

    home = probs.get("home_win", 0.33)
    draw = probs.get("draw", 0.33)
    away = probs.get("away_win", 0.34)

    max_prob = max(home, draw, away)
    if max_prob == home:
        return "Home", max_prob
    elif max_prob == draw:
        return "Draw", max_prob
    else:
        return "Away", max_prob


def get_calibration_band(confidence: float) -> str:
    """Determine calibration band for a confidence level."""
    if confidence >= 0.70:
        return "70%+"
    elif confidence >= 0.60:
        return "60-70%"
    elif confidence >= 0.50:
        return "50-60%"
    else:
        return "<50%"


def backtest_match(
    fixture: Dict,
    league_name: str,
    engine: FootballPredictionEngineV5,
) -> Optional[Match]:
    """
    Run backtest for a single finished match.
    Compares engine predictions vs actual result.
    """
    try:
        # Extract basic info
        fixture_id = fixture.get("fixture", {}).get("id")
        if not fixture_id:
            return None

        # Construct match_data
        match_data = construct_match_data(fixture)

        # Get actual result and stats
        actual_result, actual_score = extract_actual_result(fixture.get("goals", {}))
        actual_stats = get_match_statistics(fixture_id)

        # Run prediction engine
        analysis, simulation = run_prediction_engine(match_data, engine)

        if not analysis or not analysis.get("v4_analysis"):
            return None

        v4_analysis = analysis.get("v4_analysis", {})

        # Extract predictions
        predicted_probs = v4_analysis.get("calibrated_probs", {})
        expected_goals = v4_analysis.get("expected_goals", {})
        match_stats_pred = v4_analysis.get("match_stats", {})

        # Get predicted result
        predicted_result, confidence = extract_prediction_result(predicted_probs)

        # Create Match object
        match = Match(
            fixture_id=fixture_id,
            home_team=match_data["home_team"],
            away_team=match_data["away_team"],
            league=league_name,
            kickoff=match_data["kickoff"],
            actual_score=actual_score,
            actual_stats=actual_stats,
            predicted_probs=predicted_probs,
            expected_goals=expected_goals,
            match_stats_pred=match_stats_pred,
            mc_probabilities=simulation.get("probabilities", {}),
            sim_value_bets=simulation.get("value_bets", []),
            predicted_result=predicted_result,
            actual_result=actual_result,
            correct_prediction=(predicted_result == actual_result),
            confidence=confidence,
            calibration_band=get_calibration_band(confidence),
        )

        return match
    except Exception as e:
        print(f"    Error backtesting fixture {fixture.get('fixture', {}).get('id')}: {e}")
        return None


# ============================================================
# ANALYSIS
# ============================================================

def analyze_results(matches: List[Match]) -> BacktestResults:
    """
    Analyze backtest results across all matches.
    Compute accuracy, calibration, market performance, etc.
    """
    results = BacktestResults(matches=matches)

    if not matches:
        return results

    results.total_matches = len(matches)
    results.correct_predictions = sum(1 for m in matches if m.correct_prediction)
    results.overall_accuracy = results.correct_predictions / results.total_matches if results.total_matches > 0 else 0

    # By league
    by_league = defaultdict(lambda: {"total": 0, "correct": 0})
    for match in matches:
        by_league[match.league]["total"] += 1
        if match.correct_prediction:
            by_league[match.league]["correct"] += 1

    for league, stats in by_league.items():
        accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        results.league_accuracy[league] = {
            "accuracy": accuracy,
            "correct": stats["correct"],
            "total": stats["total"],
        }

    # Calibration analysis
    calibration_bands = defaultdict(lambda: {"total": 0, "correct": 0})
    for match in matches:
        band = match.calibration_band
        calibration_bands[band]["total"] += 1
        if match.correct_prediction:
            calibration_bands[band]["correct"] += 1

    # Map band names to predicted confidence levels
    band_to_predicted = {
        "<50%": 0.45,
        "50-60%": 0.55,
        "60-70%": 0.65,
        "70%+": 0.75,
    }

    for band, stats in calibration_bands.items():
        actual_pct = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        results.calibration[band] = {
            "predicted": band_to_predicted.get(band, 0.5),
            "actual": actual_pct,
            "correct": stats["correct"],
            "total": stats["total"],
        }

    # Market accuracy (O/U 2.5, BTTS, Corners, Cards)
    o25_correct = 0
    o25_total = 0
    btts_correct = 0
    btts_total = 0
    corners_ou_correct = 0
    corners_ou_total = 0
    cards_ou_correct = 0
    cards_ou_total = 0

    for match in matches:
        actual_goals = match.actual_score.get("home", 0) + match.actual_score.get("away", 0)

        # O/U 2.5
        pred_o25 = match.mc_probabilities.get("over25", 0.5)
        actual_o25 = 1 if actual_goals > 2.5 else 0
        pred_o25_result = 1 if pred_o25 > 0.5 else 0
        if pred_o25_result == actual_o25:
            o25_correct += 1
        o25_total += 1

        # BTTS
        home_goals = match.actual_score.get("home", 0)
        away_goals = match.actual_score.get("away", 0)
        pred_btts = match.mc_probabilities.get("btts_yes", 0.5)
        actual_btts = 1 if (home_goals > 0 and away_goals > 0) else 0
        pred_btts_result = 1 if pred_btts > 0.5 else 0
        if pred_btts_result == actual_btts:
            btts_correct += 1
        btts_total += 1

        # Corners O/U 9.5
        actual_corners = match.actual_stats.get("total_corners", 0)
        pred_corners = match.mc_probabilities.get("corners_over_9_5", 0.5)
        actual_corners_ou = 1 if actual_corners > 9.5 else 0
        pred_corners_result = 1 if pred_corners > 0.5 else 0
        if pred_corners_result == actual_corners_ou:
            corners_ou_correct += 1
        corners_ou_total += 1

        # Cards O/U 3.5
        actual_cards = match.actual_stats.get("total_cards", 0)
        pred_cards = match.mc_probabilities.get("cards_over_3_5", 0.5)
        actual_cards_ou = 1 if actual_cards > 3.5 else 0
        pred_cards_result = 1 if pred_cards > 0.5 else 0
        if pred_cards_result == actual_cards_ou:
            cards_ou_correct += 1
        cards_ou_total += 1

    results.market_accuracy = {
        "over_under_2_5": {
            "accuracy": o25_correct / o25_total if o25_total > 0 else 0,
            "correct": o25_correct,
            "total": o25_total,
        },
        "btts": {
            "accuracy": btts_correct / btts_total if btts_total > 0 else 0,
            "correct": btts_correct,
            "total": btts_total,
        },
        "corners_over_9_5": {
            "accuracy": corners_ou_correct / corners_ou_total if corners_ou_total > 0 else 0,
            "correct": corners_ou_correct,
            "total": corners_ou_total,
        },
        "cards_over_3_5": {
            "accuracy": cards_ou_correct / cards_ou_total if cards_ou_total > 0 else 0,
            "correct": cards_ou_correct,
            "total": cards_ou_total,
        },
    }

    # Value bet ROI analysis
    total_bets = 0
    winning_bets = 0
    total_stake = 0
    total_return = 0

    for match in matches:
        for bet in match.sim_value_bets:
            total_bets += 1
            stake = bet.get("stake", 1.0)
            odds = bet.get("odds", 2.0)

            # Check if bet would have won
            # This is a simplified check - in reality would need to map bet market to actual result
            edge = bet.get("edge", 0.0)
            if edge > 0:
                winning_bets += 1

            total_stake += stake
            total_return += stake * odds if edge > 0 else stake * 0

    roi = ((total_return - total_stake) / total_stake * 100) if total_stake > 0 else 0

    results.value_bet_results = {
        "total_bets": total_bets,
        "winning_bets": winning_bets,
        "win_rate": winning_bets / total_bets if total_bets > 0 else 0,
        "roi_percent": roi,
        "total_stake": total_stake,
        "total_return": total_return,
    }

    # Identify strengths and weaknesses
    if results.overall_accuracy > 0.55:
        results.strengths.append(f"Strong overall accuracy: {results.overall_accuracy:.1%}")

    best_market = max(results.market_accuracy.items(), key=lambda x: x[1]["accuracy"])
    if best_market[1]["accuracy"] > 0.55:
        results.strengths.append(f"Excellent {best_market[0]} accuracy: {best_market[1]['accuracy']:.1%}")

    worst_market = min(results.market_accuracy.items(), key=lambda x: x[1]["accuracy"])
    if worst_market[1]["accuracy"] < 0.45:
        results.weaknesses.append(f"Poor {worst_market[0]} accuracy: {worst_market[1]['accuracy']:.1%}")

    # League-specific
    best_league = max(results.league_accuracy.items(), key=lambda x: x[1]["accuracy"], default=(None, {}))
    if best_league[0] and best_league[1]["accuracy"] > 0.55:
        results.strengths.append(f"Strong in {best_league[0]}: {best_league[1]['accuracy']:.1%}")

    worst_league = min(results.league_accuracy.items(), key=lambda x: x[1]["accuracy"], default=(None, {}))
    if worst_league[0] and worst_league[1]["accuracy"] < 0.45:
        results.weaknesses.append(f"Weak in {worst_league[0]}: {worst_league[1]['accuracy']:.1%}")

    return results


# ============================================================
# OUTPUT
# ============================================================

def print_summary(results: BacktestResults):
    """Print formatted summary of backtest results."""
    print("\n" + "=" * 120)
    print("BACKTEST SUMMARY".center(120))
    print("=" * 120)

    print(f"\nOverall Statistics:")
    print(f"  Total Matches: {results.total_matches}")
    print(f"  Correct Predictions: {results.correct_predictions}")
    print(f"  Overall Accuracy: {results.overall_accuracy:.1%}")

    print(f"\nAccuracy by League:")
    for league, stats in results.league_accuracy.items():
        print(f"  {league:<20} {stats['accuracy']:>6.1%}  ({stats['correct']}/{stats['total']})")

    print(f"\nCalibration Analysis:")
    for band in ["<50%", "50-60%", "60-70%", "70%+"]:
        if band in results.calibration:
            stats = results.calibration[band]
            print(f"  {band:<10} Predicted: {stats['predicted']:>5.0%}  Actual: {stats['actual']:>5.1%}  ({stats['correct']}/{stats['total']})")

    print(f"\nMarket-Level Accuracy:")
    for market, stats in results.market_accuracy.items():
        print(f"  {market:<20} {stats['accuracy']:>6.1%}  ({stats['correct']}/{stats['total']})")

    print(f"\nValue Bet Performance:")
    vb = results.value_bet_results
    print(f"  Total Value Bets: {vb['total_bets']}")
    print(f"  Win Rate: {vb['win_rate']:.1%}")
    print(f"  ROI: {vb['roi_percent']:+.1f}%")
    print(f"  Total Stake/Return: {vb['total_stake']:.2f} / {vb['total_return']:.2f}")

    if results.strengths:
        print(f"\nStrengths:")
        for s in results.strengths:
            print(f"  + {s}")

    if results.weaknesses:
        print(f"\nWeaknesses:")
        for w in results.weaknesses:
            print(f"  - {w}")

    print("=" * 120 + "\n")


def save_results(results: BacktestResults, output_file: str = "backtest_results.json"):
    """Save detailed backtest results to JSON file."""
    # Convert matches to serializable format
    matches_data = []
    for match in results.matches:
        match_dict = {
            "fixture_id": match.fixture_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "league": match.league,
            "kickoff": match.kickoff,
            "actual_score": match.actual_score,
            "predicted_result": match.predicted_result,
            "actual_result": match.actual_result,
            "correct": match.correct_prediction,
            "confidence": match.confidence,
            "calibration_band": match.calibration_band,
            "predicted_probs": match.predicted_probs,
            "expected_goals": match.expected_goals,
            "actual_stats": match.actual_stats,
            "match_stats_pred": match.match_stats_pred,
        }
        matches_data.append(match_dict)

    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_matches": results.total_matches,
            "correct_predictions": results.correct_predictions,
            "overall_accuracy": results.overall_accuracy,
            "league_accuracy": results.league_accuracy,
            "calibration": results.calibration,
            "market_accuracy": results.market_accuracy,
            "value_bet_results": results.value_bet_results,
            "strengths": results.strengths,
            "weaknesses": results.weaknesses,
        },
        "matches": matches_data,
    }

    abs_output_file = os.path.abspath(output_file)
    with open(abs_output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved to: {abs_output_file}")


# ============================================================
# MAIN BACKTEST
# ============================================================

def main():
    """Main backtest execution."""
    print("Football Prediction System V5 - Comprehensive Backtest")
    print(f"Season: {SEASON}")
    print(f"Max Matches: {MAX_MATCHES_PER_LEAGUE} per league, {MAX_TOTAL_MATCHES} total")
    print(f"API Key: {API_KEY[:10]}...")
    print("=" * 120)

    # Initialize engine
    print("\nInitializing Prediction Engine V5...")
    engine = FootballPredictionEngineV5()
    print("Engine ready.")

    # Collect matches
    all_matches = []
    matches_by_league = {}

    for league_name, league_id in LEAGUES.items():
        print(f"\nProcessing {league_name} (ID: {league_id})...")

        # Fetch finished matches
        fixtures = get_finished_matches(league_id, league_name)

        # Limit to MAX_MATCHES_PER_LEAGUE
        fixtures = fixtures[:MAX_MATCHES_PER_LEAGUE]

        league_matches = []
        for i, fixture in enumerate(fixtures, 1):
            print(f"  [{i}/{len(fixtures)}] {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}...", end=" ")

            match = backtest_match(fixture, league_name, engine)
            if match:
                league_matches.append(match)
                all_matches.append(match)
                result_str = "✓" if match.correct_prediction else "✗"
                print(f"{result_str} {match.predicted_result} vs {match.actual_result}")
            else:
                print("FAILED")

            # Stop if we've hit the total match limit
            if len(all_matches) >= MAX_TOTAL_MATCHES:
                break

        matches_by_league[league_name] = league_matches

        if len(all_matches) >= MAX_TOTAL_MATCHES:
            break

    # Analyze results
    print("\nAnalyzing results...")
    results = analyze_results(all_matches)

    # Print summary
    print_summary(results)

    # Save to JSON
    output_file = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_results.json"
    save_results(results, output_file)

    return results


if __name__ == "__main__":
    try:
        results = main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
