"""
Historical Agent — Analyzes head-to-head records and historical patterns.
Focuses on rivalry patterns, historical over/under trends, and venue effects.
"""
from typing import Dict
from .base_agent import BaseAgent, AgentReport, AgentPrediction


class HistoricalAgent(BaseAgent):
    name = "HistoricalAgent"
    specialty = "Head-to-Head & Historical Patterns"
    weight = 0.9

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:

        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        total_h2h = h2h["total_matches"]

        # If no H2H data, return empty report
        if total_h2h == 0:
            return AgentReport(
                agent_name=self.name, match_id=match_data["id"],
                home_team=home, away_team=away, predictions=[],
                overall_assessment=f"No H2H data available for {home} vs {away}.",
                reliability_score=0.1,
            )

        # --- Goals from H2H ---
        avg_goals = h2h["avg_goals_per_match"]
        from scipy.stats import poisson

        for line in [1.5, 2.5, 3.5]:
            over_prob = self._clamp(1 - poisson.cdf(int(line), avg_goals))
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=min(0.7, 0.4 + total_h2h * 0.02),  # More H2H data = more confidence
                reasoning=f"H2H avg {avg_goals:.1f} goals/match over {total_h2h} meetings",
                data_points=[
                    f"H2H record: {home} {h2h['home_wins']}W - {h2h['draws']}D - {h2h['away_wins']}W {away}",
                    f"Over 2.5 in {h2h['over_2_5_percentage']}% of H2H meetings"
                ]
            ))

        # --- BTTS from H2H ---
        btts_pct = h2h["btts_percentage"] / 100
        predictions.append(AgentPrediction(
            market="btts",
            outcome="Yes" if btts_pct > 0.5 else "No",
            probability=self._clamp(max(btts_pct, 1 - btts_pct)),
            confidence=min(0.65, 0.35 + total_h2h * 0.02),
            reasoning=f"BTTS hit in {h2h['btts_percentage']}% of {total_h2h} H2H meetings",
        ))

        # --- Corners from H2H ---
        avg_corners = h2h["avg_corners_per_match"]
        for line in [8.5, 9.5, 10.5, 11.5]:
            over_prob = self._clamp(1 - poisson.cdf(int(line), avg_corners))
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"corners_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=min(0.6, 0.35 + total_h2h * 0.015),
                reasoning=f"H2H avg {avg_corners:.1f} corners/match",
                data_points=[f"Sample size: {total_h2h} matches"]
            ))

        # --- Cards from H2H ---
        avg_cards = h2h["avg_cards_per_match"]
        for line in [3.5, 4.5, 5.5]:
            over_prob = self._clamp(1 - poisson.cdf(int(line), avg_cards))
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"cards_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=min(0.55, 0.3 + total_h2h * 0.015),
                reasoning=f"H2H avg {avg_cards:.1f} cards/match (derby factor may increase)",
            ))

        # --- Match Result from H2H ---
        home_win_pct = h2h["home_wins"] / total_h2h
        draw_pct = h2h["draws"] / total_h2h
        away_win_pct = h2h["away_wins"] / total_h2h

        best_outcome = max(
            (home_win_pct, f"{home} Win"),
            (draw_pct, "Draw"),
            (away_win_pct, f"{away} Win"),
            key=lambda x: x[0]
        )

        predictions.append(AgentPrediction(
            market="match_result",
            outcome=best_outcome[1],
            probability=self._clamp(best_outcome[0]),
            confidence=min(0.5, 0.25 + total_h2h * 0.015),
            reasoning=f"H2H: {home} {h2h['home_wins']}W-{h2h['draws']}D-{h2h['away_wins']}W {away} in {total_h2h} games",
        ))

        overall = (
            f"Historical: {total_h2h} meetings between {home} and {away}. "
            f"Avg {avg_goals:.1f} goals, {avg_corners:.1f} corners, {avg_cards:.1f} cards per match. "
            f"BTTS in {h2h['btts_percentage']}% of games. "
            f"H2H advantage: {'HOME' if home_win_pct > away_win_pct else 'AWAY' if away_win_pct > home_win_pct else 'EVEN'}."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=min(0.7, 0.4 + total_h2h * 0.02)
        )
