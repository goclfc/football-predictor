"""
Value Agent V2 — Fixed circular logic.

V1 Problem: Compared Pinnacle odds vs best available odds.
That measures bookmaker disagreement, not OUR edge.

V2 Fix: Compares our MODEL'S consensus probability (from Stats + Form agents)
against the best available odds. This is the real value detection.

The value agent now works in two passes:
1. Quick scan: identify markets where ANY bookmaker offers odds that
   imply a probability LOWER than what our model estimates
2. Deep check: verify the edge with multiple sanity filters
"""
from typing import Dict, List
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class ValueAgentV2(BaseAgent):
    name = "ValueAgent"
    specialty = "Model vs Market Value Detection"
    weight = 1.5

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:
        """
        Pass 1: Analyze odds structure for bookmaker inefficiencies.
        The REAL value detection happens in meta_agent when we compare
        consensus model probability vs odds. But we can still flag
        structural signals here.
        """
        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        markets = match_data.get("markets", {})

        for market_key, bookmaker_odds in markets.items():
            signals = self._analyze_market_structure(market_key, bookmaker_odds)
            predictions.extend(signals)

        predictions.sort(key=lambda p: p.probability, reverse=True)

        overall = (
            f"Market structure analysis for {home} vs {away}: "
            f"Found {len(predictions)} structural signals across {len(markets)} markets."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.55  # Lower than V1 — this is just structural, real value is in meta
        )

    def _analyze_market_structure(self, market_key: str,
                                    bookmaker_odds: List[Dict]) -> List[AgentPrediction]:
        """
        Analyze the odds structure for signals — but DON'T claim value.
        Just report what the market thinks and flag anomalies.
        """
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

        for outcome, data in outcome_data.items():
            odds_list = data["odds_list"]
            bookmakers = data["bookmakers"]

            if len(odds_list) < 2:
                continue

            avg_odds = sum(odds_list) / len(odds_list)
            best_odds = max(odds_list)
            best_bookie = bookmakers[odds_list.index(best_odds)]

            # Skip extreme odds
            if avg_odds > 10.0:
                continue

            # Pinnacle = sharp reference
            pinnacle_idx = None
            for i, bm in enumerate(bookmakers):
                if bm == "Pinnacle":
                    pinnacle_idx = i
                    break

            if pinnacle_idx is not None:
                sharp_odds = odds_list[pinnacle_idx]
                sharp_prob = 1 / sharp_odds * 0.98  # Remove ~2% margin
            else:
                sharp_prob = 1 / avg_odds * 0.95  # Remove ~5% margin

            if sharp_prob < 0.08:
                continue

            # Odds spread analysis
            odds_spread = (max(odds_list) - min(odds_list)) / avg_odds
            if odds_spread > 0.5:
                continue

            # Signal 1: Sharp money signal (Pinnacle significantly different from average)
            sharp_signal = False
            if pinnacle_idx is not None:
                pinnacle_implied = 1 / odds_list[pinnacle_idx]
                avg_implied = 1 / avg_odds
                if abs(pinnacle_implied - avg_implied) > 0.03:
                    sharp_signal = True

            # Signal 2: Best odds significantly above average (potential value)
            best_vs_avg = (best_odds - avg_odds) / avg_odds
            potential_value = best_vs_avg > 0.03

            # Report as market signal (NOT as value claim — that's meta's job)
            if sharp_signal or potential_value:
                # Confidence is about how RELIABLE the signal is, not how much value
                signal_confidence = 0.45  # Base
                if sharp_signal:
                    signal_confidence += 0.1
                if len(odds_list) >= 4:
                    signal_confidence += 0.05
                if odds_spread < 0.1:
                    signal_confidence += 0.05

                results.append(AgentPrediction(
                    market=market_key,
                    outcome=outcome,
                    probability=self._clamp(sharp_prob),
                    confidence=self._clamp(signal_confidence, 0.3, 0.75),
                    reasoning=(
                        f"Market signal: sharp_prob={sharp_prob:.1%}, "
                        f"best={best_odds:.2f}@{best_bookie}, avg={avg_odds:.2f} "
                        f"{'[SHARP SIGNAL]' if sharp_signal else ''} "
                        f"{'[VALUE POTENTIAL]' if potential_value else ''}"
                    ),
                    data_points=[
                        f"Odds range: {min(odds_list):.2f} - {max(odds_list):.2f}",
                        f"Bookmakers: {len(odds_list)}",
                        f"Spread: {odds_spread:.1%}",
                    ]
                ))

        return results
