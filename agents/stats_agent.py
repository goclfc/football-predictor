"""
Stats Agent — Analyzes season-long statistics using Poisson distribution.
The mathematical backbone — uses statistical models for all markets.
"""
from typing import Dict
from scipy.stats import poisson
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class StatsAgent(BaseAgent):
    name = "StatsAgent"
    specialty = "Statistical Models (Poisson/xG)"
    weight = 1.3  # Higher weight — stats are the most reliable predictor

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:

        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]

        # --- GOALS: Poisson Model ---
        # Expected goals for each team based on season attack/defense rates
        home_expected = (home_stats["home_goals_avg"] + away_stats["away_conceded_avg"]) / 2
        away_expected = (away_stats["away_goals_avg"] + home_stats["home_conceded_avg"]) / 2
        total_expected = home_expected + away_expected

        for line in [1.5, 2.5, 3.5]:
            over_prob = 1 - poisson.cdf(int(line), total_expected)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=self._prob_confidence(max(over_prob, 1 - over_prob), 0.72),
                reasoning=f"Poisson model: {home} xG {home_expected:.2f}, {away} xG {away_expected:.2f}, total {total_expected:.2f}",
                data_points=[
                    f"{home} home attack: {home_stats['home_goals_avg']}, {away} away defense: {away_stats['away_conceded_avg']}",
                    f"{away} away attack: {away_stats['away_goals_avg']}, {home} home defense: {home_stats['home_conceded_avg']}"
                ]
            ))

        # Match result probabilities from Poisson
        home_win_prob, draw_prob, away_win_prob = self._poisson_match_result(home_expected, away_expected)
        predictions.append(AgentPrediction(
            market="match_result",
            outcome=f"{home} Win" if home_win_prob >= max(draw_prob, away_win_prob) else
                    ("Draw" if draw_prob >= away_win_prob else f"{away} Win"),
            probability=self._clamp(max(home_win_prob, draw_prob, away_win_prob)),
            confidence=0.68,
            reasoning=f"Poisson: P({home})={home_win_prob:.1%}, P(Draw)={draw_prob:.1%}, P({away})={away_win_prob:.1%}",
        ))

        # BTTS
        home_score_prob = 1 - poisson.pmf(0, home_expected)
        away_score_prob = 1 - poisson.pmf(0, away_expected)
        btts_prob = home_score_prob * away_score_prob
        predictions.append(AgentPrediction(
            market="btts",
            outcome="Yes" if btts_prob > 0.5 else "No",
            probability=self._clamp(max(btts_prob, 1 - btts_prob)),
            confidence=0.7,
            reasoning=f"P({home} scores)={home_score_prob:.1%}, P({away} scores)={away_score_prob:.1%}",
        ))

        # --- CORNERS: Poisson Model ---
        home_corners_exp = home_stats["home_corners_avg"]
        away_corners_exp = away_stats["away_corners_avg"]
        total_corners_exp = home_corners_exp + away_corners_exp

        for line in [8.5, 9.5, 10.5, 11.5]:
            over_prob = 1 - poisson.cdf(int(line), total_corners_exp)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"corners_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.68,
                reasoning=f"Season corners: {home} {home_corners_exp:.1f}/home, {away} {away_corners_exp:.1f}/away, exp total {total_corners_exp:.1f}",
            ))

        # Corner dominance
        if abs(home_corners_exp - away_corners_exp) > 1.0:
            dominant = home if home_corners_exp > away_corners_exp else away
            dom_prob = self._clamp(max(home_corners_exp, away_corners_exp) / total_corners_exp + 0.05)
            predictions.append(AgentPrediction(
                market="corners_home_away",
                outcome=f"{dominant} More Corners",
                probability=dom_prob,
                confidence=0.6,
                reasoning=f"Corner avg gap: {home} {home_corners_exp:.1f} vs {away} {away_corners_exp:.1f}",
            ))

        # --- CARDS: Poisson Model ---
        home_cards_exp = home_stats["home_cards_avg"]
        away_cards_exp = away_stats["away_cards_avg"]
        total_cards_exp = home_cards_exp + away_cards_exp

        for line in [3.5, 4.5, 5.5]:
            over_prob = 1 - poisson.cdf(int(line), total_cards_exp)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"cards_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.62,
                reasoning=f"Season cards: {home} {home_cards_exp:.1f}/home, {away} {away_cards_exp:.1f}/away, exp total {total_cards_exp:.1f}",
            ))

        # --- SHOTS ON TARGET ---
        home_sot = home_stats.get("avg_shots_on_target", 4.5)
        away_sot = away_stats.get("avg_shots_on_target", 4.0)
        total_sot = home_sot + away_sot

        for line in [4.5, 5.5, 6.5]:
            over_prob = 1 - poisson.cdf(int(line), total_sot)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"shots_on_target_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.58,
                reasoning=f"Season SoT: {home} {home_sot:.1f}, {away} {away_sot:.1f}, total {total_sot:.1f}",
            ))

        # --- THROW-INS ---
        home_ti = home_stats.get("avg_throw_ins", 22)
        away_ti = away_stats.get("avg_throw_ins", 22)
        total_ti = home_ti + away_ti

        for line in [21.5, 23.5, 25.5]:
            # Throw-ins roughly follow normal distribution, approx with Poisson
            diff = total_ti - line
            over_prob = self._clamp(0.5 + diff * 0.06)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"throwins_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.45,
                reasoning=f"Season throw-ins: {home} {home_ti:.1f}, {away} {away_ti:.1f}, total {total_ti:.1f}",
            ))

        # First half goals
        fh_expected = total_expected * 0.42  # ~42% of goals in first half
        for line in [0.5, 1.5]:
            over_prob = 1 - poisson.cdf(int(line), fh_expected)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"first_half_goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.6,
                reasoning=f"FH expected goals: {fh_expected:.2f} (42% of {total_expected:.2f} total)",
            ))

        overall = (
            f"Statistical model: {home} xG={home_expected:.2f}, {away} xG={away_expected:.2f}. "
            f"Expected {total_expected:.1f} goals, {total_corners_exp:.1f} corners, {total_cards_exp:.1f} cards. "
            f"Win probs: {home} {home_win_prob:.0%} / Draw {draw_prob:.0%} / {away} {away_win_prob:.0%}."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.75
        )

    def _poisson_match_result(self, home_exp: float, away_exp: float):
        """Calculate match result probabilities using bivariate Poisson."""
        home_win = 0
        draw = 0
        away_win = 0

        for i in range(8):  # max goals to consider
            for j in range(8):
                prob = poisson.pmf(i, home_exp) * poisson.pmf(j, away_exp)
                if i > j:
                    home_win += prob
                elif i == j:
                    draw += prob
                else:
                    away_win += prob

        return home_win, draw, away_win

    def _prob_confidence(self, prob: float, base_confidence: float) -> float:
        """
        Scale confidence based on how extreme the probability is.
        Predictions near 50/50 are more useful than 95/5 predictions.
        Very extreme predictions (>90% or <10%) get reduced confidence
        because they're either obvious or unreliable.
        """
        # prob here is the "winning side" probability (always > 0.5)
        if prob > 0.92:
            # Extremely one-sided — probably obvious, low analytical value
            return base_confidence * 0.5
        elif prob > 0.80:
            return base_confidence * 0.7
        elif prob > 0.65:
            return base_confidence * 0.9
        else:
            # 50-65% range — this is where the money is
            return base_confidence
