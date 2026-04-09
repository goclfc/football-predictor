"""
Context Agent — Match context analysis.

Analyzes non-statistical factors that affect match outcomes:
1. Derby/rivalry intensity → more cards, tighter games
2. League position motivation → relegation battles, title races
3. Recent scheduling (congestion, rest days)
4. Season phase (early, mid, late, final day)
5. Home/away strength differential
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from .base_agent import BaseAgent, AgentReport, AgentPrediction


# Derby pairs with intensity levels (1-3)
DERBIES = {
    # EPL
    frozenset({"Arsenal","Tottenham"}): 3,
    frozenset({"Liverpool","Everton"}): 3,
    frozenset({"Manchester City","Manchester United"}): 3,
    frozenset({"Man City","Man United"}): 3,
    frozenset({"Chelsea","Arsenal"}): 2,
    frozenset({"Chelsea","Tottenham"}): 2,
    frozenset({"Newcastle","Sunderland"}): 3,
    frozenset({"West Ham","Millwall"}): 3,
    # La Liga
    frozenset({"Real Madrid","Barcelona"}): 3,
    frozenset({"Real Madrid","Atletico Madrid"}): 3,
    frozenset({"Sevilla","Betis"}): 3,
    frozenset({"Valencia","Villarreal"}): 2,
    # Serie A
    frozenset({"Inter","AC Milan"}): 3,
    frozenset({"Inter Milan","AC Milan"}): 3,
    frozenset({"Roma","Lazio"}): 3,
    frozenset({"Juventus","Inter"}): 2,
    frozenset({"Juventus","Inter Milan"}): 2,
    frozenset({"Napoli","Roma"}): 2,
    frozenset({"Napoli","Juventus"}): 2,
    # Bundesliga
    frozenset({"Bayern Munich","Borussia Dortmund"}): 3,
    frozenset({"Bayern Munich","Dortmund"}): 3,
    frozenset({"Schalke","Dortmund"}): 3,
    frozenset({"Schalke","Borussia Dortmund"}): 3,
    # Ligue 1
    frozenset({"PSG","Marseille"}): 3,
    frozenset({"Paris Saint-Germain","Marseille"}): 3,
    frozenset({"Lyon","Saint-Etienne"}): 3,
    frozenset({"Monaco","Nice"}): 2,
    frozenset({"Lille","Lens"}): 2,
}

# Stat adjustments by derby intensity
DERBY_ADJUSTMENTS = {
    3: {"cards_mult": 1.20, "fouls_mult": 1.10, "goals_mult": 0.95, "draw_boost": 0.04},
    2: {"cards_mult": 1.12, "fouls_mult": 1.06, "goals_mult": 0.98, "draw_boost": 0.02},
    1: {"cards_mult": 1.05, "fouls_mult": 1.03, "goals_mult": 1.00, "draw_boost": 0.01},
}

# Position-based motivation
MOTIVATION_CONTEXTS = {
    "title_race": {"intensity": 1.15, "focus_mult": 1.05, "cards_mult": 1.08},
    "cl_chase": {"intensity": 1.10, "focus_mult": 1.03, "cards_mult": 1.05},
    "relegation_battle": {"intensity": 1.20, "focus_mult": 1.08, "cards_mult": 1.15},
    "midtable": {"intensity": 0.95, "focus_mult": 0.98, "cards_mult": 0.95},
    "nothing_to_play_for": {"intensity": 0.85, "focus_mult": 0.92, "cards_mult": 0.88},
}


class ContextAgent(BaseAgent):
    name = "ContextAgent"
    specialty = "Match Context (Derby, Motivation, Schedule)"
    weight = 0.8  # Lower weight — supplementary agent

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats) -> AgentReport:
        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        league = match_data.get("league", "Unknown")
        notes = []

        # === 1. DERBY ANALYSIS ===
        pair = frozenset({home, away})
        derby_intensity = DERBIES.get(pair, 0)
        if derby_intensity > 0:
            adj = DERBY_ADJUSTMENTS[derby_intensity]
            notes.append(f"DERBY (intensity {derby_intensity}/3): +{(adj['cards_mult']-1)*100:.0f}% cards, +{adj['draw_boost']*100:.0f}% draw boost")

            # Derby → more cards
            predictions.append(AgentPrediction(
                market="cards_context",
                outcome=f"Derby cards boost x{adj['cards_mult']:.2f}",
                probability=0.65 + derby_intensity * 0.05,
                confidence=0.70,
                reasoning=f"Derby intensity {derby_intensity}/3: historically +{(adj['cards_mult']-1)*100:.0f}% more cards",
                data_points=[f"Empirical: tight matches (GD≤1) have 10-15% more cards"],
            ))

            # Derby → draw more likely
            predictions.append(AgentPrediction(
                market="match_result",
                outcome="Draw",
                probability=0.28 + adj["draw_boost"],
                confidence=0.55,
                reasoning=f"Derby draw boost: +{adj['draw_boost']*100:.1f}% (derbies tend to be tighter)",
            ))

        # === 2. MOTIVATION ANALYSIS ===
        home_pos = home_stats.get("league_position")
        away_pos = away_stats.get("league_position")
        total_teams = 20  # Most leagues

        home_motivation = self._get_motivation(home_pos, total_teams, league)
        away_motivation = self._get_motivation(away_pos, total_teams, league)

        if home_motivation != "midtable" or away_motivation != "midtable":
            notes.append(f"Motivation: {home}={home_motivation}, {away}={away_motivation}")

            # Relegation battle → more fouls/cards, tighter game
            if home_motivation == "relegation_battle" or away_motivation == "relegation_battle":
                predictions.append(AgentPrediction(
                    market="cards_context",
                    outcome="Relegation battle: elevated cards",
                    probability=0.68,
                    confidence=0.60,
                    reasoning=f"Relegation battle: +15% more cards, more desperate fouls",
                    data_points=[f"{home} pos:{home_pos}, {away} pos:{away_pos}"],
                ))

            # Title race → focused, fewer silly fouls but higher intensity
            if home_motivation == "title_race" or away_motivation == "title_race":
                predictions.append(AgentPrediction(
                    market="goals_context",
                    outcome="Title race: slightly fewer goals",
                    probability=0.55,
                    confidence=0.50,
                    reasoning="Title race matches tend to be cagey — teams can't afford mistakes",
                ))

            # Nothing to play for → open game, more goals
            if home_motivation == "nothing_to_play_for" and away_motivation == "nothing_to_play_for":
                predictions.append(AgentPrediction(
                    market="goals_context",
                    outcome="Low stakes: more open game",
                    probability=0.58,
                    confidence=0.45,
                    reasoning="Both teams have nothing to play for — historically more open, end-to-end football",
                ))

        # === 3. HOME/AWAY STRENGTH DIFFERENTIAL ===
        home_goals = home_stats.get("home_goals_avg", 1.3)
        away_goals = away_stats.get("away_goals_avg", 1.0)
        home_conceded = home_stats.get("home_conceded_avg", 0.9)
        away_conceded = away_stats.get("away_conceded_avg", 1.3)

        home_strength = home_goals - home_conceded  # positive = strong at home
        away_strength = away_goals - away_conceded  # positive = strong away

        if home_strength > 0.5:
            predictions.append(AgentPrediction(
                market="match_result",
                outcome=f"{home} Win",
                probability=0.52,
                confidence=0.45,
                reasoning=f"{home} strong at home: scoring {home_goals:.1f}, conceding {home_conceded:.1f} (net +{home_strength:.1f})",
            ))
        if away_strength > 0.3:
            predictions.append(AgentPrediction(
                market="match_result",
                outcome=f"{away} Win",
                probability=0.40,
                confidence=0.40,
                reasoning=f"{away} decent away: scoring {away_goals:.1f}, conceding {away_conceded:.1f} (net +{away_strength:.1f})",
            ))

        # === 4. HEAD-TO-HEAD PATTERNS ===
        total_h2h = h2h.get("total_matches", 0)
        if total_h2h >= 3:
            h2h_draws = h2h.get("draws", 0)
            h2h_draw_pct = h2h_draws / total_h2h
            if h2h_draw_pct > 0.35:
                predictions.append(AgentPrediction(
                    market="match_result",
                    outcome="Draw",
                    probability=0.30 + (h2h_draw_pct - 0.35) * 0.5,
                    confidence=0.45,
                    reasoning=f"H2H draw rate: {h2h_draw_pct:.0%} ({h2h_draws}/{total_h2h} draws)",
                ))

            h2h_btts = h2h.get("btts_percentage", 50)
            h2h_over25 = h2h.get("over_2_5_percentage", 50)
            if h2h_over25 > 65:
                predictions.append(AgentPrediction(
                    market="goals_over_under_2.5",
                    outcome="Over 2.5",
                    probability=min(0.70, h2h_over25 / 100),
                    confidence=0.40,
                    reasoning=f"H2H pattern: {h2h_over25:.0f}% over 2.5 in last {total_h2h} meetings",
                ))

        # === Overall ===
        overall_parts = []
        if derby_intensity: overall_parts.append(f"DERBY (intensity {derby_intensity}/3)")
        if home_motivation != "midtable": overall_parts.append(f"{home}: {home_motivation}")
        if away_motivation != "midtable": overall_parts.append(f"{away}: {away_motivation}")
        overall_parts.append(f"Home strength: {home_strength:+.1f}, Away strength: {away_strength:+.1f}")
        if total_h2h >= 3: overall_parts.append(f"H2H: {total_h2h} matches")

        overall = "Context: " + ". ".join(overall_parts) + "."

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.55,  # Context is supplementary
        )

    def _get_motivation(self, position, total_teams, league):
        if position is None:
            return "midtable"
        try:
            pos = int(position)
        except (TypeError, ValueError):
            return "midtable"

        if pos <= 2: return "title_race"
        if pos <= 4: return "cl_chase"  # UCL spots
        if pos <= 6: return "cl_chase"  # UEL spots
        if pos >= total_teams - 2: return "relegation_battle"
        if pos >= total_teams - 4: return "relegation_battle"
        if pos >= total_teams // 2 + 2: return "nothing_to_play_for"
        return "midtable"
