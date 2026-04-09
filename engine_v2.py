"""
Engine V2 — Uses upgraded agents:
- StatsAgentV2 (Dixon-Coles + Elo + referee cards)
- ValueAgentV2 (fixed circular logic)
- Same FormAgent, HistoricalAgent, MarketAgent (still useful)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict
from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent_v2 import StatsAgentV2
from agents.market_agent import MarketAgent
from agents.value_agent_v2 import ValueAgentV2
from agents.meta_agent import MetaAgent, FinalBet


class FootballPredictionEngineV2:
    """V2 engine with improved agents."""

    def __init__(self):
        self.agents = [
            FormAgent(),
            HistoricalAgent(),
            StatsAgentV2(),       # Dixon-Coles + Elo
            MarketAgent(),
            ValueAgentV2(),       # Fixed value detection
        ]
        self.meta_agent = MetaAgent()

    def analyze_match(self, match_data: Dict, home_form: Dict, away_form: Dict,
                       h2h: Dict, home_stats: Dict, away_stats: Dict) -> List[FinalBet]:
        """Run all agents on a single match and return value bets."""
        agent_reports = []
        for agent in self.agents:
            try:
                report = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats)
                agent_reports.append(report)
            except Exception as e:
                print(f"    Agent {agent.name} error: {e}")

        return self.meta_agent.synthesize(match_data, agent_reports)


# Quick test
if __name__ == "__main__":
    engine = FootballPredictionEngineV2()

    # Test with a sample match
    from data.collector import OddsCollector, StatsCollector
    odds_col = OddsCollector()
    stats_col = StatsCollector()

    matches = odds_col.get_upcoming_odds()
    if matches:
        m = matches[0]
        home = m["home_team"]
        away = m["away_team"]
        print(f"Testing: {home} vs {away}")

        hf = stats_col.get_team_form(home)
        af = stats_col.get_team_form(away)
        h2h = stats_col.get_head_to_head(home, away)
        hs = stats_col.get_team_stats(home)
        as_ = stats_col.get_team_stats(away)

        bets = engine.analyze_match(m, hf, af, h2h, hs, as_)
        print(f"\nFound {len(bets)} value bets:")
        for b in bets[:10]:
            print(f"  {b.market_display}: {b.outcome} @ {b.best_odds:.2f} "
                  f"(conf: {b.confidence_pct:.1f}%, EV: {b.expected_value:+.1f}%)")
