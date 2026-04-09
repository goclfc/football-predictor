"""
Value Agent — The key agent that compares model probabilities vs bookmaker odds.
Identifies positive Expected Value (+EV) bets.
A bet has value when: our_probability > implied_probability_from_odds
"""
from typing import Dict, List
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class ValueAgent(BaseAgent):
    name = "ValueAgent"
    specialty = "Value Bet Detection (+EV)"
    weight = 1.5  # Highest weight — this is the money-making agent

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:
        """
        This agent is special — it doesn't generate its own probability estimates.
        Instead, it's called AFTER other agents and compares their consensus vs odds.
        For the initial pass, it analyzes the odds structure for value indicators.
        """
        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        markets = match_data.get("markets", {})

        for market_key, bookmaker_odds in markets.items():
            value_bets = self._find_value_in_market(market_key, bookmaker_odds)
            predictions.extend(value_bets)

        # Sort by expected value
        predictions.sort(key=lambda p: p.probability * (1/p.confidence if p.confidence > 0 else 0), reverse=True)

        value_count = len([p for p in predictions if p.confidence > 0.6])
        overall = (
            f"Value scan for {home} vs {away}: "
            f"Found {value_count} high-confidence value opportunities across {len(markets)} markets."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.6
        )

    def _find_value_in_market(self, market_key: str, bookmaker_odds: List[Dict]) -> List[AgentPrediction]:
        """Find value bets within a single market by analyzing odds structure."""
        if not bookmaker_odds:
            return []

        results = []

        # Aggregate odds per outcome
        outcome_data = {}
        for bookie in bookmaker_odds:
            for outcome, odds in bookie["odds"].items():
                if outcome not in outcome_data:
                    outcome_data[outcome] = {"odds_list": [], "bookmakers": []}
                outcome_data[outcome]["odds_list"].append(odds)
                outcome_data[outcome]["bookmakers"].append(bookie["bookmaker"])

        # Calculate the "true" probability using Pinnacle (sharpest bookmaker) or average
        for outcome, data in outcome_data.items():
            odds_list = data["odds_list"]
            bookmakers = data["bookmakers"]

            # SANITY CHECK 1: Skip extreme odds (> 10.0) — bookmaker spread at these
            # levels is noise, not signal. A 0-0 bet at 26.00 is not a value bet.
            avg_odds = sum(odds_list) / len(odds_list)
            if avg_odds > 10.0:
                continue  # Skip longshots — edge is unreliable

            # SANITY CHECK 2: Need at least 2 bookmakers to compare
            if len(odds_list) < 2:
                continue

            # Find Pinnacle odds (sharp bookmaker = closest to true probability)
            pinnacle_idx = None
            for i, bm in enumerate(bookmakers):
                if bm == "Pinnacle":
                    pinnacle_idx = i
                    break

            # Sharp probability (from Pinnacle, or average if Pinnacle not available)
            if pinnacle_idx is not None:
                sharp_odds = odds_list[pinnacle_idx]
                # Remove Pinnacle margin (~2%)
                sharp_prob = (1 / sharp_odds) * 0.98
            else:
                # Remove average margin (~5%)
                sharp_prob = (1 / avg_odds) * 0.95

            # Find the best available odds across all bookmakers
            best_odds = max(odds_list)
            best_bookie_idx = odds_list.index(best_odds)
            best_bookie = bookmakers[best_bookie_idx]
            implied_prob = 1 / best_odds

            # SANITY CHECK 3: If the sharp probability itself is very low (<10%),
            # the edge is unreliable — small errors in probability create fake EV
            if sharp_prob < 0.10:
                continue

            # SANITY CHECK 4: If odds spread between bookmakers is too wild (>50%),
            # it's likely a data/timing issue, not real value
            odds_spread = (max(odds_list) - min(odds_list)) / avg_odds
            if odds_spread > 0.5:
                continue

            # Expected Value: (prob * odds) - 1
            ev = (sharp_prob * best_odds) - 1

            # Only flag if there's positive EV with at least 3% edge
            if ev > 0.03:
                # Confidence scales with: number of bookmakers, odds range tightness, EV size
                confidence = self._ev_to_confidence(ev, len(odds_list), odds_spread, sharp_prob)

                results.append(AgentPrediction(
                    market=market_key,
                    outcome=outcome,
                    probability=self._clamp(sharp_prob),
                    confidence=confidence,
                    reasoning=(
                        f"VALUE BET: EV={ev:+.1%} | "
                        f"True prob ~{sharp_prob:.1%} vs implied {implied_prob:.1%} | "
                        f"Best odds {best_odds:.2f} @ {best_bookie} | "
                        f"{len(odds_list)} bookmakers compared"
                    ),
                    data_points=[
                        f"EV: {ev:+.3f}",
                        f"Best odds: {best_odds} @ {best_bookie}",
                        f"Odds range: {min(odds_list):.2f} - {max(odds_list):.2f}",
                        f"Bookmakers: {len(odds_list)}",
                    ]
                ))

        return results

    def _ev_to_confidence(self, ev: float, num_bookmakers: int = 2,
                           odds_spread: float = 0.1, prob: float = 0.5) -> float:
        """
        Calculate confidence based on multiple factors:
        - EV size (higher = more confident, but diminishing returns)
        - Number of bookmakers compared (more = more reliable)
        - Odds spread (tighter = more reliable signal)
        - Base probability (mid-range probabilities are more reliable)
        """
        # Base confidence from EV (capped — huge EV is often a data artifact)
        ev_score = min(ev * 3, 0.3)  # Max 0.3 from EV alone

        # Bookmaker count bonus (more opinions = more reliable)
        bookie_score = min(num_bookmakers * 0.04, 0.2)  # Max 0.2

        # Tight odds spread = bookmakers agree = more reliable
        spread_score = max(0, 0.2 - odds_spread * 0.4)  # Max 0.2

        # Mid-range probabilities are more reliable than extremes
        # Peak confidence at 40-60% probability, drops off at extremes
        prob_score = 0.15 * (1 - abs(prob - 0.5) * 2)  # Max 0.15

        # Base floor
        confidence = 0.35 + ev_score + bookie_score + spread_score + prob_score

        return self._clamp(confidence, 0.3, 0.85)
