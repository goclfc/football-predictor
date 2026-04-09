#!/usr/bin/env python3
"""
Main runner — executes the full pipeline and generates the dashboard.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import FootballPredictionEngine
from dashboard import generate_dashboard


def main():
    # Initialize engine (no API keys = uses realistic simulation)
    engine = FootballPredictionEngine(
        odds_api_key=os.environ.get("ODDS_API_KEY"),
        stats_api_key=os.environ.get("STATS_API_KEY"),
    )

    # Run the full pipeline
    results = engine.run()

    # Generate dashboard
    output_path = os.environ.get("OUTPUT_PATH", "/sessions/intelligent-sleepy-bell/mnt/predictions/football_intelligence.html")
    dashboard_path = generate_dashboard(results, output_path)
    print(f"\nDashboard saved to: {dashboard_path}")

    # Print top bets summary
    all_bets = results["all_bets"]
    print(f"\n{'='*100}")
    print(f"  TOP 25 VALUE BETS — Ranked by Confidence x Expected Value")
    print(f"{'='*100}")
    print(f"{'#':>3} {'Match':<28} {'Market':<24} {'Bet':<18} {'Odds':>6} {'Conf':>6} {'EV':>7} {'Risk':>7} {'Stake':>7} {'Book':<12}")
    print(f"{'-'*100}")

    for i, bet in enumerate(all_bets[:25], 1):
        match_str = f"{bet.home_team} vs {bet.away_team}"[:26]
        market_str = bet.market_display[:22]
        outcome_str = bet.outcome[:16]
        print(
            f"{i:>3} {match_str:<28} {market_str:<24} {outcome_str:<18} "
            f"{bet.best_odds:>6.2f} {bet.confidence_pct:>5.1f}% "
            f"{bet.expected_value:>+6.1f}% {bet.risk_level:>7} "
            f"{bet.recommended_stake:>6.2f}% {bet.best_bookmaker:<12}"
        )

    # Summary
    summary = results["summary"]
    print(f"\n{'='*100}")
    print(f"  SUMMARY: {summary['total_value_bets']} value bets from {summary['total_matches']} matches")
    print(f"  Risk breakdown: {summary['low_risk']} LOW | {summary['medium_risk']} MEDIUM | {summary['high_risk']} HIGH")
    print(f"{'='*100}")

    return results


if __name__ == "__main__":
    main()
