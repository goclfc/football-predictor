import random
import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class EventType(Enum):
    """Enumeration of match event types."""
    KICKOFF = "kickoff"
    GOAL = "goal"
    SHOT_ON_TARGET = "shot_on_target"
    SHOT_OFF_TARGET = "shot_off_target"
    CORNER = "corner"
    FOUL = "foul"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SUBSTITUTION = "substitution"
    INJURY = "injury"
    VAR_CHECK = "var_check"
    PENALTY = "penalty"
    FREE_KICK_DANGEROUS = "free_kick_dangerous"
    OFFSIDE = "offside"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"
    TACTICAL_CHANGE = "tactical_change"


# GK detection names
GK_KEYWORDS = [
    "oblak", "courtois", "neuer", "ter stegen", "alisson", "ederson", "raya",
    "donnarumma", "maignan", "sommer", "musso", "szczesny", "navas", "onana",
    "garcia", "remiro", "areola", "simon", "rui silva", "mamardashvili",
    "szobo", "lafont", "nübel", "hradecky", "gulacsi", "trapp", "kobel",
    "casteels", "mvogo", "flekken", "keeper", "gk", "goalkeeper"
]


@dataclass
class ManagerProfile:
    """Manager's tactical profile for simulation."""
    name: str = "Unknown"
    pressing_intensity: str = "medium"  # low/medium/high
    counter_attack_tendency: str = "medium"
    sub_timing: str = "normal"  # early/normal/late
    defensive_organization: int = 6
    attacking_creativity: int = 6
    set_piece_coaching: int = 6
    mental_resilience: int = 6
    h2h_record_style: str = "adaptive"  # neutralizer/aggressive/adaptive/conservative
    tactical_flexibility: int = 6
    preferred_formation: str = "4-3-3"


@dataclass
class TeamProfile:
    """Profile of a team's capabilities built from ALL agent intelligence."""
    name: str
    attack_rating: float = 70.0  # 0-100
    defense_rating: float = 70.0  # 0-100
    midfield_rating: float = 70.0  # 0-100
    set_piece_rating: float = 65.0  # 0-100
    gk_rating: float = 75.0  # 0-100
    discipline: float = 0.75  # 0-1 (higher = more disciplined)
    motivation: float = 0.85  # 0-1
    fatigue: float = 0.2  # 0-1 (higher = more fatigued)
    momentum: float = 0.5  # 0-1
    tactical_style: str = "balanced"
    key_players: List[str] = field(default_factory=list)
    manager: ManagerProfile = field(default_factory=ManagerProfile)
    # NEW: Player role data from lineup
    starters: List[Dict] = field(default_factory=list)  # [{name, position, number}]
    subs: List[Dict] = field(default_factory=list)  # [{name, position, number}]
    formation: str = "4-3-3"
    # NEW: Player form data from PlayerNewsAgent
    player_ratings: Dict[str, float] = field(default_factory=dict)  # name -> rating
    top_scorers: List[Dict] = field(default_factory=list)  # [{name, goals, assists}]
    # NEW: Odds-based strength
    implied_win_prob: float = 0.33
    # NEW: Form data
    recent_form: str = ""  # e.g. "WWDLW"
    h2h_advantage: float = 0.0  # -1 to 1

    def get_outfield_players(self) -> List[str]:
        """Get outfield players (exclude GK)."""
        if self.starters:
            return [p["name"] for p in self.starters
                    if not any(gk in p.get("name", "").lower() for gk in GK_KEYWORDS)
                    and p.get("position", "").lower() != "goalkeeper"]
        return [p for p in self.key_players
                if not any(gk in p.lower() for gk in GK_KEYWORDS)]

    def get_attackers(self) -> List[str]:
        """Get attacking players."""
        if self.starters:
            atk = [p["name"] for p in self.starters
                   if p.get("position", "").lower() in ("forward", "attacker", "striker")]
            if atk:
                return atk
        # Fallback: first 3 outfield
        outfield = self.get_outfield_players()
        return outfield[:3] if outfield else [f"{self.name} Forward"]

    def get_midfielders(self) -> List[str]:
        """Get midfield players."""
        if self.starters:
            mid = [p["name"] for p in self.starters
                   if p.get("position", "").lower() == "midfielder"]
            if mid:
                return mid
        outfield = self.get_outfield_players()
        return outfield[3:6] if len(outfield) > 3 else outfield

    def get_defenders(self) -> List[str]:
        """Get defensive players."""
        if self.starters:
            defs = [p["name"] for p in self.starters
                    if p.get("position", "").lower() == "defender"]
            if defs:
                return defs
        outfield = self.get_outfield_players()
        return outfield[6:] if len(outfield) > 6 else outfield

    def get_best_scorer(self) -> str:
        """Get the most likely goal scorer based on form data."""
        if self.top_scorers:
            return self.top_scorers[0].get("name", self.get_attackers()[0])
        attackers = self.get_attackers()
        return attackers[0] if attackers else f"{self.name} Forward"

    def get_adjusted_attack(self, minute: int, score_diff: int) -> float:
        """Attack rating adjusted for game state, fatigue, manager style, and momentum."""
        rating = self.attack_rating

        # Manager creativity boost
        rating += (self.manager.attacking_creativity - 5) * 1.5

        # Desperation boost if losing late
        if score_diff < 0:
            urgency = 1.05 + (minute / 90) * 0.1  # Up to 15% boost at 90'
            rating *= urgency

        # Counter-attack boost when defending deep and winning
        if score_diff > 0 and self.manager.counter_attack_tendency == "high":
            rating *= 1.05  # Counter-attacking teams stay dangerous

        # Pressing intensity affects attacking transitions
        if self.manager.pressing_intensity == "high" and minute < 70:
            rating *= 1.06
        elif self.manager.pressing_intensity == "low":
            rating *= 0.95

        # Fatigue kicks in — high-pressing teams tire faster
        if minute > 60:
            base_fatigue = self.fatigue * 0.2
            if self.manager.pressing_intensity == "high":
                base_fatigue *= 1.3  # High press = faster tired
            rating *= (1 - base_fatigue)

        # Momentum factor
        rating *= (0.95 + self.momentum * 0.1)

        # Motivation
        rating *= (0.9 + self.motivation * 0.1)

        return min(100, max(0, rating))

    def get_adjusted_defense(self, minute: int, score_diff: int) -> float:
        """Defense rating adjusted for game state and manager organization."""
        rating = self.defense_rating

        # Manager defensive organization boost
        rating += (self.manager.defensive_organization - 5) * 2.0

        # Leading teams defend deeper (better organized)
        if score_diff > 0 and self.manager.h2h_record_style in ("neutralizer", "conservative"):
            rating *= 1.08

        # Losing teams become desperate, defense suffers
        if score_diff < 0 and minute > 70:
            rating *= 0.88

        # Red card impact — massive defensive hole
        # (handled in game state)

        # Fatigue penalty
        if minute > 60:
            base_fatigue = self.fatigue * 0.15
            rating *= (1 - base_fatigue)

        return min(100, max(0, rating))


