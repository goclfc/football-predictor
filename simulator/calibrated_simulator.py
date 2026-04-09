"""
Calibrated Match Simulator — Anchored to V5 predictions.

Instead of generating goals as random events each minute (which produces
unrealistic 4-2, 1-6 scorelines), this simulator:

1. Pre-determines outcomes from V5 calibrated expected goals using Poisson sampling
2. Pre-determines corners, cards, shots from agent-informed model
3. Places events at realistic minutes using empirical timing distributions
4. Generates commentary/narrative around the predetermined events

This means the simulation CONFIRMS the prediction rather than contradicting it.
Monte Carlo runs produce outcome distributions consistent with the model.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.stats import poisson

from .match_simulator import (
    MatchSimulator, TeamProfile, GameState, EventType
)


# Empirical goal timing distribution (% of goals per 15-min window)
# Source: analysis of 10,000+ matches across top 5 leagues
GOAL_TIMING_WEIGHTS = {
    (1, 15): 0.11,    # Goals in 1-15'
    (16, 30): 0.15,   # Goals in 16-30'
    (31, 45): 0.14,   # Goals in 31-45' (+ first half stoppage)
    (46, 60): 0.17,   # Goals in 46-60' (2nd half start burst)
    (61, 75): 0.19,   # Goals in 61-75' (substitution impact)
    (76, 90): 0.24,   # Goals in 76-90'+ (urgency + fatigue)
}

# Empirical corner timing (fairly even, slight 2nd half bias)
CORNER_TIMING_WEIGHTS = {
    (1, 15): 0.14, (16, 30): 0.16, (31, 45): 0.17,
    (46, 60): 0.17, (61, 75): 0.18, (76, 90): 0.18,
}

# Empirical card timing (increases through match)
CARD_TIMING_WEIGHTS = {
    (1, 15): 0.08, (16, 30): 0.12, (31, 45): 0.15,
    (46, 60): 0.18, (61, 75): 0.22, (76, 90): 0.25,
}


def _sample_minute_from_weights(weights: Dict[Tuple[int, int], float]) -> int:
    """Sample a random minute from a weighted time-window distribution."""
    windows = list(weights.keys())
    probs = list(weights.values())
    total = sum(probs)
    probs = [p / total for p in probs]

    r = random.random()
    cumulative = 0
    for window, prob in zip(windows, probs):
        cumulative += prob
        if r <= cumulative:
            return random.randint(window[0], window[1])
    return random.randint(1, 90)


@dataclass
class CalibratedMatchPlan:
    """Pre-determined match outcome plan from the calibrated model."""
    home_goals: int = 0
    away_goals: int = 0
    home_goal_minutes: List[int] = field(default_factory=list)
    away_goal_minutes: List[int] = field(default_factory=list)
    total_corners: int = 9
    home_corners: int = 5
    away_corners: int = 4
    corner_minutes: List[Tuple[int, str]] = field(default_factory=list)  # (minute, "home"/"away")
    total_cards: int = 4
    home_cards: int = 2
    away_cards: int = 2
    card_minutes: List[Tuple[int, str]] = field(default_factory=list)
    total_shots: int = 22
    home_shots: int = 12
    away_shots: int = 10
    total_sot: int = 8
    home_sot: int = 5
    away_sot: int = 3
    total_fouls: int = 24
    red_cards: int = 0


class CalibratedSimulator:
    """
    Simulation engine anchored to V5 predictions.

    Uses the existing MatchSimulator for team profile building and commentary,
    but replaces the core simulation logic with calibrated Poisson sampling.
    """

    def __init__(self):
        self.base_simulator = MatchSimulator()

    def simulate_match(
        self,
        home_name: str,
        away_name: str,
        agent_reports: List[Dict],
        v5_expected_goals: Optional[Dict] = None,
        match_stats_prediction: Optional[Dict] = None,
        calibrated_probs: Optional[Dict] = None,
        seed: Optional[int] = None,
    ) -> Dict:
        """
        Run a single calibrated match simulation.

        Args:
            home_name, away_name: Team names
            agent_reports: Raw agent report dicts for team profile building
            v5_expected_goals: {"home": 1.4, "away": 0.9, "total": 2.3} from V5
            match_stats_prediction: {"corners": 9.5, "cards": 4.2, ...} from V4 analysis
            calibrated_probs: {"home_win": 0.55, "draw": 0.25, ...} from V5
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

        # Build team profiles from agent intelligence (reuse existing logic)
        home_profile, away_profile = self.base_simulator.build_team_profiles(agent_reports)
        home_profile.name = home_name
        away_profile.name = away_name

        # === STEP 1: Pre-determine match outcome from V5 model ===
        plan = self._create_match_plan(
            v5_expected_goals, match_stats_prediction, home_profile, away_profile
        )

        # === STEP 2: Generate minute-by-minute events around the plan ===
        events, state = self._generate_events(
            plan, home_profile, away_profile, home_name, away_name
        )

        # === STEP 3: Post-match analysis ===
        motm = self.base_simulator._calculate_motm(events, home_profile, away_profile)
        summary = self.base_simulator._generate_match_summary(
            home_name, away_name, state, events, home_profile, away_profile
        )
        key_moments = self.base_simulator._extract_key_moments(events)

        return {
            "match": f"{home_name} vs {away_name}",
            "final_score": {"home": plan.home_goals, "away": plan.away_goals},
            "half_time_score": self._compute_ht_score(plan),
            "events": events,
            "stats": {
                "possession": [round(state.possession_pct[0], 1), round(state.possession_pct[1], 1)],
                "shots": [plan.home_shots, plan.away_shots],
                "shots_on_target": [plan.home_sot, plan.away_sot],
                "corners": [plan.home_corners, plan.away_corners],
                "fouls": [state.fouls.get("home", 0), state.fouls.get("away", 0)],
                "yellow_cards": [plan.home_cards, plan.away_cards],
                "red_cards": [plan.red_cards if random.random() < 0.5 else 0,
                              plan.red_cards if random.random() >= 0.5 else 0],
                "offsides": [random.randint(1, 4), random.randint(1, 4)],
                "passes": [state.passes.get("home", 0), state.passes.get("away", 0)],
            },
            "xg": [
                round(v5_expected_goals.get("home", plan.home_goals * 0.85 + 0.3), 2) if v5_expected_goals else round(plan.home_goals * 0.85 + 0.3, 2),
                round(v5_expected_goals.get("away", plan.away_goals * 0.85 + 0.3), 2) if v5_expected_goals else round(plan.away_goals * 0.85 + 0.3, 2),
            ],
            "motm": motm,
            "match_summary": summary,
            "key_moments": key_moments,
            "formations": {
                "home": home_profile.formation,
                "away": away_profile.formation,
            },
            "managers": {
                "home": home_profile.manager.name,
                "away": away_profile.manager.name,
            },
            "tactical_changes": state.tactical_changes,
            "substitutions_detail": state.subs_made,
        }

    def _create_match_plan(
        self,
        v5_xg: Optional[Dict],
        match_stats: Optional[Dict],
        home: TeamProfile,
        away: TeamProfile,
    ) -> CalibratedMatchPlan:
        """
        Pre-determine match outcomes using Poisson sampling anchored to V5 expected goals.
        """
        plan = CalibratedMatchPlan()

        # --- Goals: Poisson sample from V5 expected goals ---
        if v5_xg and v5_xg.get("home", 0) > 0:
            home_lambda = v5_xg["home"]
            away_lambda = v5_xg["away"]
        else:
            # Fallback: derive from team profiles (but cap to be realistic)
            home_lambda = min(2.5, max(0.5, home.attack_rating / 50.0))
            away_lambda = min(2.0, max(0.3, away.attack_rating / 55.0))

        # Apply small random perturbation (±15%) to prevent every sim being identical
        home_lambda *= random.uniform(0.85, 1.15)
        away_lambda *= random.uniform(0.85, 1.15)

        plan.home_goals = poisson.rvs(home_lambda)
        plan.away_goals = poisson.rvs(away_lambda)

        # Cap extreme scorelines (>5 goals for one team is extremely rare)
        plan.home_goals = min(plan.home_goals, 5)
        plan.away_goals = min(plan.away_goals, 5)

        # Place goals at realistic minutes
        plan.home_goal_minutes = sorted([
            _sample_minute_from_weights(GOAL_TIMING_WEIGHTS) for _ in range(plan.home_goals)
        ])
        plan.away_goal_minutes = sorted([
            _sample_minute_from_weights(GOAL_TIMING_WEIGHTS) for _ in range(plan.away_goals)
        ])

        # --- Corners: Poisson from model prediction ---
        if match_stats and match_stats.get("corners", 0) > 0:
            corner_lambda = match_stats["corners"]
            home_corner_ratio = match_stats.get("home_corners", 5) / max(1, match_stats.get("corners", 10))
        else:
            corner_lambda = 9.5
            home_corner_ratio = 0.52

        # Add small variance
        corner_lambda *= random.uniform(0.85, 1.15)
        plan.total_corners = max(3, min(18, poisson.rvs(corner_lambda)))
        plan.home_corners = max(1, min(plan.total_corners - 1,
                                       int(plan.total_corners * home_corner_ratio + random.uniform(-1, 1))))
        plan.away_corners = plan.total_corners - plan.home_corners

        # Place corners at realistic minutes
        corner_events = []
        for _ in range(plan.home_corners):
            corner_events.append((_sample_minute_from_weights(CORNER_TIMING_WEIGHTS), "home"))
        for _ in range(plan.away_corners):
            corner_events.append((_sample_minute_from_weights(CORNER_TIMING_WEIGHTS), "away"))
        plan.corner_minutes = sorted(corner_events, key=lambda x: x[0])

        # --- Cards: Poisson from model prediction ---
        if match_stats and match_stats.get("cards", 0) > 0:
            card_lambda = match_stats["cards"]
        else:
            card_lambda = 4.0

        card_lambda *= random.uniform(0.85, 1.15)
        plan.total_cards = max(0, min(10, poisson.rvs(card_lambda)))
        plan.home_cards = max(0, min(plan.total_cards, int(plan.total_cards * 0.45 + random.uniform(-0.5, 0.5))))
        plan.away_cards = plan.total_cards - plan.home_cards

        # Place cards at realistic minutes (more in 2nd half)
        card_events = []
        for _ in range(plan.home_cards):
            card_events.append((_sample_minute_from_weights(CARD_TIMING_WEIGHTS), "home"))
        for _ in range(plan.away_cards):
            card_events.append((_sample_minute_from_weights(CARD_TIMING_WEIGHTS), "away"))
        plan.card_minutes = sorted(card_events, key=lambda x: x[0])

        # --- Shots ---
        if match_stats and match_stats.get("shots", 0) > 0:
            plan.total_shots = max(8, int(match_stats["shots"] * random.uniform(0.85, 1.15)))
            plan.total_sot = max(3, int(match_stats.get("sot", 8) * random.uniform(0.85, 1.15)))
        else:
            plan.total_shots = random.randint(18, 28)
            plan.total_sot = random.randint(6, 12)

        # Distribute shots proportionally (team with more goals gets more shots)
        total_goals = plan.home_goals + plan.away_goals + 0.1
        home_shot_ratio = 0.5 + (plan.home_goals - plan.away_goals) / (total_goals * 4)
        home_shot_ratio = max(0.3, min(0.7, home_shot_ratio))
        plan.home_shots = int(plan.total_shots * home_shot_ratio)
        plan.away_shots = plan.total_shots - plan.home_shots
        plan.home_sot = max(plan.home_goals, int(plan.total_sot * home_shot_ratio))
        plan.away_sot = max(plan.away_goals, plan.total_sot - plan.home_sot)

        # --- Fouls & red cards ---
        if match_stats and match_stats.get("fouls", 0) > 0:
            plan.total_fouls = max(10, int(match_stats["fouls"] * random.uniform(0.85, 1.15)))
        else:
            plan.total_fouls = random.randint(18, 30)

        # Red card: ~3% probability per match
        if match_stats and match_stats.get("reds", 0) > 0.15:
            plan.red_cards = 1 if random.random() < match_stats["reds"] else 0
        else:
            plan.red_cards = 1 if random.random() < 0.03 else 0

        return plan

    def _compute_ht_score(self, plan: CalibratedMatchPlan) -> Dict:
        """Compute half-time score from goal minutes."""
        ht_home = sum(1 for m in plan.home_goal_minutes if m <= 45)
        ht_away = sum(1 for m in plan.away_goal_minutes if m <= 45)
        return {"home": ht_home, "away": ht_away}

    def _generate_events(
        self,
        plan: CalibratedMatchPlan,
        home: TeamProfile,
        away: TeamProfile,
        home_name: str,
        away_name: str,
    ) -> Tuple[List[Dict], GameState]:
        """
        Generate minute-by-minute events around the pre-determined plan.
        Events are PLACED at their predetermined minutes — not randomly generated.
        """
        state = GameState()
        events = []
        self.base_simulator.card_recipients = {"home": [], "away": []}

        # Build event schedule: merge all predetermined events
        scheduled = []
        for m in plan.home_goal_minutes:
            scheduled.append((m, "goal", "home"))
        for m in plan.away_goal_minutes:
            scheduled.append((m, "goal", "away"))
        for m, side in plan.corner_minutes:
            scheduled.append((m, "corner", side))
        for m, side in plan.card_minutes:
            scheduled.append((m, "card", side))
        scheduled.sort(key=lambda x: (x[0], x[1]))

        # Distribute shots across minutes (not pre-scheduled, just tracked)
        home_shots_remaining = plan.home_shots - plan.home_sot  # Off-target shots
        away_shots_remaining = plan.away_shots - plan.away_sot

        # Kickoff
        events.append({
            "minute": 0,
            "type": EventType.KICKOFF.value,
            "team": None, "player": None,
            "commentary": f"The referee blows the whistle! {home_name} kick off against {away_name}. "
                          f"Formations: {home.formation} vs {away.formation}."
        })

        # Possession calculation
        home_mid = home.midfield_rating
        away_mid = away.midfield_rating
        total_mid = home_mid + away_mid
        if total_mid > 0:
            state.possession_pct[0] = (home_mid / total_mid) * 100
            state.possession_pct[1] = (away_mid / total_mid) * 100

        # Process minute by minute
        next_event_idx = 0
        home_score, away_score = 0, 0

        for minute in range(1, 96):
            if minute == 46:
                # Half-time
                events.append({
                    "minute": 45, "type": EventType.HALF_TIME.value,
                    "team": None, "player": None,
                    "commentary": f"Half-time: {home_name} {home_score}-{away_score} {away_name}. "
                                  f"Possession: {state.possession_pct[0]:.0f}%-{state.possession_pct[1]:.0f}%"
                })

            # Process scheduled events for this minute
            while next_event_idx < len(scheduled) and scheduled[next_event_idx][0] == minute:
                _, etype, side = scheduled[next_event_idx]
                next_event_idx += 1

                team_name = home_name if side == "home" else away_name
                profile = home if side == "home" else away
                opponent = away if side == "home" else home

                if etype == "goal":
                    # Generate goal event with real player names
                    scorer = self.base_simulator._pick_scorer(profile)
                    assister = self.base_simulator._pick_assister(profile, scorer)

                    if side == "home":
                        home_score += 1
                        state.home_score = home_score
                    else:
                        away_score += 1
                        state.away_score = away_score

                    state.shots_on_target[side] = state.shots_on_target.get(side, 0) + 1
                    state.shots[side] = state.shots.get(side, 0) + 1
                    state.xg[side] = state.xg.get(side, 0) + random.uniform(0.15, 0.55)

                    # Goal commentary variants
                    # Determine context for commentary
                    own_score = home_score if side == "home" else away_score
                    opp_score = away_score if side == "home" else home_score
                    context_word = "take the lead" if own_score > opp_score else ("equalize" if home_score == away_score else "pull one back")
                    score_line = f"{home_name} {home_score}-{away_score} {away_name}"

                    variants = [
                        f"⚽ {minute}' — GOAL! {scorer} scores for {team_name}! "
                        f"Assisted by {assister}. {score_line}.",
                        f"⚽ {minute}' — {scorer} finds the net! {team_name} {context_word}! "
                        f"{score_line}.",
                        f"⚽ {minute}' — Brilliant from {scorer}! {assister} with the assist. "
                        f"{score_line}.",
                    ]
                    events.append({
                        "minute": minute, "type": EventType.GOAL.value,
                        "team": side, "player": scorer,
                        "commentary": random.choice(variants),
                    })

                elif etype == "corner":
                    state.corners[side] = state.corners.get(side, 0) + 1

                    # Only create corner events for ~40% (keep transcript manageable)
                    if random.random() < 0.4:
                        events.append({
                            "minute": minute, "type": EventType.CORNER.value,
                            "team": side, "player": None,
                            "commentary": f"🚩 {minute}' — Corner kick for {team_name}. "
                                          f"{'Swung in dangerously!' if random.random() < 0.3 else 'Cleared by the defense.'}"
                        })

                elif etype == "card":
                    state.yellow_cards[side] = state.yellow_cards.get(side, 0) + 1
                    # Pick a player to receive the card
                    outfield = profile.get_outfield_players()
                    fouler = random.choice(outfield) if outfield else f"{team_name} player"
                    opp_player = random.choice(opponent.get_outfield_players()) if opponent.get_outfield_players() else "opponent"

                    fouls_list = [
                        f"🟨 {minute}' — Yellow card for {fouler} ({team_name}). Late challenge on {opp_player}.",
                        f"🟨 {minute}' — {fouler} is booked for a reckless foul.",
                        f"🟨 {minute}' — The referee shows yellow to {fouler}. Cynical foul to stop a counter-attack.",
                    ]
                    events.append({
                        "minute": minute, "type": EventType.YELLOW_CARD.value,
                        "team": side, "player": fouler,
                        "commentary": random.choice(fouls_list),
                    })
                    state.fouls[side] = state.fouls.get(side, 0) + 1

            # Atmospheric events: shots, fouls, etc. (fill in between major events)
            if random.random() < 0.15:
                side = "home" if random.random() < state.possession_pct[0] / 100 else "away"
                profile = home if side == "home" else away
                team_name = home_name if side == "home" else away_name

                if random.random() < 0.3 and state.shots.get(side, 0) < (plan.home_shots if side == "home" else plan.away_shots):
                    # Shot event
                    state.shots[side] = state.shots.get(side, 0) + 1
                    shooter = random.choice(profile.get_attackers()) if profile.get_attackers() else f"{team_name} player"

                    if random.random() < 0.35:
                        state.shots_on_target[side] = state.shots_on_target.get(side, 0) + 1
                        state.xg[side] = state.xg.get(side, 0) + random.uniform(0.05, 0.2)
                        events.append({
                            "minute": minute, "type": EventType.SHOT_ON_TARGET.value,
                            "team": side, "player": shooter,
                            "commentary": f"🎯 {minute}' — {shooter} tests the keeper! Good save.",
                        })
                    else:
                        miss_type = "wide" if random.random() < 0.5 else "over the bar"
                        events.append({
                            "minute": minute, "type": EventType.SHOT_OFF_TARGET.value,
                            "team": side, "player": shooter,
                            "commentary": f"💨 {minute}' — {shooter} fires {miss_type}.",
                        })

                elif random.random() < 0.25:
                    # Foul (no card)
                    state.fouls[side] = state.fouls.get(side, 0) + 1

            # Substitutions in 2nd half
            if 55 <= minute <= 85 and random.random() < 0.08:
                for side_name, team, tname in [("home", home, home_name), ("away", away, away_name)]:
                    if state.substitutions[side_name] < 5 and random.random() < 0.3:
                        sub_event = self.base_simulator._create_substitution_event(
                            minute, side_name, team, tname, state
                        )
                        if sub_event:
                            events.append(sub_event)
                            state.substitutions[side_name] += 1

            # Passes accumulation
            state.passes["home"] = state.passes.get("home", 0) + int(state.possession_pct[0] / 12)
            state.passes["away"] = state.passes.get("away", 0) + int(state.possession_pct[1] / 12)

        # Distribute remaining fouls evenly
        total_fouls_so_far = state.fouls.get("home", 0) + state.fouls.get("away", 0)
        remaining = plan.total_fouls - total_fouls_so_far
        if remaining > 0:
            state.fouls["home"] = state.fouls.get("home", 0) + remaining // 2
            state.fouls["away"] = state.fouls.get("away", 0) + remaining - remaining // 2

        # Full-time
        events.append({
            "minute": 90,
            "type": EventType.FULL_TIME.value,
            "team": None, "player": None,
            "commentary": f"Full-time: {home_name} {home_score}-{away_score} {away_name}"
        })

        return events, state
