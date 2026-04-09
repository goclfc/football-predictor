"""
Stats Agent V2 — Upgraded with Dixon-Coles model, Elo ratings, and
referee-aware card predictions.

Improvements over V1:
1. Dixon-Coles instead of independent Poisson (corrects low-score correlation)
2. Elo-based opponent strength adjustment
3. Time-weighted form data (recent matches matter more)
4. Referee-adjusted card predictions
5. Corners model using attacking intensity, not just averages
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


# Shared Elo system (persists across matches in same session)
_elo_system = EloRating()
_elo_initialized = False


def get_elo_system() -> EloRating:
    global _elo_system, _elo_initialized
    if not _elo_initialized:
        _elo_system.initialize_top5_defaults()
        _elo_initialized = True
    return _elo_system


class StatsAgentV2(BaseAgent):
    name = "StatsAgent"  # Same name so meta_agent weights still apply
    specialty = "Dixon-Coles Statistical Models + Elo"
    weight = 1.3

    def __init__(self):
        self.elo = get_elo_system()

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict) -> AgentReport:

        predictions = []
        home = match_data["home_team"]
        away = match_data["away_team"]
        referee = match_data.get("referee", None)

        # ─── STEP 1: Elo-adjusted expected goals ───────────────────
        # USE xG DATA when available (much more predictive than actual goals)
        has_xg = home_stats.get("has_xg_data", False) and away_stats.get("has_xg_data", False)

        if has_xg:
            # Use xG (expected goals) — this is THE key upgrade
            # Blend season-long xG with recent 5-match xG (60/40)
            home_attack_raw = (
                home_stats["home_xg_avg"] * 0.6 +
                home_stats["recent_xg_avg"] * 0.4
            )
            home_defense_raw = (
                home_stats["home_xga_avg"] * 0.6 +
                home_stats["recent_xga_avg"] * 0.4
            )
            away_attack_raw = (
                away_stats["away_xg_avg"] * 0.6 +
                away_stats["recent_xg_avg"] * 0.4
            )
            away_defense_raw = (
                away_stats["away_xga_avg"] * 0.6 +
                away_stats["recent_xga_avg"] * 0.4
            )
            data_source = "xG (Understat)"
        else:
            # Fallback to actual goals
            home_attack_raw = home_stats["home_goals_avg"]
            home_defense_raw = home_stats["home_conceded_avg"]
            away_attack_raw = away_stats["away_goals_avg"]
            away_defense_raw = away_stats["away_conceded_avg"]
            data_source = "actual goals"

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

        # ─── STEP 2: Dixon-Coles match probabilities ──────────────
        dc_probs = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)

        # ─── GOALS MARKETS ─────────────────────────────────────────
        for line in [1.5, 2.5, 3.5]:
            over_prob = prob_over_goals(dc_probs, line)
            better_side = "Over" if over_prob > 0.5 else "Under"
            prob_val = max(over_prob, 1 - over_prob)
            predictions.append(AgentPrediction(
                market=f"goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(prob_val),
                confidence=self._prob_confidence(prob_val, 0.74),
                reasoning=(
                    f"Dixon-Coles: {home} xG {home_exp:.2f}, {away} xG {away_exp:.2f} "
                    f"(Elo: {self.elo.get_rating(home):.0f} vs {self.elo.get_rating(away):.0f}) "
                    f"[source: {data_source}]"
                ),
                data_points=[
                    f"Elo-adjusted xG: home={home_exp:.2f}, away={away_exp:.2f}",
                    f"Data source: {data_source}",
                    f"DC rho=-0.13 (low-score correlation correction)",
                ]
            ))

        # ─── MATCH RESULT (from Dixon-Coles) ──────────────────────
        hw = dc_probs['home_win']
        dw = dc_probs['draw']
        aw = dc_probs['away_win']

        # Also get Elo prediction for comparison
        elo_pred = self.elo.predict_match(home, away)

        # Blend DC + Elo (60/40 — DC is more precise but Elo captures long-term form)
        blend_hw = hw * 0.6 + elo_pred['home_win'] * 0.4
        blend_dw = dw * 0.6 + elo_pred['draw'] * 0.4
        blend_aw = aw * 0.6 + elo_pred['away_win'] * 0.4

        # Normalize
        total = blend_hw + blend_dw + blend_aw
        blend_hw /= total
        blend_dw /= total
        blend_aw /= total

        best = max(blend_hw, blend_dw, blend_aw)
        if blend_hw == best:
            mr_outcome = f"{home} Win"
        elif blend_dw == best:
            mr_outcome = "Draw"
        else:
            mr_outcome = f"{away} Win"

        predictions.append(AgentPrediction(
            market="match_result",
            outcome=mr_outcome,
            probability=self._clamp(best),
            confidence=self._prob_confidence(best, 0.70),
            reasoning=(
                f"DC+Elo blend: P({home})={blend_hw:.1%}, P(Draw)={blend_dw:.1%}, "
                f"P({away})={blend_aw:.1%}"
            ),
            data_points=[
                f"Dixon-Coles: {hw:.1%}/{dw:.1%}/{aw:.1%}",
                f"Elo model: {elo_pred['home_win']:.1%}/{elo_pred['draw']:.1%}/{elo_pred['away_win']:.1%}",
            ]
        ))

        # ─── BTTS (from Dixon-Coles — much more accurate than independent Poisson) ──
        btts_prob = prob_btts(dc_probs)
        predictions.append(AgentPrediction(
            market="btts",
            outcome="Yes" if btts_prob > 0.5 else "No",
            probability=self._clamp(max(btts_prob, 1 - btts_prob)),
            confidence=0.72,
            reasoning=(
                f"Dixon-Coles BTTS: {btts_prob:.1%} "
                f"(corrected for score correlation, not just independent P(score>0))"
            ),
        ))

        # ─── DOUBLE CHANCE ────────────────────────────────────────
        dc_chances = prob_double_chance(dc_probs)
        for label, prob_val in dc_chances.items():
            if prob_val > 0.65:  # Only predict strong double chances
                predictions.append(AgentPrediction(
                    market="double_chance",
                    outcome=label,
                    probability=self._clamp(prob_val),
                    confidence=0.68,
                    reasoning=f"Double chance {label}: {prob_val:.1%} from Dixon-Coles",
                ))

        # ─── CORNERS (using dedicated corners model) ──────────────
        # Prefer REAL corner stats from football-data.co.uk when available
        home_corners_avg = home_stats.get("real_corners_for_avg",
                                           home_stats.get("home_corners_avg", 5.0))
        away_corners_avg = away_stats.get("real_corners_for_avg",
                                           away_stats.get("away_corners_avg", 4.5))
        home_shots = home_stats.get("avg_shots_on_target", 4.5)
        away_shots = away_stats.get("avg_shots_on_target", 4.0)

        # Get attack strength from Elo
        home_attack_str = self.elo.team_strength_ratio(home, away)
        away_attack_str = self.elo.team_strength_ratio(away, home)

        total_corners_exp = corners_model(
            home_possession=55.0,  # TODO: get real possession data
            away_possession=45.0,
            home_shots_avg=home_shots * 2,  # Convert SoT to total shots (approx)
            away_shots_avg=away_shots * 2,
            home_corners_avg=home_corners_avg,
            away_corners_avg=away_corners_avg,
            home_attack_strength=home_attack_str,
            away_attack_strength=away_attack_str,
        )

        for line in [8.5, 9.5, 10.5, 11.5]:
            over_prob = 1 - poisson.cdf(int(line), total_corners_exp)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"corners_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.66,
                reasoning=(
                    f"Corners model: exp {total_corners_exp:.1f} "
                    f"(attack intensity + shot volume adjusted)"
                ),
                data_points=[
                    f"Base: {home} {home_corners_avg:.1f} + {away} {away_corners_avg:.1f}",
                    f"Attack strength: {home_attack_str:.2f} / {away_attack_str:.2f}",
                ]
            ))

        # Corner dominance
        if abs(home_corners_avg - away_corners_avg) > 0.8:
            dominant = home if home_corners_avg > away_corners_avg else away
            dom_prob = self._clamp(
                max(home_corners_avg, away_corners_avg) /
                (home_corners_avg + away_corners_avg) + 0.03
            )
            predictions.append(AgentPrediction(
                market="corners_home_away",
                outcome=f"{dominant} More Corners",
                probability=dom_prob,
                confidence=0.58,
                reasoning=f"Corner avg: {home} {home_corners_avg:.1f} vs {away} {away_corners_avg:.1f}",
            ))

        # ─── CARDS (referee-adjusted) ─────────────────────────────
        base_cards = home_stats.get("home_cards_avg", 2.0) + away_stats.get("away_cards_avg", 2.3)

        # Check if this is a derby/rivalry
        is_derby = self._is_derby(home, away)

        adjusted_cards = referee_adjusted_cards(
            base_cards_expected=base_cards,
            referee_name=referee,
            is_derby=is_derby,
        )

        for line in [3.5, 4.5, 5.5]:
            over_prob = 1 - poisson.cdf(int(line), adjusted_cards)
            better_side = "Over" if over_prob > 0.5 else "Under"
            ref_note = f" (ref: {referee})" if referee else ""
            derby_note = " [DERBY]" if is_derby else ""
            predictions.append(AgentPrediction(
                market=f"cards_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.64 + (0.06 if referee else 0),  # Higher confidence with referee data
                reasoning=(
                    f"Cards model: exp {adjusted_cards:.1f}{ref_note}{derby_note} "
                    f"(base {base_cards:.1f}, referee-adjusted)"
                ),
                data_points=[
                    f"Base team cards: {base_cards:.1f}",
                    f"Referee profile: {KNOWN_REFEREES.get(referee, 'unknown') if referee else 'no data'}",
                ]
            ))

        # ─── SHOTS ON TARGET ──────────────────────────────────────
        total_sot = home_shots + away_shots
        for line in [4.5, 5.5, 6.5]:
            over_prob = 1 - poisson.cdf(int(line), total_sot)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"shots_on_target_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.58,
                reasoning=f"SoT: {home} {home_shots:.1f}, {away} {away_shots:.1f}, total {total_sot:.1f}",
            ))

        # ─── FIRST HALF GOALS (Dixon-Coles for first half) ───────
        for line in [0.5, 1.5]:
            fh_over = prob_first_half_goals_over(home_exp, away_exp, line)
            better_side = "Over" if fh_over > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"first_half_goals_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(fh_over, 1 - fh_over)),
                confidence=0.62,
                reasoning=f"FH Dixon-Coles: 42% of goals in first half, adjusted for low-score correlation",
            ))

        # ─── THROW-INS ───────────────────────────────────────────
        home_ti = home_stats.get("avg_throw_ins", 22)
        away_ti = away_stats.get("avg_throw_ins", 22)
        total_ti = home_ti + away_ti
        for line in [21.5, 23.5, 25.5]:
            diff = total_ti - line
            over_prob = self._clamp(0.5 + diff * 0.06)
            better_side = "Over" if over_prob > 0.5 else "Under"
            predictions.append(AgentPrediction(
                market=f"throwins_over_under_{line}",
                outcome=f"{better_side} {line}",
                probability=self._clamp(max(over_prob, 1 - over_prob)),
                confidence=0.42,  # Low confidence — throw-in data is mostly defaults
                reasoning=f"Throw-ins: {total_ti:.1f} expected (low confidence — limited data)",
            ))

        # ─── CONTEXT ADJUSTMENTS (motivation, PPDA) ────────────────
        home_motivation = home_stats.get("motivation_context", "unknown")
        away_motivation = away_stats.get("motivation_context", "unknown")
        home_ppda = home_stats.get("ppda", 0)
        away_ppda = away_stats.get("ppda", 0)

        # PPDA-based pressing intensity note (affects card and foul predictions)
        if home_ppda > 0 and away_ppda > 0:
            pressing_note = (
                f"Pressing: {home} PPDA={home_ppda:.1f} "
                f"({'high press' if home_ppda < 9 else 'medium' if home_ppda < 12 else 'low block'}), "
                f"{away} PPDA={away_ppda:.1f} "
                f"({'high press' if away_ppda < 9 else 'medium' if away_ppda < 12 else 'low block'})"
            )
        else:
            pressing_note = ""

        # xG overperformance warning (teams outperforming xG are due for regression)
        home_overperf = home_stats.get("xg_overperformance", 0)
        away_overperf = away_stats.get("xg_overperformance", 0)
        regression_note = ""
        if abs(home_overperf) > 0.2:
            regression_note += f" {home} {'over' if home_overperf > 0 else 'under'}performing xG by {home_overperf:+.2f} goals/match."
        if abs(away_overperf) > 0.2:
            regression_note += f" {away} {'over' if away_overperf > 0 else 'under'}performing xG by {away_overperf:+.2f} goals/match."

        # ─── Overall assessment ──────────────────────────────────
        overall = (
            f"Dixon-Coles V2 [{data_source}]: "
            f"{home} xG={home_exp:.2f} (Elo {self.elo.get_rating(home):.0f}, pos {home_stats.get('league_position', '?')}), "
            f"{away} xG={away_exp:.2f} (Elo {self.elo.get_rating(away):.0f}, pos {away_stats.get('league_position', '?')}). "
            f"Match: {blend_hw:.0%}/{blend_dw:.0%}/{blend_aw:.0%}. "
            f"Exp {total_expected:.1f} goals, {total_corners_exp:.1f} corners, "
            f"{adjusted_cards:.1f} cards{' (ref-adjusted)' if referee else ''}."
            f"{' ' + pressing_note if pressing_note else ''}"
            f"{regression_note}"
        )

        # Higher reliability when using xG data
        reliability = 0.85 if has_xg else 0.80

        return AgentReport(
            agent_name=self.name,
            match_id=match_data["id"],
            home_team=home, away_team=away,
            predictions=predictions,
            overall_assessment=overall,
            reliability_score=reliability
        )

    def _prob_confidence(self, prob: float, base_confidence: float) -> float:
        """Scale confidence based on probability extremeness."""
        if prob > 0.92:
            return base_confidence * 0.5
        elif prob > 0.80:
            return base_confidence * 0.7
        elif prob > 0.65:
            return base_confidence * 0.9
        else:
            return base_confidence

    def _is_derby(self, home: str, away: str) -> bool:
        """Check if this is a local derby or major rivalry."""
        derbies = [
            {"Arsenal", "Tottenham"}, {"Liverpool", "Everton"},
            {"Manchester City", "Manchester United"}, {"Chelsea", "Fulham"},
            {"Real Madrid", "Atletico Madrid"}, {"Real Madrid", "Barcelona"},
            {"Barcelona", "Espanyol"}, {"Sevilla", "Betis"},
            {"Bayern Munich", "Borussia Dortmund"},
            {"Inter Milan", "AC Milan"}, {"Roma", "Lazio"},
            {"Juventus", "Inter Milan"}, {"Napoli", "Roma"},
            {"Paris Saint-Germain", "Marseille"}, {"Lyon", "Saint-Etienne"},
            {"Monaco", "Nice"}, {"Lille", "Lens"},
        ]
        pair = {home, away}
        return any(pair == d for d in derbies)
