"""
Meta Agent — The orchestrator that combines all agent predictions.
Weighs each agent's confidence and reliability, resolves disagreements,
and produces the final ranked list of value bets.
"""
from typing import Dict, List, Tuple
from collections import defaultdict
from .base_agent import AgentReport, AgentPrediction
from dataclasses import dataclass, field


@dataclass
class FinalBet:
    """A final bet recommendation after all agents have voted."""
    match_id: str
    home_team: str
    away_team: str
    league: str
    match_date: str             # Match date/time
    market: str
    market_display: str
    outcome: str
    confidence_pct: float       # Final confidence (0-100)
    best_odds: float            # Best available odds
    best_bookmaker: str
    expected_value: float       # EV as percentage
    agent_agreement: float      # What % of agents agree (0-100)
    reasoning: List[str]        # Combined reasoning from agents
    risk_level: str             # LOW / MEDIUM / HIGH
    recommended_stake: float    # % of bankroll (Kelly-inspired)


class MetaAgent:
    """Orchestrator that synthesizes all agent reports into final bet recommendations."""

    # Agent weights (how much we trust each agent)
    AGENT_WEIGHTS = {
        "StatsAgent": 1.3,
        "FormAgent": 1.2,
        "MarketAgent": 1.1,
        "HistoricalAgent": 0.9,
        "ValueAgent": 1.5,
    }

    MARKET_DISPLAY_NAMES = {
        "match_result": "Match Result",
        "btts": "Both Teams to Score",
        "double_chance": "Double Chance",
        "corners_home_away": "Corner Dominance",
    }

    def synthesize(self, match_data: Dict, agent_reports: List[AgentReport]) -> List[FinalBet]:
        """Combine all agent reports into final ranked bet recommendations."""
        home = match_data["home_team"]
        away = match_data["away_team"]
        league = match_data.get("league", "Unknown")
        match_date = match_data.get("commence_time", "TBD")
        markets = match_data.get("markets", {})

        # Group all predictions by market+outcome
        market_predictions = defaultdict(list)
        for report in agent_reports:
            for pred in report.predictions:
                key = (pred.market, pred.outcome)
                market_predictions[key].append({
                    "agent": report.agent_name,
                    "probability": pred.probability,
                    "confidence": pred.confidence,
                    "reliability": report.reliability_score,
                    "reasoning": pred.reasoning,
                    "data_points": pred.data_points,
                })

        final_bets = []

        for (market_key, outcome), agent_preds in market_predictions.items():
            # Calculate weighted consensus probability
            total_weight = 0
            weighted_prob = 0
            weighted_confidence = 0

            for ap in agent_preds:
                w = self.AGENT_WEIGHTS.get(ap["agent"], 1.0) * ap["reliability"] * ap["confidence"]
                weighted_prob += ap["probability"] * w
                weighted_confidence += ap["confidence"] * w
                total_weight += w

            if total_weight == 0:
                continue

            consensus_prob = weighted_prob / total_weight
            consensus_confidence = weighted_confidence / total_weight

            # How many agents agree on this outcome for this market?
            # Count agents that predicted ANY outcome for this market
            agents_on_market = set()
            agents_agreeing = set()
            for report in agent_reports:
                for pred in report.predictions:
                    if pred.market == market_key:
                        agents_on_market.add(report.agent_name)
                        if pred.outcome == outcome:
                            agents_agreeing.add(report.agent_name)

            agreement = len(agents_agreeing) / len(agents_on_market) * 100 if agents_on_market else 0

            # Find the best available odds for this outcome
            best_odds, best_bookie = self._find_best_odds(markets, market_key, outcome)

            if best_odds is None:
                continue

            # Calculate Expected Value
            implied_prob = 1 / best_odds
            ev = (consensus_prob * best_odds) - 1

            # Only include if EV > 0 (positive expected value)
            if ev <= 0:
                continue

            # SANITY CHECKS — filter out garbage predictions
            # 1. Skip extreme odds (longshots with unreliable edge)
            if best_odds > 10.0:
                continue

            # 2. Skip if consensus probability is very low (< 15%)
            #    These are longshots where tiny model errors create fake EV
            if consensus_prob < 0.15:
                continue

            # 3. Cap EV at 50% — anything higher is almost certainly a model error
            #    In reality, bookmakers rarely misprice by more than 10-15%
            if ev > 0.50:
                ev = min(ev, 0.50)

            # 4. Require minimum 2 agents to have predicted this market
            if len(agent_preds) < 2:
                continue

            # Risk assessment
            risk = self._assess_risk(consensus_confidence, agreement, ev, len(agent_preds))

            # Kelly criterion for stake sizing (fractional Kelly = conservative)
            kelly_fraction = self._kelly_stake(consensus_prob, best_odds)

            # Collect all reasoning
            all_reasoning = [ap["reasoning"] for ap in agent_preds if ap["reasoning"]]

            final_bets.append(FinalBet(
                match_id=match_data["id"],
                home_team=home,
                away_team=away,
                league=league,
                match_date=match_date,
                market=market_key,
                market_display=self._format_market_name(market_key),
                outcome=outcome,
                confidence_pct=round(consensus_confidence * 100, 1),
                best_odds=best_odds,
                best_bookmaker=best_bookie,
                expected_value=round(ev * 100, 2),
                agent_agreement=round(agreement, 1),
                reasoning=all_reasoning[:3],  # Top 3 reasons
                risk_level=risk,
                recommended_stake=round(kelly_fraction * 100, 2),
            ))

        # Sort by: confidence * EV (best bets first)
        final_bets.sort(key=lambda b: b.confidence_pct * b.expected_value, reverse=True)

        return final_bets

    def _find_best_odds(self, markets: Dict, market_key: str, outcome: str) -> Tuple:
        """Find the best available odds for an outcome across bookmakers."""
        bookmaker_odds = markets.get(market_key, [])
        best_odds = None
        best_bookie = None

        for bookie in bookmaker_odds:
            for out, odds in bookie["odds"].items():
                if out == outcome:
                    if best_odds is None or odds > best_odds:
                        best_odds = odds
                        best_bookie = bookie["bookmaker"]

        return best_odds, best_bookie

    def _assess_risk(self, confidence: float, agreement: float, ev: float, num_agents: int) -> str:
        """Assess the risk level of a bet."""
        score = confidence * 0.4 + (agreement / 100) * 0.3 + min(ev * 5, 0.3)
        if num_agents >= 3:
            score += 0.1

        if score > 0.7:
            return "LOW"
        elif score > 0.45:
            return "MEDIUM"
        return "HIGH"

    def _kelly_stake(self, prob: float, odds: float) -> float:
        """Calculate Kelly criterion stake (fractional = 25% Kelly for safety)."""
        b = odds - 1
        q = 1 - prob
        if b <= 0:
            return 0
        kelly = (b * prob - q) / b
        # Use 25% Kelly (conservative)
        return max(0, min(kelly * 0.25, 0.05))  # Cap at 5% of bankroll

    def _format_market_name(self, market_key: str) -> str:
        """Convert market key to human-readable name."""
        if market_key in self.MARKET_DISPLAY_NAMES:
            return self.MARKET_DISPLAY_NAMES[market_key]

        # Auto-format
        name = market_key.replace("_", " ").title()
        name = name.replace("Over Under", "O/U")
        name = name.replace("Goals O/U", "Goals O/U")
        name = name.replace("Corners O/U", "Corners O/U")
        name = name.replace("Cards O/U", "Cards O/U")
        name = name.replace("Throwins O/U", "Throw-ins O/U")
        name = name.replace("Shots On Target O/U", "Shots on Target O/U")
        name = name.replace("First Half Goals O/U", "1st Half Goals O/U")
        return name
