"""
Market Agent — Analyzes bookmaker odds for value detection.
Looks for: line movements, bookmaker disagreements, margin analysis, sharp money signals.
"""
from typing import Dict, List
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class MarketAgent(BaseAgent):
    name = "MarketAgent"
    specialty = "Odds Analysis & Market Intelligence"
    weight = 1.1

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:

        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        markets = match_data.get("markets", {})

        for market_key, bookmaker_odds in markets.items():
            analysis = self._analyze_market(market_key, bookmaker_odds)
            if analysis:
                predictions.append(analysis)

        overall_signals = self._detect_market_signals(markets)
        overall = (
            f"Market analysis for {home} vs {away}: "
            f"{len(predictions)} markets analyzed. "
            f"Signals: {overall_signals}"
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.7
        )

    def _analyze_market(self, market_key: str, bookmaker_odds: List[Dict]) -> AgentPrediction:
        """Analyze a single market across all bookmakers."""
        if not bookmaker_odds:
            return None

        # Collect all odds per outcome
        outcome_odds = {}
        for bookie in bookmaker_odds:
            for outcome, odds in bookie["odds"].items():
                if outcome not in outcome_odds:
                    outcome_odds[outcome] = []
                outcome_odds[outcome].append({"bookmaker": bookie["bookmaker"], "odds": odds})

        # Find the best value: highest odds (= bookmaker thinks it's less likely than others do)
        best_value = None
        best_score = 0

        for outcome, odds_list in outcome_odds.items():
            all_odds = [o["odds"] for o in odds_list]
            avg_odds = sum(all_odds) / len(all_odds)
            max_odds = max(all_odds)
            min_odds = min(all_odds)

            # Implied probability from average odds
            implied_prob = 1 / avg_odds

            # Bookmaker disagreement score: higher = more disagreement = potential value
            spread = (max_odds - min_odds) / avg_odds if avg_odds > 0 else 0

            # Pinnacle (sharp bookmaker) odds vs others
            pinnacle_odds = None
            for o in odds_list:
                if o["bookmaker"] == "Pinnacle":
                    pinnacle_odds = o["odds"]
                    break

            # If Pinnacle gives higher odds than average, sharp money might be on the other side
            sharp_signal = 0
            if pinnacle_odds:
                sharp_signal = (pinnacle_odds - avg_odds) / avg_odds

            value_score = spread + abs(sharp_signal) * 2

            if value_score > best_score:
                best_score = value_score
                best_bookie = max(odds_list, key=lambda x: x["odds"])
                best_value = {
                    "outcome": outcome,
                    "avg_odds": avg_odds,
                    "best_odds": max_odds,
                    "best_bookmaker": best_bookie["bookmaker"],
                    "implied_prob": implied_prob,
                    "spread": spread,
                    "sharp_signal": sharp_signal,
                    "value_score": value_score,
                }

        if not best_value:
            return None

        # Determine market probability from consensus
        market_prob = best_value["implied_prob"]

        # Confidence based on bookmaker agreement
        confidence = self._clamp(0.5 + best_value["spread"] * 2 + abs(best_value["sharp_signal"]) * 3, 0.3, 0.85)

        reasoning_parts = [
            f"Avg odds: {best_value['avg_odds']:.2f} (implied {market_prob:.1%})",
            f"Best: {best_value['best_odds']:.2f} @ {best_value['best_bookmaker']}",
        ]
        if best_value["spread"] > 0.05:
            reasoning_parts.append(f"Bookmaker disagreement: {best_value['spread']:.1%}")
        if abs(best_value["sharp_signal"]) > 0.02:
            direction = "higher" if best_value["sharp_signal"] > 0 else "lower"
            reasoning_parts.append(f"Pinnacle {direction} than market avg")

        return AgentPrediction(
            market=market_key,
            outcome=best_value["outcome"],
            probability=self._clamp(market_prob),
            confidence=confidence,
            reasoning=" | ".join(reasoning_parts),
            data_points=[f"Spread: {best_value['spread']:.3f}", f"Value score: {best_value['value_score']:.3f}"]
        )

    def _detect_market_signals(self, markets: Dict) -> str:
        """Detect overall market signals across all markets."""
        signals = []
        high_spread_count = 0

        for market_key, bookmaker_odds in markets.items():
            if not bookmaker_odds:
                continue
            for bookie_data in bookmaker_odds:
                odds_values = list(bookie_data["odds"].values())
                if len(odds_values) >= 2:
                    spread = max(odds_values) - min(odds_values)
                    if spread > 1.5:
                        high_spread_count += 1

        if high_spread_count > 5:
            signals.append("HIGH bookmaker disagreement across markets")
        elif high_spread_count > 2:
            signals.append("Moderate bookmaker disagreement")
        else:
            signals.append("Markets well-aligned")

        return " | ".join(signals) if signals else "No significant signals"