@dataclass
class GameState:
    """Current state of the match with enhanced tracking."""
    home_score: int = 0
    away_score: int = 0
    possession_pct: List[float] = field(default_factory=lambda: [50.0, 50.0])
    yellow_cards: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    red_cards: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    corners: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    shots: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    shots_on_target: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    fouls: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    offsides: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    passes: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    momentum: Dict[str, float] = field(default_factory=lambda: {"home": 0.5, "away": 0.5})
    injuries: List[Dict] = field(default_factory=list)
    substitutions: Dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    subs_made: Dict[str, List[Dict]] = field(default_factory=lambda: {"home": [], "away": []})
    # xG tracking
    xg: Dict[str, float] = field(default_factory=lambda: {"home": 0.0, "away": 0.0})
    # Tactical changes
    tactical_changes: Dict[str, List[str]] = field(default_factory=lambda: {"home": [], "away": []})


class MatchSimulator:
    """Enhanced football match simulation engine that uses ALL 25 agent intelligence."""

    def __init__(self):
        self.card_recipients = {"home": [], "away": []}

    def _safe_parse(self, val):
        """Safely parse string representations of lists/dicts."""
        if isinstance(val, (list, dict)):
            return val
        if isinstance(val, str) and val.startswith(("[", "{")):
            try:
                return ast.literal_eval(val)
            except:
                return []
        return val

    def build_team_profiles(self, agent_reports: List[Dict]) -> Tuple[TeamProfile, TeamProfile]:
        """Build comprehensive team profiles from ALL 25 agents' intelligence."""
        h = {"atk": [], "def": [], "mid": [], "sp": [], "gk": [], "disc": [],
             "mot": [], "fat": [], "mom": [], "style": "balanced", "players": [],
             "mgr": ManagerProfile(), "starters": [], "subs": [], "formation": "4-3-3",
             "player_ratings": {}, "top_scorers": [], "win_prob": 0.33,
             "form": "", "h2h_adv": 0.0}
        a = {"atk": [], "def": [], "mid": [], "sp": [], "gk": [], "disc": [],
             "mot": [], "fat": [], "mom": [], "style": "balanced", "players": [],
             "mgr": ManagerProfile(), "starters": [], "subs": [], "formation": "4-3-3",
             "player_ratings": {}, "top_scorers": [], "win_prob": 0.33,
             "form": "", "h2h_adv": 0.0}

        for rpt in agent_reports:
            p = rpt.get("predictions", {})
            # Support both "agent" and "agent_name" keys
            agent = rpt.get("agent", "") or rpt.get("agent_name", "")

            # === Original 6 Agents (BaseAgent format: predictions is list of dicts) ===
            # These have predictions as list of {market, outcome, probability, ...}
            if isinstance(p, list):
                pred_dict = {}
                for pred in p:
                    if isinstance(pred, dict):
                        pred_dict[pred.get("market", "")] = pred.get("outcome", "")
                p = pred_dict

            # ---- KEY PLAYER AGENT ----
            if agent == "key_player_analyst":
                if "home_key_players" in p and isinstance(p["home_key_players"], list):
                    h["players"] = p["home_key_players"]
                if "away_key_players" in p and isinstance(p["away_key_players"], list):
                    a["players"] = p["away_key_players"]
                self._safe_float_append(h["atk"], p.get("key_player_influence_home"), mult=100)
                self._safe_float_append(a["atk"], p.get("key_player_influence_away"), mult=100)

            # ---- ATTACKING PROFILE AGENT ----
            if agent == "attacking_profile_agent":
                self._safe_float_append(h["atk"], p.get("xg_home"), mult=40)
                self._safe_float_append(a["atk"], p.get("xg_away"), mult=40)

            # ---- DEFENSIVE PROFILE AGENT ----
            if agent == "defensive_profile_agent":
                self._safe_float_append(h["def"], p.get("clean_sheet_prob_home"), mult=100)
                self._safe_float_append(a["def"], p.get("clean_sheet_prob_away"), mult=100)

            # ---- TACTICAL AGENT ----
            if agent == "tactical_agent":
                if "tactical_edge" in p:
                    edge = self._safe_float(p["tactical_edge"])
                    h["mid"].append(70 + edge * 20)
                    a["mid"].append(70 - edge * 20)
                if "possession_prediction" in p:
                    pp = self._safe_float(p["possession_prediction"])
                    h["mid"].append(pp * 100)
                    a["mid"].append((1 - pp) * 100)
                h["style"] = p.get("home_style", h["style"])
                a["style"] = p.get("away_style", a["style"])

            # ---- SET PIECE AGENT ----
            if agent == "set_piece_agent":
                self._safe_float_append(h["sp"], p.get("corner_goal_prob_home"), mult=500)
                self._safe_float_append(a["sp"], p.get("corner_goal_prob_away"), mult=500)

            # ---- GOALKEEPER AGENT ----
            if agent == "goalkeeper_analyst":
                if "clean_sheet_adj_home" in p:
                    h["gk"].append(70 + self._safe_float(p["clean_sheet_adj_home"]) * 50)
                if "clean_sheet_adj_away" in p:
                    a["gk"].append(70 + self._safe_float(p["clean_sheet_adj_away"]) * 50)

            # ---- STAKES AGENT ----
            if agent == "stakes_agent":
                self._safe_float_append(h["mot"], p.get("motivation_multiplier_home"))
                self._safe_float_append(a["mot"], p.get("motivation_multiplier_away"))

            # ---- FATIGUE AGENT ----
            if agent == "fatigue_analyst":
                self._safe_float_append(h["fat"], p.get("fatigue_level_home"))
                self._safe_float_append(a["fat"], p.get("fatigue_level_away"))

            # ---- MOMENTUM AGENT ----
            if agent == "momentum_agent":
                self._safe_float_append(h["mom"], p.get("momentum_home"))
                self._safe_float_append(a["mom"], p.get("momentum_away"))

            # ---- RIVALRY AGENT ----
            if agent == "rivalry_agent":
                if "card_multiplier" in p:
                    cm = self._safe_float(p["card_multiplier"])
                    h["disc"].append(max(0.4, 1.0 - (cm - 1.0)))
                    a["disc"].append(max(0.4, 1.0 - (cm - 1.0)))

            # ---- MANAGER AGENT (ENHANCED) ----
            if agent == "manager_agent":
                # Quality scores
                if "in_game_adjustment_rating_home" in p:
                    h_mgr_quality = self._safe_float(p["in_game_adjustment_rating_home"]) * 10
                    h["mgr"].tactical_flexibility = int(self._safe_float(p["in_game_adjustment_rating_home"]))
                if "in_game_adjustment_rating_away" in p:
                    a_mgr_quality = self._safe_float(p["in_game_adjustment_rating_away"]) * 10
                    a["mgr"].tactical_flexibility = int(self._safe_float(p["in_game_adjustment_rating_away"]))

                # Manager names
                h["mgr"].name = str(p.get("home_manager", "Unknown"))
                a["mgr"].name = str(p.get("away_manager", "Unknown"))

                # NEW tactical fields
                h["mgr"].pressing_intensity = str(p.get("home_pressing_intensity", "medium"))
                a["mgr"].pressing_intensity = str(p.get("away_pressing_intensity", "medium"))
                h["mgr"].counter_attack_tendency = str(p.get("home_counter_attack_tendency", "medium"))
                a["mgr"].counter_attack_tendency = str(p.get("away_counter_attack_tendency", "medium"))
                h["mgr"].sub_timing = str(p.get("home_sub_timing", "normal"))
                a["mgr"].sub_timing = str(p.get("away_sub_timing", "normal"))
                h["mgr"].defensive_organization = int(self._safe_float(p.get("home_defensive_organization", 6)))
                a["mgr"].defensive_organization = int(self._safe_float(p.get("away_defensive_organization", 6)))
                h["mgr"].attacking_creativity = int(self._safe_float(p.get("home_attacking_creativity", 6)))
                a["mgr"].attacking_creativity = int(self._safe_float(p.get("away_attacking_creativity", 6)))
                h["mgr"].set_piece_coaching = int(self._safe_float(p.get("home_set_piece_coaching", 6)))
                a["mgr"].set_piece_coaching = int(self._safe_float(p.get("away_set_piece_coaching", 6)))
                h["mgr"].mental_resilience = int(self._safe_float(p.get("home_mental_resilience", 6)))
                a["mgr"].mental_resilience = int(self._safe_float(p.get("away_mental_resilience", 6)))
                h["mgr"].h2h_record_style = str(p.get("home_h2h_record_style", "adaptive"))
                a["mgr"].h2h_record_style = str(p.get("away_h2h_record_style", "adaptive"))

            # ---- REFEREE AGENT ----
            if agent == "referee_agent":
                if "referee_strictness" in p:
                    strict = self._safe_float(p["referee_strictness"]) / 10
                    h["disc"].append(max(0.5, 0.85 - strict * 0.1))
                    a["disc"].append(max(0.5, 0.85 - strict * 0.1))

            # ---- LINEUP AGENT (REAL SQUAD DATA) ----
            if agent == "lineup_analyst":
                xi_home = self._safe_parse(p.get("home_predicted_xi", []))
                xi_away = self._safe_parse(p.get("away_predicted_xi", []))
                if xi_home and isinstance(xi_home, list):
                    h["starters"] = xi_home
                    h["players"] = [pl["name"] for pl in xi_home if isinstance(pl, dict) and "name" in pl]
                if xi_away and isinstance(xi_away, list):
                    a["starters"] = xi_away
                    a["players"] = [pl["name"] for pl in xi_away if isinstance(pl, dict) and "name" in pl]

                # Subs: derive from full squad minus predicted XI
                squad_home = self._safe_parse(p.get("home_squad", []))
                squad_away = self._safe_parse(p.get("away_squad", []))
                if squad_home and isinstance(squad_home, list) and xi_home:
                    xi_names = {pl.get("name", "").lower() for pl in xi_home if isinstance(pl, dict)}
                    h["subs"] = [pl for pl in squad_home
                                 if isinstance(pl, dict) and pl.get("name", "").lower() not in xi_names
                                 and pl.get("position", "").lower() != "goalkeeper"]
                if squad_away and isinstance(squad_away, list) and xi_away:
                    xi_names = {pl.get("name", "").lower() for pl in xi_away if isinstance(pl, dict)}
                    a["subs"] = [pl for pl in squad_away
                                 if isinstance(pl, dict) and pl.get("name", "").lower() not in xi_names
                                 and pl.get("position", "").lower() != "goalkeeper"]

                # Formations
                h["formation"] = str(p.get("home_formation", "4-3-3"))
                a["formation"] = str(p.get("away_formation", "4-3-3"))

                # Injury impact
                if "home_injury_impact" in p:
                    impact = self._safe_float(p["home_injury_impact"])
                    if impact > 0:
                        h["atk"].append(max(55, 72 - impact * 200))
                if "away_injury_impact" in p:
                    impact = self._safe_float(p["away_injury_impact"])
                    if impact > 0:
                        a["atk"].append(max(55, 72 - impact * 200))

            # ---- PLAYER NEWS AGENT (FORM DATA) ----
            if agent == "player_news_analyst":
                # Top scorers
                home_top = self._safe_parse(p.get("home_top_scorers", []))
                away_top = self._safe_parse(p.get("away_top_scorers", []))
                if home_top and isinstance(home_top, list):
                    h["top_scorers"] = home_top
                    total_g = sum(self._safe_float(s.get("goals", 0)) for s in home_top[:3])
                    h["atk"].append(min(92, 60 + total_g * 2))
                if away_top and isinstance(away_top, list):
                    a["top_scorers"] = away_top
                    total_g = sum(self._safe_float(s.get("goals", 0)) for s in away_top[:3])
                    a["atk"].append(min(92, 60 + total_g * 2))

                # Player ratings map
                home_reports = self._safe_parse(p.get("home_player_reports", []))
                away_reports = self._safe_parse(p.get("away_player_reports", []))
                if home_reports and isinstance(home_reports, list):
                    for pr in home_reports:
                        if isinstance(pr, dict) and "name" in pr:
                            rating = self._safe_float(pr.get("stats", {}).get("rating", 0))
                            if rating > 0:
                                h["player_ratings"][pr["name"]] = rating
                if away_reports and isinstance(away_reports, list):
                    for pr in away_reports:
                        if isinstance(pr, dict) and "name" in pr:
                            rating = self._safe_float(pr.get("stats", {}).get("rating", 0))
                            if rating > 0:
                                a["player_ratings"][pr["name"]] = rating

            # ---- VENUE AGENT ----
            if agent == "venue_agent":
                if "home_advantage_factor" in p:
                    haf = self._safe_float(p["home_advantage_factor"])
                    h["atk"].append(70 + haf * 10)
                    h["def"].append(70 + haf * 5)

            # ---- WEATHER AGENT ----
            if agent == "weather_agent":
                if "weather_impact" in p:
                    wi = self._safe_float(p["weather_impact"])
                    if wi > 0.5:  # Bad weather
                        h["atk"].append(max(55, 70 - wi * 10))
                        a["atk"].append(max(55, 70 - wi * 10))

            # ---- REST DAYS AGENT ----
            if agent == "rest_days_agent":
                if "rest_advantage" in p:
                    ra = str(p["rest_advantage"])
                    if ra == "home":
                        h["fat"].append(max(0, h["fat"][-1] - 0.1) if h["fat"] else 0.15)
                    elif ra == "away":
                        a["fat"].append(max(0, a["fat"][-1] - 0.1) if a["fat"] else 0.15)

            # ---- INJURY AGENT ----
            if agent == "injury_analyst":
                if "home_injury_severity" in p:
                    sev = self._safe_float(p["home_injury_severity"])
                    h["atk"].append(max(50, 75 - sev * 15))
                if "away_injury_severity" in p:
                    sev = self._safe_float(p["away_injury_severity"])
                    a["atk"].append(max(50, 75 - sev * 15))

            # ---- MEDIA PRESSURE AGENT ----
            if agent == "media_pressure_agent":
                if "pressure_level_home" in p:
                    pl_h = self._safe_float(p["pressure_level_home"])
                    # High pressure can hurt or help depending on mental resilience
                    h["mot"].append(max(0.6, 0.85 + (pl_h - 5) * 0.01))
                if "pressure_level_away" in p:
                    pl_a = self._safe_float(p["pressure_level_away"])
                    a["mot"].append(max(0.6, 0.85 + (pl_a - 5) * 0.01))

            # ---- FORM AGENT (original) ----
            if agent in ("FormAgent", "form_agent"):
                if "home_form_score" in p:
                    h["mom"].append(self._safe_float(p["home_form_score"]))
                if "away_form_score" in p:
                    a["mom"].append(self._safe_float(p["away_form_score"]))

            # ---- MARKET/ODDS AGENT ----
            if agent in ("MarketAgent", "market_agent"):
                if "home_win_prob" in p:
                    h["win_prob"] = self._safe_float(p["home_win_prob"])
                if "away_win_prob" in p:
                    a["win_prob"] = self._safe_float(p["away_win_prob"])

            # ---- HISTORICAL/H2H AGENT ----
            if agent in ("HistoricalAgent", "historical_agent"):
                if "h2h_home_advantage" in p:
                    h["h2h_adv"] = self._safe_float(p["h2h_home_advantage"])

            # ---- SCHEDULE CONTEXT AGENT ----
            if agent == "schedule_context_agent":
                # Rotation risk affects team strength
                home_rot = self._safe_float(p.get("home_rotation_risk", 0))
                away_rot = self._safe_float(p.get("away_rotation_risk", 0))
                if home_rot > 0.2:
                    h["atk"].append(max(55, 72 - home_rot * 15))
                    h["mot"].append(max(0.6, 0.85 - home_rot * 0.2))
                if away_rot > 0.2:
                    a["atk"].append(max(55, 68 - away_rot * 15))
                    a["mot"].append(max(0.6, 0.80 - away_rot * 0.2))

                # H2H goals pattern affects expected goals
                h2h_avg_goals = self._safe_float(p.get("h2h_avg_goals", 0))
                if h2h_avg_goals > 3.0:
                    h["atk"].append(min(90, 72 + (h2h_avg_goals - 2.5) * 5))
                    a["atk"].append(min(90, 68 + (h2h_avg_goals - 2.5) * 5))

            # ---- HISTORICAL ODDS AGENT ----
            if agent == "historical_odds_agent":
                # Implied probabilities from current odds
                ip_home = self._safe_float(p.get("implied_prob_home", 0))
                ip_away = self._safe_float(p.get("implied_prob_away", 0))
                if ip_home > 0:
                    h["win_prob"] = ip_home
                if ip_away > 0:
                    a["win_prob"] = ip_away

        def avg(lst, default):
            return sum(float(x) for x in lst) / len(lst) if lst else default

        home_profile = TeamProfile(
            name="Home",
            attack_rating=min(95, avg(h["atk"], 72)),
            defense_rating=min(95, avg(h["def"], 70)),
            midfield_rating=min(95, avg(h["mid"], 72)),
            set_piece_rating=min(95, avg(h["sp"], 65)),
            gk_rating=min(95, avg(h["gk"], 75)),
            discipline=max(0.3, min(1.0, avg(h["disc"], 0.75))),
            motivation=max(0.5, min(1.0, avg(h["mot"], 0.85))),
            fatigue=max(0.0, min(1.0, avg(h["fat"], 0.2))),
            momentum=max(0.0, min(1.0, avg(h["mom"], 0.5))),
            tactical_style=h["style"],
            key_players=h["players"][:11] if h["players"] else ["Star Forward", "Midfielder", "Defender", "Goalkeeper"],
            manager=h["mgr"],
            starters=h["starters"],
            subs=h["subs"],
            formation=h["formation"],
            player_ratings=h["player_ratings"],
            top_scorers=h["top_scorers"],
            implied_win_prob=h["win_prob"],
            h2h_advantage=h["h2h_adv"],
        )

        away_profile = TeamProfile(
            name="Away",
            attack_rating=min(95, avg(a["atk"], 68)),
            defense_rating=min(95, avg(a["def"], 68)),
            midfield_rating=min(95, avg(a["mid"], 70)),
            set_piece_rating=min(95, avg(a["sp"], 63)),
            gk_rating=min(95, avg(a["gk"], 73)),
            discipline=max(0.3, min(1.0, avg(a["disc"], 0.72))),
            motivation=max(0.5, min(1.0, avg(a["mot"], 0.80))),
            fatigue=max(0.0, min(1.0, avg(a["fat"], 0.25))),
            momentum=max(0.0, min(1.0, avg(a["mom"], 0.5))),
            tactical_style=a["style"],
            key_players=a["players"][:11] if a["players"] else ["Star Forward", "Midfielder", "Defender", "Goalkeeper"],
            manager=a["mgr"],
            starters=a["starters"],
            subs=a["subs"],
            formation=a["formation"],
            player_ratings=a["player_ratings"],
            top_scorers=a["top_scorers"],
            implied_win_prob=a["win_prob"],
            h2h_advantage=a["h2h_adv"],
        )

        return home_profile, away_profile

    def _safe_float(self, val, default=0.0) -> float:
        """Safely convert a value to float."""
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _safe_float_append(self, lst: list, val, mult=1.0):
        """Safely append a float value to a list."""
        if val is not None:
            f = self._safe_float(val)
            if f != 0:
                lst.append(f * mult)

    def simulate_match(
        self,
        home_team_name: str,
        away_team_name: str,
        agent_reports: List[Dict],
        seed: Optional[int] = None
    ) -> Dict:
        """Simulate a complete match with minute-by-minute events using all intelligence."""
        if seed is not None:
            random.seed(seed)

        # Build team profiles from ALL agent intelligence
        home_profile, away_profile = self.build_team_profiles(agent_reports)
        home_profile.name = home_team_name
        away_profile.name = away_team_name

        # Initialize game state
        state = GameState()
        events = []
        ht_score = None

        # Reset card tracking
        self.card_recipients = {"home": [], "away": []}

        # Kickoff
        events.append({
            "minute": 0,
            "type": EventType.KICKOFF.value,
            "team": None,
            "player": None,
            "commentary": f"The referee blows the whistle! {home_team_name} kick off against {away_team_name}. "
                          f"Formations: {home_profile.formation} vs {away_profile.formation}."
        })

        # Simulate first half
        for minute in range(1, 46):
            self._simulate_minute(minute, home_profile, away_profile, state, events,
                                  home_team_name, away_team_name)

        # Half-time
        ht_score = {"home": state.home_score, "away": state.away_score}
        events.append({
            "minute": 45,
            "type": EventType.HALF_TIME.value,
            "team": None,
            "player": None,
            "commentary": f"Half-time: {home_team_name} {state.home_score}-{state.away_score} {away_team_name}. "
                          f"Possession: {state.possession_pct[0]:.0f}%-{state.possession_pct[1]:.0f}%"
        })

        # Half-time tactical adjustments (manager-driven)
        self._apply_halftime_adjustments(home_profile, away_profile, state, events,
                                         home_team_name, away_team_name)

        # Simulate second half
        for minute in range(46, 91):
            self._simulate_minute(minute, home_profile, away_profile, state, events,
                                  home_team_name, away_team_name)

        # Injury time
        injury_time = random.randint(1, 5)
        for minute in range(91, 91 + injury_time):
            self._simulate_minute(minute, home_profile, away_profile, state, events,
                                  home_team_name, away_team_name, injury_time=True)

        # Full-time
        events.append({
            "minute": 90 + injury_time,
            "type": EventType.FULL_TIME.value,
            "team": None,
            "player": None,
            "commentary": f"Full-time: {home_team_name} {state.home_score}-{state.away_score} {away_team_name}"
        })

        # Post-match analysis
        motm = self._calculate_motm(events, home_profile, away_profile)
        summary = self._generate_match_summary(home_team_name, away_team_name, state, events,
                                                home_profile, away_profile)
        key_moments = self._extract_key_moments(events)

        return {
            "match": f"{home_team_name} vs {away_team_name}",
            "final_score": {"home": state.home_score, "away": state.away_score},
            "half_time_score": ht_score,
            "events": events,
            "stats": {
                "possession": [round(state.possession_pct[0], 1), round(state.possession_pct[1], 1)],
                "shots": [state.shots.get("home", 0), state.shots.get("away", 0)],
                "shots_on_target": [state.shots_on_target.get("home", 0), state.shots_on_target.get("away", 0)],
                "corners": [state.corners.get("home", 0), state.corners.get("away", 0)],
                "fouls": [state.fouls.get("home", 0), state.fouls.get("away", 0)],
                "yellow_cards": [state.yellow_cards.get("home", 0), state.yellow_cards.get("away", 0)],
                "red_cards": [state.red_cards.get("home", 0), state.red_cards.get("away", 0)],
                "offsides": [state.offsides.get("home", 0), state.offsides.get("away", 0)],
                "passes": [state.passes.get("home", 0), state.passes.get("away", 0)]
            },
            "xg": [round(state.xg["home"], 2), round(state.xg["away"], 2)],
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

    def _apply_halftime_adjustments(self, home: TeamProfile, away: TeamProfile,
                                     state: GameState, events: List[Dict],
                                     home_name: str, away_name: str):
        """Manager-driven half-time tactical adjustments."""
        score_diff = state.home_score - state.away_score

        # Home team losing — manager responds
        if score_diff < 0 and home.manager.tactical_flexibility >= 7:
            if home.manager.h2h_record_style == "aggressive":
                home.attack_rating = min(95, home.attack_rating + 5)
                home.defense_rating = max(50, home.defense_rating - 3)
                events.append({
                    "minute": 45, "type": EventType.TACTICAL_CHANGE.value,
                    "team": "home", "player": home.manager.name,
                    "commentary": f"📋 {home.manager.name} makes a tactical switch at half-time, "
                                  f"pushing {home_name} into a more attacking shape."
                })
                state.tactical_changes["home"].append("More attacking shape (HT)")

        # Away team losing
        if score_diff > 0 and away.manager.tactical_flexibility >= 7:
            if away.manager.h2h_record_style in ("aggressive", "adaptive"):
                away.attack_rating = min(95, away.attack_rating + 5)
                away.defense_rating = max(50, away.defense_rating - 3)
                events.append({
                    "minute": 45, "type": EventType.TACTICAL_CHANGE.value,
                    "team": "away", "player": away.manager.name,
                    "commentary": f"📋 {away.manager.name} responds at the break, "
                                  f"pushing {away_name} forward with more urgency."
                })
                state.tactical_changes["away"].append("More attacking shape (HT)")

        # Leading team parks the bus (defensive managers)
        if score_diff > 0 and home.manager.h2h_record_style in ("neutralizer", "conservative"):
            home.defense_rating = min(95, home.defense_rating + 3)
            state.tactical_changes["home"].append("Deeper defensive block (HT)")

        if score_diff < 0 and away.manager.h2h_record_style in ("neutralizer", "conservative"):
            away.defense_rating = min(95, away.defense_rating + 3)
            state.tactical_changes["away"].append("Deeper defensive block (HT)")

    def _simulate_minute(
        self,
        minute: int,
        home: TeamProfile,
        away: TeamProfile,
        state: GameState,
        events: List[Dict],
        home_name: str,
        away_name: str,
        injury_time: bool = False
    ):
        """Simulate a single minute with full tactical intelligence."""
        score_diff_home = state.home_score - state.away_score
        score_diff_away = -score_diff_home

        # Adjusted ratings with manager influence
        home_attack = home.get_adjusted_attack(minute, score_diff_home)
        away_attack = away.get_adjusted_attack(minute, score_diff_away)
        home_defense = home.get_adjusted_defense(minute, score_diff_home)
        away_defense = away.get_adjusted_defense(minute, score_diff_away)

        # Red card impact
        if state.red_cards["home"] > 0:
            home_attack *= (0.8 ** state.red_cards["home"])
            home_defense *= (0.85 ** state.red_cards["home"])
        if state.red_cards["away"] > 0:
            away_attack *= (0.8 ** state.red_cards["away"])
            away_defense *= (0.85 ** state.red_cards["away"])

        # Possession calculation with midfield + manager style
        home_mid = home.midfield_rating
        away_mid = away.midfield_rating
        # High-pressing teams win more possession early
        if minute < 60 and home.manager.pressing_intensity == "high":
            home_mid *= 1.08
        if minute < 60 and away.manager.pressing_intensity == "high":
            away_mid *= 1.08
        total_mid = home_mid + away_mid
        if total_mid > 0:
            state.possession_pct[0] = (home_mid / total_mid) * 100
            state.possession_pct[1] = (away_mid / total_mid) * 100

        # Update passes
        state.passes["home"] += int(state.possession_pct[0] / 10)
        state.passes["away"] += int(state.possession_pct[1] / 10)

        # Who has the ball this minute
        has_possession = "home" if random.random() < state.possession_pct[0] / 100 else "away"

        # Event probabilities per minute
        base_probs = {
            EventType.GOAL: 0.028,
            EventType.SHOT_ON_TARGET: 0.07,
            EventType.SHOT_OFF_TARGET: 0.09,
            EventType.CORNER: 0.10,
            EventType.FOUL: 0.22,
            EventType.YELLOW_CARD: 0.04,
            EventType.RED_CARD: 0.002,
            EventType.INJURY: 0.008,
            EventType.VAR_CHECK: 0.004,
            EventType.PENALTY: 0.004,
            EventType.FREE_KICK_DANGEROUS: 0.035,
            EventType.OFFSIDE: 0.025
        }

        # Adjust based on who has the ball and ratings
        if has_possession == "home":
            atk_factor = home_attack / 72.0
            def_factor = 72.0 / max(30, away_defense)
            base_probs[EventType.GOAL] *= atk_factor * def_factor
            base_probs[EventType.SHOT_ON_TARGET] *= atk_factor
            base_probs[EventType.SHOT_OFF_TARGET] *= atk_factor
            # Counter-attack: defending team can still score
            if away.manager.counter_attack_tendency == "high":
                base_probs[EventType.GOAL] *= 1.12
        else:
            atk_factor = away_attack / 68.0
            def_factor = 72.0 / max(30, home_defense)
            base_probs[EventType.GOAL] *= atk_factor * def_factor
            base_probs[EventType.SHOT_ON_TARGET] *= atk_factor
            base_probs[EventType.SHOT_OFF_TARGET] *= atk_factor
            if home.manager.counter_attack_tendency == "high":
                base_probs[EventType.GOAL] *= 1.12

        # Set piece boost from manager coaching
        sp_team = home if has_possession == "home" else away
        base_probs[EventType.CORNER] *= 1.0 + (sp_team.manager.set_piece_coaching - 5) * 0.03

        # Discipline adjustments
        disc_avg = ((2 - home.discipline) + (2 - away.discipline)) / 2
        base_probs[EventType.FOUL] *= disc_avg
        base_probs[EventType.YELLOW_CARD] *= disc_avg

        # Late-game urgency
        if minute > 80 and (score_diff_home != 0):
            base_probs[EventType.GOAL] *= 1.15
            base_probs[EventType.FOUL] *= 1.2

        # Injury time scramble
        if injury_time:
            base_probs[EventType.GOAL] *= 1.3

        # Manager-driven substitutions
        self._handle_substitutions(minute, home, away, state, events, home_name, away_name,
                                   score_diff_home)

        # Generate events
        for event_type, prob in base_probs.items():
            if random.random() < prob:
                event = self._create_event(
                    minute, event_type, has_possession,
                    home, away, home_name, away_name, state, injury_time
                )
                if event:
                    events.append(event)

    def _handle_substitutions(self, minute: int, home: TeamProfile, away: TeamProfile,
                              state: GameState, events: List[Dict],
                              home_name: str, away_name: str, score_diff: int):
        """Manager-intelligence-driven substitutions using actual squad data."""
        for side, team, name in [("home", home, home_name), ("away", away, away_name)]:
            if state.substitutions[side] >= 5:  # Max 5 subs
                continue

            # Determine sub timing window based on manager style
            mgr = team.manager
            if mgr.sub_timing == "early":
                sub_window = (50, 75)
                sub_prob = 0.12
            elif mgr.sub_timing == "late":
                sub_window = (65, 85)
                sub_prob = 0.15
            else:  # normal
                sub_window = (55, 80)
                sub_prob = 0.12

            if not (sub_window[0] <= minute <= sub_window[1]):
                continue

            # Boost sub probability if losing
            sd = score_diff if side == "home" else -score_diff
            if sd < 0:
                sub_prob *= 1.5

            if random.random() < sub_prob:
                sub_event = self._create_substitution_event(minute, side, team, name, state)
                if sub_event:
                    events.append(sub_event)
                    state.substitutions[side] += 1

    def _create_substitution_event(self, minute: int, side: str, team: TeamProfile,
                                   team_name: str, state: GameState) -> Optional[Dict]:
        """Create a substitution using actual squad data."""
        # Get available subs
        already_subbed_on = [s.get("on", "") for s in state.subs_made.get(side, [])]
        available_subs = [s for s in team.subs
                          if isinstance(s, dict) and s.get("name") and s["name"] not in already_subbed_on]

        if not available_subs:
            return None

        # Pick player to come off — prefer lower-rated or fatigued
        outfield = team.get_outfield_players()
        already_subbed_off = [s.get("off", "") for s in state.subs_made.get(side, [])]
        candidates_off = [p for p in outfield if p not in already_subbed_off]

        if not candidates_off:
            return None

        # Sort by rating (lowest rated comes off first)
        def player_priority(name):
            return team.player_ratings.get(name, 6.5)

        candidates_off.sort(key=player_priority)
        off_player = candidates_off[0]

        # Pick sub — try to match position
        on_player_data = random.choice(available_subs)
        on_player = on_player_data.get("name", "Substitute")

        # Record
        state.subs_made[side].append({"off": off_player, "on": on_player, "minute": minute})

        return {
            "minute": minute,
            "type": EventType.SUBSTITUTION.value,
            "team": side,
            "player": on_player,
            "commentary": f"🔄 {minute}' — Substitution for {team_name}: "
                          f"{on_player} replaces {off_player}."
        }

    def _create_event(
        self,
        minute: int,
        event_type: EventType,
        attacking_team: str,
        home: TeamProfile,
        away: TeamProfile,
        home_name: str,
        away_name: str,
        state: GameState,
        injury_time: bool
    ) -> Optional[Dict]:
        """Create a match event using real player names and positions."""
        team_name = home_name if attacking_team == "home" else away_name
        profile = home if attacking_team == "home" else away
        opponent = away if attacking_team == "home" else home

        if event_type == EventType.GOAL:
            if random.random() > 0.7 * (1.5 if injury_time else 1.0):
                return None

            # Select scorer weighted by actual goals data
            scorer = self._pick_scorer(profile)
            assister = self._pick_assister(profile, scorer)

            if attacking_team == "home":
                state.home_score += 1
            else:
                state.away_score += 1
            state.shots_on_target[attacking_team] = state.shots_on_target.get(attacking_team, 0) + 1

            # Track xG (each goal chance worth ~0.15-0.4 xG)
            xg_val = random.uniform(0.25, 0.55)
            state.xg[attacking_team] += xg_val

            # Momentum shift after goal
            if attacking_team == "home":
                state.momentum["home"] = min(1.0, state.momentum["home"] + 0.15)
                state.momentum["away"] = max(0.0, state.momentum["away"] - 0.1)
            else:
                state.momentum["away"] = min(1.0, state.momentum["away"] + 0.15)
                state.momentum["home"] = max(0.0, state.momentum["home"] - 0.1)

            # Mental resilience: losing team recovers momentum faster if high resilience
            loser = "away" if attacking_team == "home" else "home"
            loser_team = away if attacking_team == "home" else home
            if loser_team.manager.mental_resilience >= 8:
                state.momentum[loser] = min(1.0, state.momentum[loser] + 0.08)

            score_str = f"{home_name} {state.home_score}-{state.away_score} {away_name}"
            goal_descs = [
                f"{scorer} fires home after a brilliant pass from {assister}!",
                f"{scorer} slots it into the bottom corner! Assisted by {assister}.",
                f"A thunderous strike from {scorer} leaves the keeper with no chance!",
                f"{scorer} heads home from a {assister} cross!",
                f"Clinical finish by {scorer}, set up beautifully by {assister}!",
                f"{scorer} curls one into the far corner from the edge of the box!",
                f"{scorer} taps in from close range after {assister}'s cutback!",
                f"What a goal! {scorer} picks the ball up and drives it home!",
            ]
            return {
                "minute": minute,
                "type": event_type.value,
                "team": attacking_team,
                "player": scorer,
                "assist": assister,
                "commentary": f"⚽ {minute}' — GOAL! {random.choice(goal_descs)} {score_str}"
            }

        elif event_type == EventType.SHOT_ON_TARGET:
            state.shots_on_target[attacking_team] = state.shots_on_target.get(attacking_team, 0) + 1
            state.shots[attacking_team] = state.shots.get(attacking_team, 0) + 1
            shooter = self._pick_scorer(profile)
            state.xg[attacking_team] += random.uniform(0.05, 0.2)

            save_descs = [
                f"{shooter} forces a sharp save from the goalkeeper!",
                f"{shooter}'s driven shot is palmed away!",
                f"Good effort from {shooter}, but the keeper is equal to it!",
            ]
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": shooter,
                "commentary": f"🎯 {minute}' — {random.choice(save_descs)}"
            }

        elif event_type == EventType.SHOT_OFF_TARGET:
            state.shots[attacking_team] = state.shots.get(attacking_team, 0) + 1
            shooter = self._pick_scorer(profile)
            state.xg[attacking_team] += random.uniform(0.02, 0.08)

            miss_descs = [
                f"{shooter}'s shot sails high over the crossbar.",
                f"{shooter} fires wide from a good position.",
                f"{shooter}'s effort drifts just past the post.",
            ]
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": shooter,
                "commentary": f"⚠️ {minute}' — {random.choice(miss_descs)}"
            }

        elif event_type == EventType.CORNER:
            state.corners[attacking_team] = state.corners.get(attacking_team, 0) + 1
            mids = profile.get_midfielders()
            taker = random.choice(mids) if mids else "a midfielder"
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": taker,
                "commentary": f"📐 {minute}' — Corner to {team_name}, swung in by {taker}..."
            }

        elif event_type == EventType.FOUL:
            state.fouls[attacking_team] = state.fouls.get(attacking_team, 0) + 1
            # Fouls more likely committed by defenders/midfielders
            opp_attackers = opponent.get_attackers()
            fouled = random.choice(opp_attackers) if opp_attackers else "an opponent"
            defenders = profile.get_defenders()
            fouler = random.choice(defenders) if defenders else "a defender"
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": fouler,
                "commentary": f"🚫 {minute}' — Foul by {fouler} on {fouled}."
            }

        elif event_type == EventType.YELLOW_CARD:
            if random.random() > 0.6:
                return None
            state.yellow_cards[attacking_team] = state.yellow_cards.get(attacking_team, 0) + 1
            all_players = profile.get_outfield_players()
            player = random.choice(all_players) if all_players else f"{team_name} Player"
            self.card_recipients[attacking_team].append(player)

            card_descs = [
                f"{player} receives a yellow card for a late challenge.",
                f"Booking for {player} — cynical foul to stop the counter.",
                f"Yellow card shown to {player} for dissent.",
            ]
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": player,
                "commentary": f"🟨 {minute}' — {random.choice(card_descs)}"
            }

        elif event_type == EventType.RED_CARD:
            if random.random() > 0.15:
                return None
            state.red_cards[attacking_team] = state.red_cards.get(attacking_team, 0) + 1
            all_players = profile.get_outfield_players()
            # Second yellow more likely for already-booked players
            booked = [p for p in self.card_recipients.get(attacking_team, []) if p in all_players]
            if booked and random.random() < 0.7:
                player = random.choice(booked)
                desc = f"Second yellow for {player} — he's off!"
            else:
                player = random.choice(all_players) if all_players else f"{team_name} Player"
                desc = f"{player} sees a straight red for a dangerous tackle!"
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": player,
                "commentary": f"🔴 {minute}' — {desc}"
            }

        elif event_type == EventType.INJURY:
            all_players = profile.get_outfield_players()
            player = random.choice(all_players) if all_players else f"{team_name} Player"
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": player,
                "commentary": f"🏥 {minute}' — {player} is down and receiving treatment."
            }

        elif event_type == EventType.VAR_CHECK:
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": None,
                "commentary": f"📹 {minute}' — VAR review in progress..."
            }

        elif event_type == EventType.PENALTY:
            if random.random() > 0.5:
                return None
            taker = profile.get_best_scorer()
            scored = random.random() < 0.78  # 78% conversion rate
            state.shots_on_target[attacking_team] = state.shots_on_target.get(attacking_team, 0) + 1
            state.xg[attacking_team] += 0.76  # Penalty xG

            if scored:
                if attacking_team == "home":
                    state.home_score += 1
                else:
                    state.away_score += 1
                score_str = f"{home_name} {state.home_score}-{state.away_score} {away_name}"
                return {
                    "minute": minute, "type": event_type.value,
                    "team": attacking_team, "player": taker,
                    "commentary": f"⚽ {minute}' — PENALTY SCORED! {taker} sends the keeper the wrong way! {score_str}"
                }
            else:
                return {
                    "minute": minute, "type": event_type.value,
                    "team": attacking_team, "player": taker,
                    "commentary": f"❌ {minute}' — PENALTY SAVED! {taker}'s spot kick is denied by the goalkeeper!"
                }

        elif event_type == EventType.FREE_KICK_DANGEROUS:
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": None,
                "commentary": f"⚡ {minute}' — Dangerous free kick to {team_name} in a promising area."
            }

        elif event_type == EventType.OFFSIDE:
            state.offsides[attacking_team] = state.offsides.get(attacking_team, 0) + 1
            attackers = profile.get_attackers()
            player = random.choice(attackers) if attackers else f"{team_name} Forward"
            return {
                "minute": minute, "type": event_type.value,
                "team": attacking_team, "player": player,
                "commentary": f"🚩 {minute}' — {player} caught in an offside position."
            }

        return None

    def _pick_scorer(self, profile: TeamProfile) -> str:
        """Pick a goal scorer weighted by actual scoring data."""
        # Use top scorers data if available
        if profile.top_scorers:
            weights = []
            names = []
            for s in profile.top_scorers[:5]:
                if isinstance(s, dict):
                    goals = self._safe_float(s.get("goals", 1))
                    names.append(s.get("name", "Forward"))
                    weights.append(max(1, goals))
            if names:
                return random.choices(names, weights=weights, k=1)[0]

        # Fallback to attackers
        attackers = profile.get_attackers()
        if attackers:
            return random.choice(attackers)
        outfield = profile.get_outfield_players()
        return random.choice(outfield) if outfield else f"{profile.name} Forward"

    def _pick_assister(self, profile: TeamProfile, scorer: str) -> str:
        """Pick an assist provider (not the scorer)."""
        outfield = profile.get_outfield_players()
        candidates = [p for p in outfield if p != scorer]
        if candidates:
            # Weight by rating — higher-rated players assist more
            weights = [profile.player_ratings.get(p, 6.5) for p in candidates]
            return random.choices(candidates, weights=weights, k=1)[0]
        return "a teammate"

    def _calculate_motm(self, events: List[Dict], home: TeamProfile, away: TeamProfile) -> str:
        """Calculate Man of the Match based on goals, assists, and ratings."""
        scores = {}
        for event in events:
            if event["type"] == EventType.GOAL.value and event.get("player"):
                p = event["player"]
                scores[p] = scores.get(p, 0) + 3
                if event.get("assist"):
                    a = event["assist"]
                    scores[a] = scores.get(a, 0) + 1.5

        # Add rating bonuses
        for name, rating in {**home.player_ratings, **away.player_ratings}.items():
            scores[name] = scores.get(name, 0) + (rating - 6.5)

        if scores:
            return max(scores, key=scores.get)

        all_players = home.get_outfield_players() + away.get_outfield_players()
        return random.choice(all_players) if all_players else "Star Player"

    def _generate_match_summary(self, home: str, away: str, state: GameState,
                                 events: List[Dict], home_p: TeamProfile, away_p: TeamProfile) -> str:
        """Generate a tactical match summary using manager intelligence."""
        hs, aws = state.home_score, state.away_score

        # Count goals
        goal_events = [e for e in events if e["type"] == EventType.GOAL.value]
        scorers_home = [e["player"] for e in goal_events if e.get("team") == "home"]
        scorers_away = [e["player"] for e in goal_events if e.get("team") == "away"]

        if hs == aws:
            result_line = f"{home} {hs}-{aws} {away} — a hard-fought draw."
        elif hs > aws:
            result_line = f"{home} {hs}-{aws} {away} — victory for the hosts."
        else:
            result_line = f"{home} {hs}-{aws} {away} — the visitors take the three points."

        # Tactical context
        poss = state.possession_pct
        dom = home if poss[0] > 55 else (away if poss[1] > 55 else "neither side")
        dom_name = home if poss[0] > 55 else (away if poss[1] > 55 else "")

        parts = [result_line]

        if dom_name:
            parts.append(f"{dom_name} dominated possession ({poss[0]:.0f}%-{poss[1]:.0f}%).")

        # Manager mention
        if hs > aws:
            parts.append(f"{home_p.manager.name}'s {home_p.manager.pressing_intensity}-pressing "
                         f"approach proved effective.")
        elif aws > hs:
            parts.append(f"{away_p.manager.name}'s game plan paid dividends on the road.")

        # Scorers
        if scorers_home:
            from collections import Counter
            sc = Counter(scorers_home)
            scorer_strs = [f"{n} ({c}x)" if c > 1 else n for n, c in sc.items()]
            parts.append(f"Goals for {home}: {', '.join(scorer_strs)}.")
        if scorers_away:
            from collections import Counter
            sc = Counter(scorers_away)
            scorer_strs = [f"{n} ({c}x)" if c > 1 else n for n, c in sc.items()]
            parts.append(f"Goals for {away}: {', '.join(scorer_strs)}.")

        # xG
        parts.append(f"xG: {home} {state.xg['home']:.2f} - {state.xg['away']:.2f} {away}.")

        return " ".join(parts)

    def _extract_key_moments(self, events: List[Dict]) -> List[str]:
        """Extract key moments from events."""
        key_types = {EventType.GOAL.value, EventType.RED_CARD.value,
                     EventType.PENALTY.value, EventType.TACTICAL_CHANGE.value}
        moments = []
        for event in events:
            if event["type"] in key_types:
                moment = f"{event['minute']}' {event['type'].replace('_', ' ').title()}"
                if event.get("player"):
                    moment += f" - {event['player']}"
                moments.append(moment)
        return moments[:8]
