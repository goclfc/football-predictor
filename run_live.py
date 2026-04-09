#!/usr/bin/env python3
"""
Live runner — fetches REAL data from The Odds API + API-Football
and generates the dashboard with live odds and stats.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.live_collector import LiveOddsCollector, LiveStatsCollector
from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent import StatsAgent
from agents.market_agent import MarketAgent
from agents.value_agent import ValueAgent
from agents.meta_agent import MetaAgent
from dashboard import generate_dashboard


def main():
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "a0497245bde02bf5159229dddea27af4")
    STATS_API_KEY = os.environ.get("STATS_API_KEY", "480b0d1da4cd81135649f1a77eb6465c")

    print("=" * 70)
    print("  FOOTBALL BETTING INTELLIGENCE — LIVE MODE")
    print("  Real odds from The Odds API + Real stats from API-Football")
    print("=" * 70)

    # Init collectors
    odds_collector = LiveOddsCollector(ODDS_API_KEY)
    stats_collector = LiveStatsCollector(STATS_API_KEY)

    # Init agents
    agents = [FormAgent(), HistoricalAgent(), StatsAgent(), MarketAgent(), ValueAgent()]
    meta_agent = MetaAgent()

    # Step 1: Fetch all upcoming matches with odds
    print("\n[1/4] Fetching live odds from bookmakers...")
    all_matches = odds_collector.get_all_upcoming_matches(max_leagues=15)
    print(f"\n  Total: {len(all_matches)} matches with live odds")

    if not all_matches:
        print("  No matches found! Check API key or try later.")
        return

    # Limit to reasonable number for API-Football rate limits (100 req/day on free plan)
    # Each match needs ~4 API calls (2 team forms + 1 H2H + maybe team stats)
    # So let's process the matches with most betting markets first
    all_matches.sort(key=lambda m: len(m.get("markets", {})), reverse=True)
    max_matches = min(len(all_matches), 20)  # Process top 20 matches
    matches_to_process = all_matches[:max_matches]

    print(f"  Processing top {max_matches} matches (by market depth)")

    all_results = []
    api_calls = 0
    MAX_STATS_CALLS = 80  # Leave buffer for free API

    for i, match in enumerate(matches_to_process):
        home = match["home_team"]
        away = match["away_team"]
        league = match["league"]
        match_time = match["commence_time"]

        print(f"\n[2/4] [{i+1}/{max_matches}] {home} vs {away} ({league}) @ {match_time[:16]}")
        print(f"  Markets available: {len(match['markets'])}")

        # Fetch stats (with rate limiting)
        if api_calls < MAX_STATS_CALLS:
            print(f"  Fetching team stats...")
            home_form = stats_collector.get_team_form(home)
            api_calls += 2  # team search + fixtures
            time.sleep(0.5)

            away_form = stats_collector.get_team_form(away)
            api_calls += 2
            time.sleep(0.5)

            h2h = stats_collector.get_head_to_head(home, away)
            api_calls += 1
            time.sleep(0.5)

            home_stats = stats_collector.get_team_stats(home)
            away_stats = stats_collector.get_team_stats(away)
            # These derive from form data mostly, so fewer API calls
        else:
            print(f"  Using cached/default stats (API limit protection)")
            home_form = stats_collector._empty_form(home)
            away_form = stats_collector._empty_form(away)
            h2h = stats_collector._empty_h2h(home, away)
            home_stats = stats_collector._empty_stats(home)
            away_stats = stats_collector._empty_stats(away)

        # Run agents
        print(f"  Running {len(agents)} agents...")
        agent_reports = []
        for agent in agents:
            try:
                report = agent.analyze(match, home_form, away_form, h2h, home_stats, away_stats)
                agent_reports.append(report)
            except Exception as e:
                print(f"    {agent.name} error: {e}")

        # Meta synthesis
        final_bets = meta_agent.synthesize(match, agent_reports)
        print(f"  -> {len(final_bets)} value bets found!")

        all_results.append({
            "match": match,
            "home_form": home_form,
            "away_form": away_form,
            "h2h": h2h,
            "agent_reports": agent_reports,
            "final_bets": final_bets,
        })

    # Flatten and rank all bets
    all_bets = []
    for result in all_results:
        all_bets.extend(result["final_bets"])
    all_bets.sort(key=lambda b: b.confidence_pct * b.expected_value, reverse=True)

    # Generate dashboard
    results = {
        "matches": all_results,
        "all_bets": all_bets,
        "summary": {
            "total_matches": len(matches_to_process),
            "total_value_bets": len(all_bets),
            "low_risk": len([b for b in all_bets if b.risk_level == "LOW"]),
            "medium_risk": len([b for b in all_bets if b.risk_level == "MEDIUM"]),
            "high_risk": len([b for b in all_bets if b.risk_level == "HIGH"]),
        }
    }

    output_path = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_intelligence_live.html"
    generate_dashboard(results, output_path)

    # Print results
    print(f"\n{'='*110}")
    print(f"  TOP 30 LIVE VALUE BETS — Real Odds from Real Bookmakers")
    print(f"{'='*110}")
    print(f"{'#':>3} {'Date':<18} {'Match':<32} {'Market':<22} {'Bet':<18} {'Odds':>6} {'Conf':>6} {'EV':>7} {'Risk':>7} {'Book':<15}")
    print(f"{'-'*110}")

    for i, bet in enumerate(all_bets[:30], 1):
        match_str = f"{bet.home_team} vs {bet.away_team}"[:30]
        market_str = bet.market_display[:20]
        outcome_str = bet.outcome[:16]
        date_str = bet.match_date[:16] if bet.match_date else "TBD"
        print(
            f"{i:>3} {date_str:<18} {match_str:<32} {market_str:<22} {outcome_str:<18} "
            f"{bet.best_odds:>6.2f} {bet.confidence_pct:>5.1f}% "
            f"{bet.expected_value:>+6.1f}% {bet.risk_level:>7} {bet.best_bookmaker:<15}"
        )

    summary = results["summary"]
    print(f"\n{'='*110}")
    print(f"  LIVE SUMMARY: {summary['total_value_bets']} value bets from {summary['total_matches']} real matches")
    print(f"  Risk: {summary['low_risk']} LOW | {summary['medium_risk']} MEDIUM | {summary['high_risk']} HIGH")
    print(f"  Dashboard: {output_path}")
    print(f"{'='*110}")

    return results


if __name__ == "__main__":
    main()
