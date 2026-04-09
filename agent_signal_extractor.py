"""
Agent Signal Extractor — Pulls structured prediction signals from all 27 agent reports
and produces adjustment factors for goals, corners, cards, shots predictions.

This is the bridge between raw agent intelligence and the statistical models.
Instead of using league averages, predictions now incorporate:
- Attacking/defensive xG from agent analysis
- Injury impact on team strength
- Tactical matchup (pressing, possession, set pieces)
- Fatigue and rest days
- Referee tendencies (cards, penalties)
- Motivation/stakes levels
- Weather and venue effects
- Manager tactical tendencies
- Key player availability
- Momentum and form
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class MatchSignals:
    """Structured signals extracted from agent reports for prediction adjustment."""

    # --- Goals signals ---
    xg_home: float = 1.3  # Expected goals home (from attacking profile)
    xg_away: float = 1.1  # Expected goals away
    clean_sheet_prob_home: float = 0.3
    clean_sheet_prob_away: float = 0.25
    goal_scoring_impact: float = 1.0  # Weather impact on scoring
    first_goal_prob_home: float = 0.5
    first_goal_prob_away: float = 0.5
    motivation_home: float = 1.0  # Stakes multiplier
    motivation_away: float = 1.0

    # --- Injury/Squad signals ---
    home_injuries_count: int = 0
    away_injuries_count: int = 0
    home_available_count: int = 25
    away_available_count: int = 25
    home_top_scorers_goals: int = 0  # Combined goals from top 5 scorers
    away_top_scorers_goals: int = 0

    # --- Fatigue signals ---
    fatigue_home: float = 0.5  # 0=fresh, 1=exhausted
    fatigue_away: float = 0.5
    rest_days_home: int = 7
    rest_days_away: int = 7
    freshness_home: float = 0.5
    freshness_away: float = 0.5

    # --- Tactical signals ---
    tactical_edge: float = 0.0  # Positive = home advantage
    possession_prediction: float = 0.5  # Home expected possession
    pressing_winner: str = "neutral"  # home/away/neutral
    formation_clash_score: float = 1.0
    home_formation: str = "4-4-2"
    away_formation: str = "4-4-2"

    # --- Set piece signals ---
    set_piece_advantage: str = "neutral"
    corner_advantage_score: float = 0.0
    corner_goal_prob_home: float = 0.025
    corner_goal_prob_away: float = 0.025
    penalty_probability: float = 0.15
    free_kick_danger_home: float = 0.5
    free_kick_danger_away: float = 0.5

    # --- Cards signals ---
    referee_expected_yellows: float = 4.0
    referee_expected_reds: float = 0.15
    referee_strictness: int = 5  # 1-10
    card_adjustment_factor: float = 1.0
    rivalry_card_multiplier: float = 1.0
    rivalry_score: float = 0.0
    aggression_boost: float = 0.0

    # --- Venue/Weather signals ---
    home_advantage_modifier: float = 1.0
    pitch_factor: float = 1.0
    atmosphere_rating: int = 5
    travel_impact_away: float = 1.0
    weather_tempo_adjustment: float = 1.0
    wind_impact: float = 0.0

    # --- Momentum signals ---
    momentum_home: float = 0.5
    momentum_away: float = 0.5
    confidence_home: float = 0.5
    confidence_away: float = 0.5
    home_form_string: str = ""
    away_form_string: str = ""

    # --- Manager signals ---
    manager_advantage: str = "neutral"
    in_game_adjustment_home: int = 5
    in_game_adjustment_away: int = 5

    # --- Aggregated form predictions from original agents ---
    agent_goals_over25_votes: int = 0  # How many agents predict Over 2.5
    agent_goals_under25_votes: int = 0
    agent_corners_over85_votes: int = 0
    agent_corners_under85_votes: int = 0
    agent_corners_over95_votes: int = 0
    agent_corners_under95_votes: int = 0
    agent_btts_yes_votes: int = 0
    agent_btts_no_votes: int = 0
    agent_home_win_votes: int = 0
    agent_draw_votes: int = 0
    agent_away_win_votes: int = 0

    # --- Derived adjustments (computed after extraction) ---
    goals_adjustment: float = 0.0  # +/- to expected total goals
    corners_adjustment: float = 0.0  # +/- to expected corners
    cards_adjustment: float = 0.0  # +/- to expected cards
    shots_adjustment: float = 0.0  # +/- to expected shots
    adjustment_notes: List[str] = field(default_factory=list)


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def extract_signals(agent_reports: List[Any]) -> MatchSignals:
    """
    Extract structured signals from all agent reports.
    Works with both dict-style and object-style reports.
    """
    signals = MatchSignals()

    for report in (agent_reports or []):
        # Normalize to dict
        if hasattr(report, '__dict__') and not isinstance(report, dict):
            rpt = {
                "agent_name": getattr(report, 'agent_name', ''),
                "predictions": [],
            }
            for p in getattr(report, 'predictions', []):
                rpt["predictions"].append({
                    "market": getattr(p, 'market', ''),
                    "outcome": getattr(p, 'outcome', ''),
                    "confidence": getattr(p, 'confidence', 0),
                })
        elif isinstance(report, dict):
            rpt = report
        else:
            continue

        agent_name = rpt.get("agent_name", "").lower()
        preds = rpt.get("predictions", [])

        # Build a lookup dict for this agent's predictions
        pred_map = {}
        for p in preds:
            mkt = p.get("market", "")
            outcome = p.get("outcome", "")
            conf = _safe_float(p.get("confidence", 0))
            pred_map[mkt] = {"outcome": outcome, "confidence": conf}

            # Count votes for key markets (from original 6 agents)
            if mkt == "goals_over_under_2.5":
                if "Over" in str(outcome):
                    signals.agent_goals_over25_votes += 1
                elif "Under" in str(outcome):
                    signals.agent_goals_under25_votes += 1
            elif mkt == "corners_over_under_8.5":
                if "Over" in str(outcome):
                    signals.agent_corners_over85_votes += 1
                else:
                    signals.agent_corners_under85_votes += 1
            elif mkt == "corners_over_under_9.5":
                if "Over" in str(outcome):
                    signals.agent_corners_over95_votes += 1
                else:
                    signals.agent_corners_under95_votes += 1
            elif mkt == "btts":
                if str(outcome).lower() in ("yes", "true"):
                    signals.agent_btts_yes_votes += 1
                else:
                    signals.agent_btts_no_votes += 1
            elif mkt == "match_result":
                o = str(outcome).lower()
                if "draw" in o:
                    signals.agent_draw_votes += 1
                elif agent_name in ("formagent", "form_agent", "statsagent", "stats_agent"):
                    # First match_result prediction is their pick
                    signals.agent_home_win_votes += 1  # Simplified

        # --- Extract by agent type ---
        if "attacking" in agent_name:
            signals.xg_home = _safe_float(pred_map.get("xg_home", {}).get("outcome"), 1.3)
            signals.xg_away = _safe_float(pred_map.get("xg_away", {}).get("outcome"), 1.1)
            signals.first_goal_prob_home = _safe_float(
                pred_map.get("first_goal_prob_home", {}).get("outcome"), 0.5)
            signals.first_goal_prob_away = _safe_float(
                pred_map.get("first_goal_prob_away", {}).get("outcome"), 0.5)

        elif "defensive" in agent_name:
            signals.clean_sheet_prob_home = _safe_float(
                pred_map.get("clean_sheet_prob_home", {}).get("outcome"), 0.3)
            signals.clean_sheet_prob_away = _safe_float(
                pred_map.get("clean_sheet_prob_away", {}).get("outcome"), 0.25)

        elif "fatigue" in agent_name:
            signals.fatigue_home = _safe_float(
                pred_map.get("fatigue_level_home", {}).get("outcome"), 0.5)
            signals.fatigue_away = _safe_float(
                pred_map.get("fatigue_level_away", {}).get("outcome"), 0.5)
            signals.rest_days_home = _safe_int(
                pred_map.get("home_days_rest", {}).get("outcome"), 7)
            signals.rest_days_away = _safe_int(
                pred_map.get("away_days_rest", {}).get("outcome"), 7)

        elif "tactical" in agent_name and "set_piece" not in agent_name:
            signals.tactical_edge = _safe_float(
                pred_map.get("tactical_edge", {}).get("outcome"), 0.0)
            signals.possession_prediction = _safe_float(
                pred_map.get("possession_prediction", {}).get("outcome"), 0.5)
            signals.pressing_winner = str(
                pred_map.get("pressing_winner", {}).get("outcome", "neutral"))
            signals.formation_clash_score = _safe_float(
                pred_map.get("formation_clash_score", {}).get("outcome"), 1.0)
            # Extract formations
            ht = pred_map.get("home_tactics", {}).get("outcome", "")
            at = pred_map.get("away_tactics", {}).get("outcome", "")
            if isinstance(ht, dict):
                signals.home_formation = ht.get("formation", "4-4-2")
            elif isinstance(ht, str) and "formation" in ht:
                try:
                    import ast
                    d = ast.literal_eval(ht)
                    signals.home_formation = d.get("formation", "4-4-2")
                except:
                    pass
            if isinstance(at, dict):
                signals.away_formation = at.get("formation", "4-4-2")

        elif "set_piece" in agent_name:
            signals.set_piece_advantage = str(
                pred_map.get("set_piece_advantage", {}).get("outcome", "neutral"))
            signals.corner_advantage_score = _safe_float(
                pred_map.get("corner_advantage_score", {}).get("outcome"), 0.0)
            signals.corner_goal_prob_home = _safe_float(
                pred_map.get("corner_goal_prob_home", {}).get("outcome"), 0.025)
            signals.corner_goal_prob_away = _safe_float(
                pred_map.get("corner_goal_prob_away", {}).get("outcome"), 0.025)
            signals.penalty_probability = _safe_float(
                pred_map.get("penalty_probability", {}).get("outcome"), 0.15)
            signals.free_kick_danger_home = _safe_float(
                pred_map.get("free_kick_danger_home", {}).get("outcome"), 0.5)
            signals.free_kick_danger_away = _safe_float(
                pred_map.get("free_kick_danger_away", {}).get("outcome"), 0.5)

        elif "stakes" in agent_name:
            signals.motivation_home = _safe_float(
                pred_map.get("motivation_multiplier_home", {}).get("outcome"), 1.0)
            signals.motivation_away = _safe_float(
                pred_map.get("motivation_multiplier_away", {}).get("outcome"), 1.0)

        elif "rivalry" in agent_name:
            signals.rivalry_score = _safe_float(
                pred_map.get("rivalry_score", {}).get("outcome"), 0.0)
            signals.rivalry_card_multiplier = _safe_float(
                pred_map.get("card_multiplier", {}).get("outcome"), 1.0)
            signals.aggression_boost = _safe_float(
                pred_map.get("aggression_boost", {}).get("outcome"), 0.0)

        elif "referee" in agent_name:
            signals.referee_expected_yellows = _safe_float(
                pred_map.get("expected_yellows", {}).get("outcome"), 4.0)
            signals.referee_expected_reds = _safe_float(
                pred_map.get("expected_reds", {}).get("outcome"), 0.15)
            signals.referee_strictness = _safe_int(
                pred_map.get("referee_strictness", {}).get("outcome"), 5)
            signals.card_adjustment_factor = _safe_float(
                pred_map.get("card_adjustment_factor", {}).get("outcome"), 1.0)

        elif "venue" in agent_name:
            signals.home_advantage_modifier = _safe_float(
                pred_map.get("home_advantage_modifier", {}).get("outcome"), 1.0)
            signals.pitch_factor = _safe_float(
                pred_map.get("pitch_factor", {}).get("outcome"), 1.0)
            signals.atmosphere_rating = _safe_int(
                pred_map.get("atmosphere_rating", {}).get("outcome"), 5)
            signals.travel_impact_away = _safe_float(
                pred_map.get("travel_impact_away", {}).get("outcome"), 1.0)

        elif "weather" in agent_name:
            signals.goal_scoring_impact = _safe_float(
                pred_map.get("goal_scoring_impact", {}).get("outcome"), 1.0)
            signals.weather_tempo_adjustment = _safe_float(
                pred_map.get("tempo_adjustment", {}).get("outcome"), 1.0)
            signals.wind_impact = _safe_float(
                pred_map.get("wind_impact", {}).get("outcome"), 0.0)

        elif "momentum" in agent_name:
            signals.momentum_home = _safe_float(
                pred_map.get("momentum_home", {}).get("outcome"), 0.5)
            signals.momentum_away = _safe_float(
                pred_map.get("momentum_away", {}).get("outcome"), 0.5)
            signals.confidence_home = _safe_float(
                pred_map.get("confidence_rating_home", {}).get("outcome"), 0.5)
            signals.confidence_away = _safe_float(
                pred_map.get("confidence_rating_away", {}).get("outcome"), 0.5)

        elif "manager" in agent_name:
            signals.manager_advantage = str(
                pred_map.get("manager_advantage", {}).get("outcome", "neutral"))
            signals.in_game_adjustment_home = _safe_int(
                pred_map.get("in_game_adjustment_rating_home", {}).get("outcome"), 5)
            signals.in_game_adjustment_away = _safe_int(
                pred_map.get("in_game_adjustment_rating_away", {}).get("outcome"), 5)

        elif "lineup" in agent_name:
            signals.home_injuries_count = _safe_int(
                pred_map.get("home_injuries_count", {}).get("outcome"), 0)
            signals.away_injuries_count = _safe_int(
                pred_map.get("away_injuries_count", {}).get("outcome"), 0)
            signals.home_available_count = _safe_int(
                pred_map.get("home_available_count", {}).get("outcome"), 25)
            signals.away_available_count = _safe_int(
                pred_map.get("away_available_count", {}).get("outcome"), 25)

        elif "player_news" in agent_name:
            signals.home_top_scorers_goals = _safe_int(
                pred_map.get("home_total_goals_top5", {}).get("outcome"), 0)
            signals.away_top_scorers_goals = _safe_int(
                pred_map.get("away_total_goals_top5", {}).get("outcome"), 0)

        elif "rest" in agent_name:
            # rest_days_agent — use as backup if fatigue agent didn't have rest days
            if signals.rest_days_home == 7:
                signals.rest_days_home = _safe_int(
                    pred_map.get("rest_days_home", {}).get("outcome"), 7)
            if signals.rest_days_away == 7:
                signals.rest_days_away = _safe_int(
                    pred_map.get("rest_days_away", {}).get("outcome"), 7)
            signals.freshness_home = _safe_float(
                pred_map.get("freshness_home", {}).get("outcome"), 0.5)
            signals.freshness_away = _safe_float(
                pred_map.get("freshness_away", {}).get("outcome"), 0.5)

        elif "schedule" in agent_name:
            signals.home_form_string = str(
                pred_map.get("home_recent_form_all_comps", {}).get("outcome", ""))
            signals.away_form_string = str(
                pred_map.get("away_recent_form_all_comps", {}).get("outcome", ""))

    # --- Compute derived adjustments ---
    _compute_adjustments(signals)
    return signals


def _compute_adjustments(s: MatchSignals):
    """
    Compute adjustment factors based on extracted signals.
    These adjustments modify the base statistical predictions.
    """
    notes = []

    # ====== GOALS ADJUSTMENT ======
    goals_adj = 0.0

    # 1. Agent xG vs baseline (1.3 + 1.1 = 2.4 baseline)
    agent_xg_total = s.xg_home + s.xg_away
    if agent_xg_total > 0.5:  # Sanity check
        xg_diff = agent_xg_total - 2.4
        goals_adj += xg_diff * 0.4  # 40% weight — agent xG is informative but noisy
        if abs(xg_diff) > 0.3:
            notes.append(f"Agent xG: {agent_xg_total:.2f} ({xg_diff:+.2f} vs baseline)")

    # 2. Clean sheet probabilities signal fewer goals
    avg_cs = (s.clean_sheet_prob_home + s.clean_sheet_prob_away) / 2
    if avg_cs > 0.35:
        goals_adj -= (avg_cs - 0.35) * 1.5  # Strong defenses = fewer goals
        notes.append(f"Strong defenses: avg CS prob {avg_cs:.0%}")
    elif avg_cs < 0.2:
        goals_adj += (0.2 - avg_cs) * 1.0  # Weak defenses = more goals
        notes.append(f"Weak defenses: avg CS prob {avg_cs:.0%}")

    # 3. Injury impact — more injuries to a team = fewer goals scored by them
    if s.home_injuries_count >= 5:
        goals_adj -= 0.15  # Significant squad depletion
        notes.append(f"Home squad hit: {s.home_injuries_count} injuries")
    if s.away_injuries_count >= 5:
        goals_adj -= 0.15
        notes.append(f"Away squad hit: {s.away_injuries_count} injuries")

    # 4. Fatigue — tired teams concede more but score less; net effect is slightly more goals
    avg_fatigue = (s.fatigue_home + s.fatigue_away) / 2
    if avg_fatigue > 0.7:
        goals_adj += 0.2  # Tired teams = more open, more goals
        notes.append(f"High fatigue: {avg_fatigue:.2f}")
    elif avg_fatigue < 0.3:
        goals_adj -= 0.1  # Fresh teams = tighter, fewer goals

    # 5. Motivation — high-stakes = tighter games (fewer goals), low-stakes = open
    avg_motivation = (s.motivation_home + s.motivation_away) / 2
    if avg_motivation < 0.85:
        goals_adj += 0.15  # Dead rubber = open game
        notes.append("Low stakes: more open game")
    elif avg_motivation > 1.1:
        goals_adj -= 0.1  # High stakes = tight game

    # 6. Weather impact
    if s.goal_scoring_impact != 1.0:
        weather_adj = (s.goal_scoring_impact - 1.0) * 0.5
        goals_adj += weather_adj
        if abs(weather_adj) > 0.05:
            notes.append(f"Weather goal impact: {s.goal_scoring_impact:.2f}")

    # 7. Agent consensus on Over/Under 2.5
    o25_votes = s.agent_goals_over25_votes
    u25_votes = s.agent_goals_under25_votes
    if o25_votes + u25_votes > 0:
        consensus = o25_votes / (o25_votes + u25_votes)
        if consensus > 0.7:
            goals_adj += 0.2 * (consensus - 0.5)
            notes.append(f"Agent consensus: {o25_votes}/{o25_votes+u25_votes} say Over 2.5")
        elif consensus < 0.3:
            goals_adj -= 0.2 * (0.5 - consensus)
            notes.append(f"Agent consensus: {u25_votes}/{o25_votes+u25_votes} say Under 2.5")

    # 8. Top scorers firepower
    total_firepower = s.home_top_scorers_goals + s.away_top_scorers_goals
    if total_firepower > 35:
        goals_adj += 0.15
        notes.append(f"High firepower: {total_firepower} goals from top scorers")
    elif total_firepower < 15 and total_firepower > 0:
        goals_adj -= 0.1

    s.goals_adjustment = round(max(-1.0, min(1.0, goals_adj)), 3)

    # ====== CORNERS ADJUSTMENT ======
    corners_adj = 0.0

    # 1. Tactical setup — possession teams generate more corners
    if s.possession_prediction > 0.55:
        corners_adj += 0.5  # Dominant team creates more chances → corners
        notes.append(f"Possession dominance ({s.possession_prediction:.0%}): +corners")
    elif s.possession_prediction < 0.45:
        corners_adj += 0.3  # Counter-attacking also generates corners from blocks

    # 2. Set piece advantage signals corner proficiency
    if s.set_piece_advantage == "home" or s.corner_advantage_score > 0.3:
        corners_adj += 0.5
        notes.append(f"Set piece advantage: home (+corners)")
    elif s.set_piece_advantage == "away" or s.corner_advantage_score < -0.3:
        corners_adj += 0.3

    # 3. High pressing → more shots → more corners (from blocked shots)
    if s.pressing_winner != "neutral":
        corners_adj += 0.3
        notes.append(f"Pressing intensity: +corners")

    # 4. Formation impact — attacking formations generate more corners
    for formation in [s.home_formation, s.away_formation]:
        if formation in ("4-3-3", "3-4-3", "3-5-2"):
            corners_adj += 0.2  # Attacking formations

    # 5. Weather — wind increases corners (from deflections, misjudged crosses)
    if s.wind_impact > 0.3:
        corners_adj += 0.5
        notes.append(f"Wind impact on corners: +{s.wind_impact:.1f}")

    # 6. Agent corner votes
    over85 = s.agent_corners_over85_votes
    under85 = s.agent_corners_under85_votes
    if over85 + under85 > 0:
        c_consensus = over85 / (over85 + under85)
        if c_consensus > 0.6:
            corners_adj += 0.5
        elif c_consensus < 0.4:
            corners_adj -= 0.5

    # 7. Corner goal probability signals set piece quality
    avg_corner_goal = (s.corner_goal_prob_home + s.corner_goal_prob_away) / 2
    if avg_corner_goal > 0.04:
        corners_adj += 0.3  # Good at corners = win more

    s.corners_adjustment = round(max(-2.0, min(2.0, corners_adj)), 2)

    # ====== CARDS ADJUSTMENT ======
    cards_adj = 0.0

    # 1. Referee is the #1 factor — their personal average
    ref_yellows = s.referee_expected_yellows
    if ref_yellows > 5.0:
        cards_adj += (ref_yellows - 4.5) * 0.4
        notes.append(f"Strict referee: {ref_yellows:.1f} avg yellows")
    elif ref_yellows < 3.5:
        cards_adj -= (4.0 - ref_yellows) * 0.3
        notes.append(f"Lenient referee: {ref_yellows:.1f} avg yellows")

    # 2. Card adjustment factor from referee agent
    if s.card_adjustment_factor != 1.0:
        cards_adj += (s.card_adjustment_factor - 1.0) * 2.0

    # 3. Rivalry intensity → more fouls → more cards
    if s.rivalry_score > 0.5:
        cards_adj += s.rivalry_score * 1.5
        notes.append(f"Rivalry ({s.rivalry_score:.1f}): +cards")
    if s.rivalry_card_multiplier > 1.0:
        cards_adj += (s.rivalry_card_multiplier - 1.0) * 2.0

    # 4. Stakes — high-stakes matches have more tactical fouls
    avg_mot = (s.motivation_home + s.motivation_away) / 2
    if avg_mot > 1.05:
        cards_adj += 0.3
        notes.append("High stakes: +tactical fouls")

    # 5. Tactical aggression — pressing teams commit more fouls
    if s.pressing_winner != "neutral":
        cards_adj += 0.2

    # 6. Fatigue → more fouls (late tackles, poor timing)
    if avg_fatigue > 0.6:
        cards_adj += 0.3
        notes.append("Fatigue: more late challenges")

    s.cards_adjustment = round(max(-3.0, min(3.0, cards_adj)), 2)

    # ====== SHOTS ADJUSTMENT ======
    shots_adj = 0.0

    # 1. xG directly correlates with shots (more xG = more quality chances)
    if agent_xg_total > 2.8:
        shots_adj += (agent_xg_total - 2.4) * 2.0
        notes.append(f"High xG ({agent_xg_total:.1f}): +shots")
    elif agent_xg_total < 2.0 and agent_xg_total > 0.5:
        shots_adj -= (2.4 - agent_xg_total) * 1.5

    # 2. Possession → more time on ball → more shots
    if s.possession_prediction > 0.55:
        shots_adj += 1.0
    elif s.possession_prediction < 0.45:
        shots_adj -= 0.5

    # 3. Tactical pressing = more turnovers = more shot opportunities
    if s.pressing_winner != "neutral":
        shots_adj += 0.5

    # 4. Weather tempo
    if s.weather_tempo_adjustment != 1.0:
        shots_adj += (s.weather_tempo_adjustment - 1.0) * 3.0

    s.shots_adjustment = round(max(-4.0, min(4.0, shots_adj)), 2)

    s.adjustment_notes = notes
