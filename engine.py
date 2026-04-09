"""
Main Engine — Orchestrates the full pipeline:
1. Collect data (odds, stats, form, H2H)
2. Run all agents on each match
3. Meta-agent synthesizes
4. Output ranked value bets
"""
import json
from typing import List, Dict
from data.collector import OddsCollector, StatsCollector
from data.live_collector import LiveOddsCollector, LiveStatsCollector
from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent import StatsAgent
from agents.market_agent import MarketAgent
from agents.value_agent import ValueAgent
from agents.meta_agent import MetaAgent, FinalBet


class FootballPredictionEngine:
    """Main engine that runs the full prediction pipeline."""

    def __init__(self, odds_api_key=None, stats_api_key=None):
        self.odds_api_key = odds_api_key
        self.stats_api_key = stats_api_key

        # Data collectors
        #
        # If keys are provided, we switch to REAL upcoming matches + odds across many leagues
        # (including Champions League) using `data/live_collector.py`.
        if odds_api_key and stats_api_key:
            self.odds_collector = LiveOddsCollector(odds_api_key)
            self.stats_collector = LiveStatsCollector(stats_api_key)
            self.live_mode = True
        else:
            self.odds_collector = OddsCollector(api_key=odds_api_key)
            self.stats_collector = StatsCollector(api_key=stats_api_key)
            self.live_mode = False

        # Agents
        self.agents = [
            FormAgent(),
            HistoricalAgent(),
            StatsAgent(),
            MarketAgent(),
            ValueAgent(),
        ]
        self.meta_agent = MetaAgent()

    def run(self) -> Dict:
        """Run the full pipeline and return all results."""
        print("=" * 60)
        print("  FOOTBALL BETTING INTELLIGENCE ENGINE")
        print("  Multi-Agent Prediction System")
        print("=" * 60)

        # Step 1: Collect upcoming matches with odds
        print("\n[1/4] Fetching upcoming matches and odds...")
        if self.live_mode:
            # Pull across all major leagues (includes Champions League in `data/live_collector.py`)
            matches = self.odds_collector.get_all_upcoming_matches(max_leagues=15)
        else:
            matches = self.odds_collector.get_upcoming_odds()
        print(f"  Found {len(matches)} upcoming matches")

        all_results = []

        for match in matches:
            home = match["home_team"]
            away = match["away_team"]
            print(f"\n[2/4] Analyzing: {home} vs {away} ({match.get('league', 'Unknown')})")

            # Step 2: Collect team data
            print(f"  Fetching form, stats, and H2H data...")
            # NOTE: LiveStatsCollector supports an optional league_id, but our match objects
            # don't always carry API-Football league ids consistently. Keep it generic.
            home_form = self.stats_collector.get_team_form(home)
            away_form = self.stats_collector.get_team_form(away)
            h2h = self.stats_collector.get_head_to_head(home, away)
            home_stats = self.stats_collector.get_team_stats(home)
            away_stats = self.stats_collector.get_team_stats(away)

            # Step 3: Run all agents
            print(f"  Running {len(self.agents)} agents...")
            agent_reports = []
            for agent in self.agents:
                report = agent.analyze(match, home_form, away_form, h2h, home_stats, away_stats)
                agent_reports.append(report)
                pred_count = len(report.predictions)
                print(f"    {agent.name}: {pred_count} predictions (reliability: {report.reliability_score:.0%})")

            # Step 4: Meta-agent synthesis
            print(f"  Meta-agent synthesizing...")
            final_bets = self.meta_agent.synthesize(match, agent_reports)
            print(f"  Found {len(final_bets)} value bets!")

            all_results.append({
                "match": match,
                "home_form": home_form,
                "away_form": away_form,
                "h2h": h2h,
                "agent_reports": agent_reports,
                "final_bets": final_bets,
            })

        # Flatten and rank ALL bets across all matches
        all_bets = []
        for result in all_results:
            all_bets.extend(result["final_bets"])

        all_bets.sort(key=lambda b: b.confidence_pct * b.expected_value, reverse=True)

        print(f"\n{'=' * 60}")
        print(f"  TOTAL: {len(all_bets)} value bets found across {len(matches)} matches")
        print(f"{'=' * 60}")

        return {
            "matches": all_results,
            "all_bets": all_bets,
            "summary": {
                "total_matches": len(matches),
                "total_value_bets": len(all_bets),
                "low_risk": len([b for b in all_bets if b.risk_level == "LOW"]),
                "medium_risk": len([b for b in all_bets if b.risk_level == "MEDIUM"]),
                "high_risk": len([b for b in all_bets if b.risk_level == "HIGH"]),
            }
        }


def run_engine():
    """Entry point."""
    engine = FootballPredictionEngine()
    return engine.run()


if __name__ == "__main__":
    results = run_engine()

    # Print top 20 bets
    print("\n\nTOP 20 VALUE BETS:")
    print("-" * 120)
    print(f"{'Match':<30} {'Market':<25} {'Outcome':<20} {'Odds':>6} {'Conf':>6} {'EV':>7} {'Risk':>8} {'Stake':>7}")
    print("-" * 120)

    for bet in results["all_bets"][:20]:
        match_str = f"{bet.home_team} vs {bet.away_team}"[:28]
        print(
            f"{match_str:<30} {bet.market_display:<25} {bet.outcome:<20} "
            f"{bet.best_odds:>6.2f} {bet.confidence_pct:>5.1f}% "
            f"{bet.expected_value:>+6.1f}% {bet.risk_level:>8} {bet.recommended_stake:>6.2f}%"
        )
