"""
Stats Agent V3 — Full V4 engine integration.

Upgrades over V2:
1. Empirical match stats model (4,888 matches) for corners/cards/fouls
2. V4 calibration (linear shrinkage 35%) for all probabilities
3. Shot→corner chains, foul→card chains from real data
4. Position matchup adjustments from empirical data
5. Match profile classification
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from scipy.stats import poisson
from .base_agent import BaseAgent, AgentReport, AgentPrediction
from models.dixon_coles import (
    dixon_coles_match_probs, prob_over_goals, prob_btts, prob_first_half_goals_over,
    prob_double_chance, prob_clean_sheet,
    EloRating, strength_adjusted_xg,
    referee_adjusted_cards, KNOWN_REFEREES,
    corners_model, time_decay_weight,
)
from models.match_stats_model import (
    predict_match_stats, calibrate_match_probs, calibrate_probability,
    BASE_RATES, LEAGUE_STAT_BASELINES, STAT_CORRELATIONS,
    RESULT_STAT_RATIOS, MATCH_PROFILES, MatchStatsPrediction,
)

_elo_system = EloRating()
_elo_initialized = False


def get_elo_system() -> EloRating:
    """Get or initialize the global Elo rating system."""
    global _elo_system, _elo_initialized
    if not _elo_initialized:
        _elo_system.initialize_top5_defaults()
        _elo_initialized = True
    return _elo_system


class StatsAgentV3(BaseAgent):
    """
    Stats Agent V3: Full integration of Dixon-Coles, Elo ratings,
    and empirical match stats model (4,888 matches).

    Key features:
    - V4 calibration (35% linear shrinkage toward base rates)
    - Empirical match stats predictions (corners, cards, fouls, shots)
    - Backtest-validated correlations (shots↔corners r=-0.02, SOT↔goals r=+0.56)
    - Match profile classification (low_scoring, average, moderate, high_scoring, thriller)
    - Derby detection with card adjustment (+8%)
    """

    name = "StatsAgent"
    specialty = "Dixon-Coles + Elo + Match Stats Model (V3, 4,888 matches)"
    weight = 1.4  # Slightly higher weight than V2

    def __init__(self):
        """Initialize with Elo system."""
        self.elo = get_elo_system()
        self._last_stats = None

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats) -> AgentReport:
        """
        Analyze a match using Dixon-Coles, Elo, and empirical match stats.

        Args:
            match_data: Dict with id, home_team, away_team, league, referee
            home_form: Form data for home team
            away_form: Form data for away team
            h2h: Head-to-head history
            home_stats: Home team statistics (xG, goals, shots, fouls, etc.)
            away_stats: Away team statistics

        Returns:
            AgentReport with predictions across all markets
        """
        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        league = match_data.get("league", "Premier League")
        referee = match_data.get("referee", None)

        # === STEP 1: xG / Goals data ===
        has_xg = home_stats.get("has_xg_data", False) and away_stats.get("has_xg_data", False)
        if has_xg:
            home_attack_raw = home_stats["home_xg_avg"] * 0.6 + home_stats["recent_xg_avg"] * 0.4
            home_defense_raw = home_stats["home_xga_avg"] * 0.6 + home_stats["recent_xga_avg"] * 0.4
            away_attack_raw = away_stats["away_xg_avg"] * 0.6 + away_stats["recent_xg_avg"] * 0.4
            away_defense_raw = away_stats["away_xga_avg"] * 0.6 + away_stats["recent_xga_avg"] * 0.4
            data_source = "xG"
        else:
            home_attack_raw = home_stats.get("home_goals_avg", 1.3)
            home_defense_raw = home_stats.get("home_conceded_avg", 0.9)
            away_attack_raw = away_stats.get("away_goals_avg", 1.0)
            away_defense_raw = away_stats.get("away_conceded_avg", 1.3)
            data_source = "actual goals"

        # Elo-adjusted xG
        home_exp, away_exp = strength_adjusted_xg(
            home_attack=home_attack_raw,
            home_defense=home_defense_raw,
            away_attack=away_attack_raw,
            away_defense=away_defense_raw,
            elo_system=self.elo,
            home_team=home,
            away_team=away,
        )
        total_expected = home_exp + away_exp
        expected_gd = home_exp - away_exp

        # === STEP 2: Dixon-Coles probabilities ===
        dc_probs = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)
        elo_pred = self.elo.predict_match(home, away)

        # Blend DC + Elo (60/40)
        blend_hw = dc_probs['home_win'] * 0.6 + elo_pred['home_win'] * 0.4
        blend_dw = dc_probs['draw'] * 0.6 + elo_pred['draw'] * 0.4
        blend_aw = dc_probs['away_win'] * 0.6 + elo_pred['away_win'] * 0.4
        total = blend_hw + blend_dw + blend_aw
        blend_hw /= total
        blend_dw /= total
        blend_aw /= total

        # === STEP 3: V4 CALIBRATION (shrinkage) ===
        cal = calibrate_match_probs(blend_hw, blend_dw, blend_aw)
        cal_hw = cal["home_win"]
        cal_dw = cal["draw"]
        cal_aw = cal["away_win"]

        # Match result prediction (calibrated)
        best = max(cal_hw, cal_dw, cal_aw)
        if cal_hw == best:
            mr_outcome = f"{home} Win"
        elif cal_dw == best:
            mr_outcome = "Draw"
        else:
            mr_outcome = f"{away} Win"

        predictions.append(AgentPrediction(
            market="match_result",
            outcome=mr_outcome,
            probability=self._clamp(best),
            confidence=self._prob_confidence(best, 0.76),
            reasoning=(
                f"V4 Calibrated: P({home})={cal_hw:.1%}, P(Draw)={cal_dw:.1%}, "
                f"P({away})={cal_aw:.1%} [shrinkage 35%]"
            ),
            data_points=[
                f"Raw DC+Elo: {blend_hw:.1%}/{blend_dw:.1%}/{blend_aw:.1%}",
                f"Calibrated: {cal_hw:.1%}/{cal_dw:.1%}/{cal_aw:.1%}",
                f"Elo: {self.elo.get_rating(home):.0f} vs {self.elo.get_rating(away):.0f}",
            ]
        ))

        # === STEP 4: Goals markets (calibrated) ===
        for line in [1.5, 2.5, 3.5]:
            over_prob = prob_over_goals(dc_probs, line)
            # Calibrate goals over/under
            if line == 2.5:
                over_prob = calibrate_probability(over_prob, BASE_RATES["over_25"])
            better_side = "Over" if over_prob > 0.5 else "Under"
            prob_val = max(over_prob, 1 - over_prob)
            predictions.append(AgentPrediction(
                market=f"goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(prob_val),
                confidence=self._prob_confidence(prob_val, 0.74),
                reasoning=(
                    f"DC xG: {home} {home_exp:.2f}, {away} {away_exp:.2f}, "
                    f"total {total_expected:.2f} [{data_source}]"
                ),
                data_points=[
                    f"Elo-adjusted, DC rho=-0.13, calibrated" if line == 2.5
                    else f"DC model"
                ],
            ))

        # BTTS
        btts_prob = prob_btts(dc_probs)
        predictions.append(AgentPrediction(
            market="btts",
            outcome="Yes" if btts_prob > 0.5 else "No",
            probability=self._clamp(max(btts_prob, 1 - btts_prob)),
            confidence=0.72,
            reasoning=f"DC BTTS: {btts_prob:.1%} (score-correlation corrected)",
        ))

        # Double Chance
        dc_chances = prob_double_chance(dc_probs)
        for label, pv in dc_chances.items():
            if pv > 0.65:
                predictions.append(AgentPrediction(
                    market="double_chance",
                    outcome=label,
                    probability=self._clamp(pv),
                    confidence=0.68,
                    reasoning=f"Double chance {label}: {pv:.1%}",
                ))

        # First Half Goals
        for line in [0.5, 1.5]:
            fh_over = prob_first_half_goals_over(home_exp, away_exp, line)
            better = "Over" if fh_over > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"first_half_goals_over_under_{line}",
                outcome=f"{better} {line}",
                probability=self._clamp(max(fh_over, 1 - fh_over)),
                confidence=0.62,
                reasoning="FH DC: 42% of goals in first half",
            ))

        # === STEP 5: Match Stats Model (4,888 matches empirical data) ===
        home_shots_avg = home_stats.get("avg_shots_on_target", 4.5) * 2  # SoT to total shots
        away_shots_avg = away_stats.get("avg_shots_on_target", 4.0) * 2
        home_fouls_avg = home_stats.get("avg_fouls", 12.0)
        away_fouls_avg = away_stats.get("avg_fouls", 12.0)
        home_pos = home_stats.get("league_position")
        away_pos = away_stats.get("league_position")

        # Convert position strings to ints if needed
        if isinstance(home_pos, str):
            try:
                home_pos = int(home_pos)
            except (ValueError, TypeError):
                home_pos = None
        if isinstance(away_pos, str):
            try:
                away_pos = int(away_pos)
            except (ValueError, TypeError):
                away_pos = None

        match_stats = predict_match_stats(
            league=league,
            home_shots_avg=home_shots_avg,
            away_shots_avg=away_shots_avg,
            home_fouls_avg=home_fouls_avg,
            away_fouls_avg=away_fouls_avg,
            home_position=home_pos,
            away_position=away_pos,
            expected_goals=total_expected,
            expected_gd=expected_gd,
        )

        # Store for engine access
        self._last_stats = match_stats

        # Corner markets from empirical model
        for line, over_prob in match_stats.corner_ou.items():
            better = "Over" if over_prob > 0.5 else "Under"
            data_points = [
                f"Shot chain: {home_shots_avg:.0f}+{away_shots_avg:.0f} shots→{match_stats.corners:.1f} corners",
                f"Corner/goals correlation: r=-0.02 (independent!)",
            ]
            if match_stats.notes:
                data_points.extend(match_stats.notes[:2])

            predictions.append(AgentPrediction(
                market=f"corners_over_under_{line}",
                outcome=f"{better} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.68,  # Higher than V2 — empirical data
                reasoning=(
                    f"Empirical model: {match_stats.corners:.1f} corners expected "
                    f"({match_stats.expected_profile})"
                ),
                data_points=data_points,
            ))

        # Card markets from empirical model
        is_derby = self._is_derby(home, away)
        for line, over_prob in match_stats.card_ou.items():
            derby_adj = 1.08 if is_derby else 1.0  # 8% more cards in derbies
            adj_prob = min(0.95, over_prob * derby_adj)
            better = "Over" if adj_prob > 0.5 else "Under"
            derby_tag = " [DERBY]" if is_derby else ""

            data_points = [
                f"Foul chain: {home_fouls_avg:.0f}+{away_fouls_avg:.0f} fouls→{match_stats.cards:.1f} cards",
            ]
            if abs(expected_gd) < 1:
                data_points.append("Tight match → +10-15% more cards")
            else:
                data_points.append(f"Expected GD {expected_gd:.1f}")

            predictions.append(AgentPrediction(
                market=f"cards_over_under_{line}",
                outcome=f"{better} {line}",
                probability=self._clamp(max(adj_prob, 1 - adj_prob)),
                confidence=0.66 + (0.04 if is_derby else 0),
                reasoning=(
                    f"Empirical: {match_stats.cards:.1f} cards "
                    f"(fouls→cards r=+0.38){derby_tag}"
                ),
                data_points=data_points,
            ))

        # SOT markets from empirical model
        for line in [4.5, 5.5, 6.5, 7.5, 8.5]:
            over_prob = 1 - poisson.cdf(int(line), match_stats.sot)
            better = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"shots_on_target_over_under_{line}",
                outcome=f"{better} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.60,
                reasoning=f"SOT model: {match_stats.sot:.1f} expected (SOT→goals r=+0.56)",
            ))

        # === Overall assessment ===
        overall = (
            f"V3 Stats [{data_source}]: "
            f"{home} xG={home_exp:.2f} (Elo {self.elo.get_rating(home):.0f}), "
            f"{away} xG={away_exp:.2f} (Elo {self.elo.get_rating(away):.0f}). "
            f"V4 Cal: {cal_hw:.0%}/{cal_dw:.0%}/{cal_aw:.0%}. "
            f"Stats: {match_stats.corners:.0f} corners, {match_stats.cards:.1f} cards, "
            f"{match_stats.shots:.0f} shots, {match_stats.sot:.0f} SOT. "
            f"Profile: {match_stats.expected_profile}."
        )

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home,
            away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=0.85 if has_xg else 0.82,
        )

    @property
    def last_match_stats(self):
        """Access the last computed match stats for engine integration."""
        return self._last_stats

    def _clamp(self, prob: float) -> float:
        """Clamp probability to valid range [0.01, 0.99]."""
        return max(0.01, min(0.99, prob))

    def _prob_confidence(self, prob: float, base_conf: float) -> float:
        """
        Adjust confidence based on probability distance from 50%.

        Args:
            prob: Probability value
            base_conf: Base confidence level

        Returns:
            Adjusted confidence
        """
        if prob > 0.92:
            return base_conf * 0.5
        elif prob > 0.80:
            return base_conf * 0.7
        elif prob > 0.65:
            return base_conf * 0.9
        return base_conf

    def _is_derby(self, home: str, away: str) -> bool:
        """
        Check if this is a known derby match.

        Args:
            home: Home team name
            away: Away team name

        Returns:
            True if it's a derby, False otherwise
        """
        derbies = [
            {"Arsenal", "Tottenham"},
            {"Liverpool", "Everton"},
            {"Manchester City", "Manchester United"},
            {"Man City", "Man United"},
            {"Chelsea", "Fulham"},
            {"Chelsea", "Arsenal"},
            {"Real Madrid", "Atletico Madrid"},
            {"Real Madrid", "Barcelona"},
            {"Barcelona", "Espanyol"},
            {"Sevilla", "Betis"},
            {"Bayern Munich", "Borussia Dortmund"},
            {"Bayern Munich", "Dortmund"},
            {"Inter Milan", "AC Milan"},
            {"Inter", "AC Milan"},
            {"Roma", "Lazio"},
            {"Juventus", "Inter Milan"},
            {"Juventus", "Inter"},
            {"Napoli", "Roma"},
            {"Napoli", "Juventus"},
            {"Paris Saint-Germain", "Marseille"},
            {"PSG", "Marseille"},
            {"Lyon", "Saint-Etienne"},
            {"Monaco", "Nice"},
            {"Lille", "Lens"},
        ]
        pair = {home, away}
        return any(pair == d for d in derbies)
