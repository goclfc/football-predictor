"""
Form Agent — Analyzes recent form (last 5-10 matches) to predict current match.
Focuses on momentum, scoring/conceding trends, and recent corner/card patterns.
"""
from typing import Dict
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class FormAgent(BaseAgent):
    name = "FormAgent"
    specialty = "Recent Form Analysis"
    weight = 1.2

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:

        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]

        # --- Goals Markets ---
        home_scoring = home_form["goals_scored_avg"]
        away_scoring = away_form["goals_scored_avg"]
        home_conceding = home_form["goals_conceded_avg"]
        away_conceding = away_form["goals_conceded_avg"]
        expected_goals = home_scoring + away_scoring  # simplified

        # Over/Under 2.5 based on form
        over_25_prob = self._goals_to_over_prob(expected_goals, 2.5)
        predictions.append(AgentPrediction(
            market="goals_over_under_2.5",
            outcome="Over 2.5" if over_25_prob > 0.5 else "Under 2.5",
            probability=self._clamp(max(over_25_prob, 1 - over_25_prob)),
            confidence=0.65,
            reasoning=f"{home} avg {home_scoring} goals, {away} avg {away_scoring} goals in last 10",
            data_points=[f"{home} form: {home_form['form_string']}", f"{away} form: {away_form['form_string']}"]
        ))

        # BTTS
        btts_prob = self._clamp(1 - (1 - home_scoring/2.5) * (1 - away_scoring/2.5))
        predictions.append(AgentPrediction(
            market="btts",
            outcome="Yes" if btts_prob > 0.5 else "No",
            probability=self._clamp(max(btts_prob, 1 - btts_prob)),
            confidence=0.6,
            reasoning=f"Both teams scoring rates: {home} scores {home_scoring}/game, {away} scores {away_scoring}/game",
        ))

        # --- Corners Markets ---
        home_corners = home_form["corners_avg"]
        away_corners = away_form["corners_avg"]
        total_corners = home_corners + away_corners

        for line in [8.5, 9.5, 10.5, 11.5]:
            over_prob = self._corners_to_over_prob(total_corners, line)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"corners_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.6 + (0.05 if abs(over_prob - 0.5) > 0.15 else 0),
                reasoning=f"Form corners avg: {home} {home_corners}, {away} {away_corners}, total ~{total_corners:.1f}",
                data_points=[f"Last 10 combined avg: {total_corners:.1f}"]
            ))

        # --- Cards Markets ---
        home_cards = home_form["cards_avg"]
        away_cards = away_form["cards_avg"]
        total_cards = home_cards + away_cards

        for line in [3.5, 4.5, 5.5]:
            over_prob = self._cards_to_over_prob(total_cards, line)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"cards_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.55,
                reasoning=f"Form cards avg: {home} {home_cards}, {away} {away_cards}, total ~{total_cards:.1f}",
            ))

        # --- Throw-ins ---
        home_ti = home_form["throw_ins_avg"]
        away_ti = away_form["throw_ins_avg"]
        total_ti = home_ti + away_ti

        for line in [21.5, 23.5, 25.5]:
            diff = total_ti - line
            over_prob = self._clamp(0.5 + diff * 0.08)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"throwins_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.45,  # Lower confidence — throw-ins are harder to predict
                reasoning=f"Form throw-ins avg: {home} {home_ti:.1f}, {away} {away_ti:.1f}",
            ))

        # --- Momentum assessment ---
        home_momentum = self._calc_momentum(home_form)
        away_momentum = self._calc_momentum(away_form)

        overall = (
            f"{home} momentum: {'STRONG' if home_momentum > 0.6 else 'MODERATE' if home_momentum > 0.4 else 'WEAK'} "
            f"({home_form['form_string'][-5:]}). "
            f"{away} momentum: {'STRONG' if away_momentum > 0.6 else 'MODERATE' if away_momentum > 0.4 else 'WEAK'} "
            f"({away_form['form_string'][-5:]}). "
            f"Expected ~{expected_goals:.1f} goals, ~{total_corners:.1f} corners, ~{total_cards:.1f} cards."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.65
        )

    def _calc_momentum(self, form: Dict) -> float:
        """Calculate momentum — recent results weighted more heavily."""
        form_str = form["form_string"]
        score = 0
        for i, r in enumerate(reversed(form_str)):
            weight = 1 + i * 0.2  # More recent = higher weight
            if r == "W": score += 3 * weight
            elif r == "D": score += 1 * weight
        max_score = sum(3 * (1 + i * 0.2) for i in range(len(form_str)))
        return score / max_score if max_score > 0 else 0.5

    def _goals_to_over_prob(self, expected: float, line: float) -> float:
        """Convert expected goals to over probability using simplified Poisson."""
        from scipy.stats import poisson
        prob_under = poisson.cdf(int(line), expected)
        return self._clamp(1 - prob_under)

    def _corners_to_over_prob(self, expected: float, line: float) -> float:
        from scipy.stats import poisson
        return self._clamp(1 - poisson.cdf(int(line), expected))

    def _cards_to_over_prob(self, expected: float, line: float) -> float:
        from scipy.stats import poisson
        return self._clamp(1 - poisson.cdf(int(line), expected))
