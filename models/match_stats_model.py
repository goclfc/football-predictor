"""
Match Stats Model — Empirical stat predictions from 4,888 match analysis.

Encodes every finding from match_stats_deep_analysis.py into usable
prediction adjustments for corners, cards, fouls, shots, SOT.

Key relationships discovered:
- Shots → Corners (r=+0.33), Shots → Goals (r=+0.26), SOT → Goals (r=+0.56)
- Fouls → Cards (r=+0.38), Cards → Reds (r=+0.40)
- Corners → Goals (r=-0.02, essentially zero)
- Goal difference → fewer cards/fouls (blowouts are calmer)
- Winners: 1.24x more shots, 1.68x more SOT, 0.87x cards vs losers
- Tight matches (GD≤1): +10-15% more cards than blowouts (GD≥3)
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
# 1. LEAGUE STAT BASELINES (from 4,888 matches)
# ═══════════════════════════════════════════════════════════════════════

LEAGUE_STAT_BASELINES = {
    "Premier League": {
        "avg_corners": 10.4, "avg_cards": 4.1, "avg_fouls": 22.8,
        "avg_shots": 25.8, "avg_sot": 8.8, "avg_reds": 0.19,
        "avg_goals": 2.82,
        "shot_accuracy": 0.349, "conversion_rate": 0.115, "sot_goal_rate": 0.328,
        "shots_per_goal": 8.7, "sot_per_goal": 3.0,
        "home_corners": 5.8, "away_corners": 4.6,
        "home_shots": 14.1, "away_shots": 11.7,
        "home_fouls": 11.1, "away_fouls": 11.7,
        "home_cards": 1.9, "away_cards": 2.2,
    },
    "La Liga": {
        "avg_corners": 9.5, "avg_cards": 4.8, "avg_fouls": 25.2,
        "avg_shots": 24.4, "avg_sot": 8.4, "avg_reds": 0.20,
        "avg_goals": 2.64,
        "shot_accuracy": 0.348, "conversion_rate": 0.109, "sot_goal_rate": 0.313,
        "shots_per_goal": 9.2, "sot_per_goal": 3.2,
        "home_corners": 5.2, "away_corners": 4.3,
        "home_shots": 13.4, "away_shots": 11.0,
        "home_fouls": 12.4, "away_fouls": 12.8,
        "home_cards": 2.2, "away_cards": 2.6,
    },
    "Bundesliga": {
        "avg_corners": 9.7, "avg_cards": 4.1, "avg_fouls": 21.8,
        "avg_shots": 25.6, "avg_sot": 9.1, "avg_reds": 0.18,
        "avg_goals": 3.08,
        "shot_accuracy": 0.360, "conversion_rate": 0.121, "sot_goal_rate": 0.336,
        "shots_per_goal": 8.3, "sot_per_goal": 3.0,
        "home_corners": 5.3, "away_corners": 4.4,
        "home_shots": 14.2, "away_shots": 11.4,
        "home_fouls": 10.6, "away_fouls": 11.2,
        "home_cards": 1.9, "away_cards": 2.2,
    },
    "Serie A": {
        "avg_corners": 9.3, "avg_cards": 4.2, "avg_fouls": 24.8,
        "avg_shots": 24.2, "avg_sot": 7.8, "avg_reds": 0.18,
        "avg_goals": 2.58,
        "shot_accuracy": 0.329, "conversion_rate": 0.103, "sot_goal_rate": 0.312,
        "shots_per_goal": 9.7, "sot_per_goal": 3.2,
        "home_corners": 5.1, "away_corners": 4.2,
        "home_shots": 13.2, "away_shots": 11.0,
        "home_fouls": 12.1, "away_fouls": 12.7,
        "home_cards": 1.9, "away_cards": 2.3,
    },
    "Ligue 1": {
        "avg_corners": 9.4, "avg_cards": 4.1, "avg_fouls": 24.5,
        "avg_shots": 24.2, "avg_sot": 8.6, "avg_reds": 0.17,
        "avg_goals": 2.78,
        "shot_accuracy": 0.361, "conversion_rate": 0.113, "sot_goal_rate": 0.313,
        "shots_per_goal": 8.8, "sot_per_goal": 3.2,
        "home_corners": 5.1, "away_corners": 4.3,
        "home_shots": 13.3, "away_shots": 10.9,
        "home_fouls": 12.0, "away_fouls": 12.5,
        "home_cards": 1.9, "away_cards": 2.2,
    },
}

# ═══════════════════════════════════════════════════════════════════════
# 2. HALFTIME SCORE → SECOND HALF STAT ADJUSTMENTS
# ═══════════════════════════════════════════════════════════════════════

# Multipliers relative to level-game (0-0 at HT) baseline
HT_SCORE_STAT_ADJUSTMENTS = {
    # ht_diff: {stat: multiplier}  (positive = home leading)
    -3: {"2h_goals": 1.16, "corners": 0.99, "cards": 0.89, "fouls": 0.97, "shots": 1.08},
    -2: {"2h_goals": 1.07, "corners": 1.00, "cards": 0.93, "fouls": 0.95, "shots": 1.07},
    -1: {"2h_goals": 1.08, "corners": 1.04, "cards": 1.00, "fouls": 0.99, "shots": 1.05},
     0: {"2h_goals": 1.00, "corners": 1.00, "cards": 1.00, "fouls": 1.00, "shots": 1.00},
     1: {"2h_goals": 1.05, "corners": 1.00, "cards": 0.98, "fouls": 0.99, "shots": 1.02},
     2: {"2h_goals": 1.12, "corners": 0.96, "cards": 0.86, "fouls": 0.97, "shots": 1.04},
     3: {"2h_goals": 1.11, "corners": 0.98, "cards": 0.73, "fouls": 0.93, "shots": 1.09},
}

# HT score → full match stat profiles
HT_SCORE_PROFILES = {
    "0-0": {"ft_goals": 1.47, "corners": 9.7, "cards": 4.3, "fouls": 24.0, "hw%": 34.7, "o25%": 17.3, "btts%": 26.8},
    "1-0": {"ft_goals": 2.59, "corners": 9.6, "cards": 4.2, "fouls": 23.7, "hw%": 68.8, "o25%": 47.8, "btts%": 51.2},
    "0-1": {"ft_goals": 2.63, "corners": 10.0, "cards": 4.4, "fouls": 23.9, "hw%": 13.3, "o25%": 49.2, "btts%": 58.1},
    "1-1": {"ft_goals": 3.57, "corners": 9.6, "cards": 4.6, "fouls": 23.9, "hw%": 39.2, "o25%": 80.2, "btts%": 100.0},
    "2-0": {"ft_goals": 3.70, "corners": 9.2, "cards": 3.8, "fouls": 23.3, "hw%": 92.6, "o25%": 84.1, "btts%": 48.9},
    "0-2": {"ft_goals": 3.61, "corners": 9.7, "cards": 4.2, "fouls": 23.1, "hw%": 3.5, "o25%": 80.3, "btts%": 48.5},
    "2-1": {"ft_goals": 4.59, "corners": 9.8, "cards": 4.6, "fouls": 23.3, "hw%": 65.2, "o25%": 100.0, "btts%": 100.0},
    "1-2": {"ft_goals": 4.67, "corners": 9.8, "cards": 4.6, "fouls": 23.5, "hw%": 19.7, "o25%": 100.0, "btts%": 100.0},
    "2-2": {"ft_goals": 5.98, "corners": 8.7, "cards": 4.6, "fouls": 23.9, "hw%": 38.8, "o25%": 100.0, "btts%": 100.0},
    "3-0": {"ft_goals": 4.66, "corners": 9.3, "cards": 3.2, "fouls": 22.4, "hw%": 97.4, "o25%": 100.0, "btts%": 44.2},
    "0-3": {"ft_goals": 4.73, "corners": 9.3, "cards": 3.9, "fouls": 23.2, "hw%": 2.0, "o25%": 100.0, "btts%": 53.1},
}

# ═══════════════════════════════════════════════════════════════════════
# 3. POSITION MATCHUP → STAT PROFILES
# ═══════════════════════════════════════════════════════════════════════

POSITION_MATCHUP_STATS = {
    # (home_pos, away_pos): {stat adjustments as multipliers vs league avg}
    ("top3", "relegation"):    {"goals": 1.19, "corners": 1.07, "cards": 0.83, "fouls": 0.91, "shots": 1.06, "hw%": 75.0},
    ("top3", "top3"):          {"goals": 1.22, "corners": 0.90, "cards": 0.90, "fouls": 0.95, "shots": 1.04, "hw%": 46.2},
    ("top3", "upper_mid"):     {"goals": 1.15, "corners": 1.01, "cards": 0.90, "fouls": 0.90, "shots": 1.08, "hw%": 72.2},
    ("top3", "lower_mid"):     {"goals": 1.17, "corners": 1.00, "cards": 0.85, "fouls": 0.89, "shots": 1.03, "hw%": 71.5},
    ("cl_spots", "cl_spots"):  {"goals": 1.04, "corners": 0.96, "cards": 1.12, "fouls": 0.97, "shots": 0.99, "hw%": 44.2},
    ("cl_spots", "relegation"): {"goals": 1.12, "corners": 1.02, "cards": 0.98, "fouls": 0.95, "shots": 1.06, "hw%": 66.5},
    ("upper_mid", "upper_mid"): {"goals": 0.99, "corners": 1.00, "cards": 1.12, "fouls": 0.99, "shots": 0.98, "hw%": 42.5},
    ("lower_mid", "lower_mid"): {"goals": 0.93, "corners": 1.01, "cards": 1.00, "fouls": 1.01, "shots": 0.99, "hw%": 42.5},
    ("relegation", "relegation"): {"goals": 0.97, "corners": 1.00, "cards": 1.10, "fouls": 1.08, "shots": 0.99, "hw%": 39.6},
    ("relegation", "top3"):    {"goals": 1.05, "corners": 1.00, "cards": 0.88, "fouls": 0.92, "shots": 1.03, "hw%": 10.7},
    ("upper_mid", "relegation"): {"goals": 1.01, "corners": 1.00, "cards": 1.02, "fouls": 1.00, "shots": 1.02, "hw%": 51.6},
    ("lower_mid", "top3"):     {"goals": 1.12, "corners": 1.02, "cards": 1.05, "fouls": 0.93, "shots": 1.02, "hw%": 21.7},
}

# ═══════════════════════════════════════════════════════════════════════
# 4. GOAL DIFFERENCE → STAT ADJUSTMENTS
# ═══════════════════════════════════════════════════════════════════════

# How stats change with blowout vs tight match (relative to GD=1 baseline)
GOAL_DIFF_ADJUSTMENTS = {
    0: {"corners": 1.00, "cards": 1.05, "fouls": 1.02, "shots": 0.97, "reds": 0.81},
    1: {"corners": 1.00, "cards": 1.10, "fouls": 1.04, "shots": 0.97, "reds": 1.00},
    2: {"corners": 1.00, "cards": 0.95, "fouls": 0.98, "shots": 1.00, "reds": 1.00},
    3: {"corners": 0.97, "cards": 0.86, "fouls": 0.97, "shots": 1.01, "reds": 0.81},
    4: {"corners": 0.97, "cards": 0.76, "fouls": 0.91, "shots": 1.03, "reds": 0.81},
    5: {"corners": 0.89, "cards": 0.71, "fouls": 0.85, "shots": 1.07, "reds": 0.62},
}

# ═══════════════════════════════════════════════════════════════════════
# 5. SHOTS → STAT CHAIN PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════

# Given total match shots, predict other stats
SHOTS_TO_STATS = {
    # shots_range: (goals, corners, cards, sot, o25%, btts%)
    (10, 14): {"goals": 1.57, "corners": 7.2, "cards": 4.3, "sot": 4.9, "o25": 0.223, "btts": 0.255},
    (15, 19): {"goals": 2.13, "corners": 8.2, "cards": 4.6, "sot": 6.2, "o25": 0.365, "btts": 0.414},
    (20, 24): {"goals": 2.63, "corners": 9.0, "cards": 4.3, "sot": 7.8, "o25": 0.498, "btts": 0.492},
    (25, 29): {"goals": 3.00, "corners": 10.1, "cards": 4.3, "sot": 9.4, "o25": 0.585, "btts": 0.601},
    (30, 34): {"goals": 3.31, "corners": 10.6, "cards": 4.1, "sot": 10.8, "o25": 0.634, "btts": 0.633},
    (35, 39): {"goals": 3.63, "corners": 11.9, "cards": 4.3, "sot": 12.7, "o25": 0.722, "btts": 0.714},
    (40, 44): {"goals": 3.47, "corners": 12.6, "cards": 3.8, "sot": 14.1, "o25": 0.727, "btts": 0.727},
}

# ═══════════════════════════════════════════════════════════════════════
# 6. FOULS → CARDS CHAIN
# ═══════════════════════════════════════════════════════════════════════

FOULS_TO_CARDS = {
    (10, 14): {"cards": 2.6, "reds": 0.12, "goals": 3.13},
    (15, 19): {"cards": 3.2, "reds": 0.14, "goals": 3.11},
    (20, 24): {"cards": 4.1, "reds": 0.19, "goals": 2.80},
    (25, 29): {"cards": 4.8, "reds": 0.22, "goals": 2.76},
    (30, 34): {"cards": 5.4, "reds": 0.25, "goals": 2.50},
    (35, 39): {"cards": 5.8, "reds": 0.22, "goals": 2.60},
}

# ═══════════════════════════════════════════════════════════════════════
# 7. WINNER vs LOSER STAT RATIOS
# ═══════════════════════════════════════════════════════════════════════

RESULT_STAT_RATIOS = {
    # stat: (winner_avg, loser_avg, ratio)
    "corners": (4.97, 4.66, 1.07),
    "shots":   (14.10, 11.33, 1.24),
    "sot":     (5.66, 3.37, 1.68),
    "fouls":   (11.64, 11.89, 0.98),
    "cards":   (1.96, 2.25, 0.87),
}

# Home vs Away stat splits by result
RESULT_HOME_AWAY_STATS = {
    "home_win":  {"h_corn": 5.3, "a_corn": 4.2, "h_shots": 15.0, "a_shots": 10.4, "h_fouls": 11.5, "a_fouls": 12.0, "h_cards": 1.8, "a_cards": 2.4, "h_sot": 5.9, "a_sot": 3.1},
    "draw":      {"h_corn": 5.4, "a_corn": 4.3, "h_shots": 13.7, "a_shots": 11.3, "h_fouls": 11.8, "a_fouls": 12.3, "h_cards": 2.1, "a_cards": 2.3, "h_sot": 4.4, "a_sot": 3.8},
    "away_win":  {"h_corn": 5.3, "a_corn": 4.5, "h_shots": 12.6, "a_shots": 12.9, "h_fouls": 11.7, "a_fouls": 11.8, "h_cards": 2.1, "a_cards": 2.1, "h_sot": 3.7, "a_sot": 5.3},
}

# ═══════════════════════════════════════════════════════════════════════
# 8. CORNER & CARD OVER/UNDER PROBABILITIES BY LEAGUE
# ═══════════════════════════════════════════════════════════════════════

CORNER_OU_PROBS = {
    "Premier League": {7.5: 0.787, 8.5: 0.706, 9.5: 0.594, 10.5: 0.484, 11.5: 0.345, 12.5: 0.262},
    "La Liga":        {7.5: 0.721, 8.5: 0.594, 9.5: 0.463, 10.5: 0.361, 11.5: 0.257, 12.5: 0.167},
    "Bundesliga":     {7.5: 0.732, 8.5: 0.612, 9.5: 0.508, 10.5: 0.389, 11.5: 0.288, 12.5: 0.205},
    "Serie A":        {7.5: 0.683, 8.5: 0.566, 9.5: 0.458, 10.5: 0.346, 11.5: 0.235, 12.5: 0.165},
    "Ligue 1":        {7.5: 0.684, 8.5: 0.566, 9.5: 0.446, 10.5: 0.340, 11.5: 0.248, 12.5: 0.178},
}

CARD_OU_PROBS = {
    "Premier League": {2.5: 0.764, 3.5: 0.599, 4.5: 0.414, 5.5: 0.239, 6.5: 0.127},
    "La Liga":        {2.5: 0.820, 3.5: 0.670, 4.5: 0.506, 5.5: 0.346, 6.5: 0.230},
    "Bundesliga":     {2.5: 0.750, 3.5: 0.577, 4.5: 0.398, 5.5: 0.250, 6.5: 0.156},
    "Serie A":        {2.5: 0.789, 3.5: 0.598, 4.5: 0.406, 5.5: 0.241, 6.5: 0.133},
    "Ligue 1":        {2.5: 0.782, 3.5: 0.584, 4.5: 0.384, 5.5: 0.205, 6.5: 0.115},
}

# ═══════════════════════════════════════════════════════════════════════
# 9. MATCH PROFILE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════

MATCH_PROFILES = {
    "low_scoring":  {"goals": (0, 1), "corners": 9.7, "cards": 4.4, "fouls": 24.5, "shots": 23.2, "sot": 6.6, "btts": 0.0},
    "average":      {"goals": (2, 2), "corners": 9.8, "cards": 4.2, "fouls": 23.8, "shots": 24.7, "sot": 8.0, "btts": 0.50},
    "moderate":     {"goals": (3, 3), "corners": 9.6, "cards": 4.3, "fouls": 24.0, "shots": 25.4, "sot": 9.0, "btts": 0.697},
    "high_scoring": {"goals": (4, 4), "corners": 9.6, "cards": 4.2, "fouls": 22.9, "shots": 26.5, "sot": 10.0, "btts": 0.837},
    "thriller":     {"goals": (5, 99), "corners": 9.5, "cards": 4.2, "fouls": 22.8, "shots": 27.9, "sot": 11.8, "btts": 0.898},
}

# ═══════════════════════════════════════════════════════════════════════
# 10. LEAGUE-SPECIFIC CONDITION ADJUSTMENTS
# ═══════════════════════════════════════════════════════════════════════

# For each league: tight match stats vs blowout, and 0-0 HT → 2H stats
LEAGUE_CONDITION_PROFILES = {
    "Premier League": {
        "tight":   {"corners": 10.6, "cards": 4.4, "fouls": 22.4, "shots": 26.1},
        "blowout": {"corners": 10.2, "cards": 3.5, "fouls": 21.4, "shots": 26.3},
        "top3_home_goals": 3.03,
        "bottom5_home_goals": 2.95,
        "ht00_2h_goals": 1.72,
        "ht00_corners": 10.6,
    },
    "La Liga": {
        "tight":   {"corners": 9.5, "cards": 5.1, "fouls": 25.8, "shots": 24.1},
        "blowout": {"corners": 9.5, "cards": 3.9, "fouls": 23.6, "shots": 25.3},
        "top3_home_goals": 3.40,
        "bottom5_home_goals": 2.35,
        "ht00_2h_goals": 1.43,
        "ht00_corners": 9.5,
    },
    "Bundesliga": {
        "tight":   {"corners": 9.8, "cards": 4.5, "fouls": 22.4, "shots": 26.1},
        "blowout": {"corners": 9.1, "cards": 3.2, "fouls": 20.1, "shots": 27.2},
        "top3_home_goals": 3.71,
        "bottom5_home_goals": 3.15,
        "ht00_2h_goals": 1.45,
        "ht00_corners": 9.9,
    },
    "Serie A": {
        "tight":   {"corners": 9.4, "cards": 4.4, "fouls": 25.3, "shots": 24.5},
        "blowout": {"corners": 8.6, "cards": 3.3, "fouls": 22.7, "shots": 26.0},
        "top3_home_goals": 2.76,
        "bottom5_home_goals": 2.52,
        "ht00_2h_goals": 1.35,
        "ht00_corners": 9.2,
    },
    "Ligue 1": {
        "tight":   {"corners": 9.6, "cards": 4.3, "fouls": 24.9, "shots": 24.4},
        "blowout": {"corners": 8.8, "cards": 3.3, "fouls": 23.9, "shots": 26.1},
        "top3_home_goals": 3.19,
        "bottom5_home_goals": 2.98,
        "ht00_2h_goals": 1.44,
        "ht00_corners": 9.5,
    },
}

# ═══════════════════════════════════════════════════════════════════════
# 11. CORRELATION COEFFICIENTS (for weighting predictions)
# ═══════════════════════════════════════════════════════════════════════

STAT_CORRELATIONS = {
    ("shots", "corners"):  +0.330,
    ("shots", "goals"):    +0.264,
    ("sot", "goals"):      +0.557,
    ("fouls", "cards"):    +0.375,
    ("cards", "reds"):     +0.397,
    ("fouls", "corners"):  -0.162,
    ("corners", "goals"):  -0.020,
    ("cards", "goals"):    -0.028,
    ("abs_gd", "cards"):   -0.164,
    ("abs_gd", "fouls"):   -0.139,
    ("abs_gd", "corners"): -0.045,
    ("abs_gd", "shots"):   +0.083,
    ("shots", "sot"):      +0.616,
}


# ═══════════════════════════════════════════════════════════════════════
# MAIN PREDICTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MatchStatsPrediction:
    """Full stat prediction for a match."""
    corners: float = 0.0
    home_corners: float = 0.0
    away_corners: float = 0.0
    cards: float = 0.0
    home_cards: float = 0.0
    away_cards: float = 0.0
    fouls: float = 0.0
    shots: float = 0.0
    sot: float = 0.0
    reds: float = 0.0
    # Over/under probabilities
    corner_ou: Dict[float, float] = field(default_factory=dict)  # line: over_prob
    card_ou: Dict[float, float] = field(default_factory=dict)
    # Match profile
    expected_profile: str = ""
    confidence: float = 0.0
    notes: list = field(default_factory=list)


def get_position_category(position: int, total_teams: int = 20) -> str:
    """Convert league position to category."""
    if position <= 3:
        return "top3"
    elif position <= 6:
        return "cl_spots"
    elif position <= 10:
        return "upper_mid"
    elif position <= total_teams - 5:
        return "lower_mid"
    else:
        return "relegation"


def predict_match_stats(
    league: str,
    home_shots_avg: float = None,
    away_shots_avg: float = None,
    home_fouls_avg: float = None,
    away_fouls_avg: float = None,
    home_position: int = None,
    away_position: int = None,
    expected_goals: float = None,
    expected_gd: float = None,
    ht_score: str = None,
    total_teams: int = 20,
) -> MatchStatsPrediction:
    """
    Predict all match stats using empirical data chains.

    Uses multiple evidence sources and weights by correlation strength:
    1. League baseline (always)
    2. Shot-based chain (if shot data available) — r=+0.33 for corners
    3. Foul-based chain (if foul data available) — r=+0.38 for cards
    4. Position matchup adjustment
    5. Expected goal difference adjustment (tight vs blowout)
    6. HT score adjustment (if in-play)
    """
    pred = MatchStatsPrediction()
    baseline = LEAGUE_STAT_BASELINES.get(league, LEAGUE_STAT_BASELINES["Premier League"])

    # Start with league baselines
    pred.corners = baseline["avg_corners"]
    pred.home_corners = baseline["home_corners"]
    pred.away_corners = baseline["away_corners"]
    pred.cards = baseline["avg_cards"]
    pred.home_cards = baseline["home_cards"]
    pred.away_cards = baseline["away_cards"]
    pred.fouls = baseline["avg_fouls"]
    pred.shots = baseline["avg_shots"]
    pred.sot = baseline["avg_sot"]
    pred.reds = baseline["avg_reds"]

    # --- Shot-based chain adjustments ---
    if home_shots_avg is not None and away_shots_avg is not None:
        total_shots = home_shots_avg + away_shots_avg
        # Find matching shot range
        for (lo, hi), stats in SHOTS_TO_STATS.items():
            if lo <= total_shots <= hi:
                # Blend: 60% shot-chain, 40% baseline (weighted by correlation strength)
                pred.corners = 0.6 * stats["corners"] + 0.4 * pred.corners
                pred.sot = 0.6 * stats["sot"] + 0.4 * pred.sot
                pred.notes.append(f"Shot chain ({total_shots:.0f} shots): corners→{stats['corners']:.1f}")
                break

        # Adjust home/away split based on shot ratio
        if total_shots > 0:
            home_ratio = home_shots_avg / total_shots
            pred.home_corners = pred.corners * (0.3 + 0.4 * home_ratio)  # home bias
            pred.away_corners = pred.corners - pred.home_corners
            pred.shots = total_shots

    # --- Foul-based chain adjustments ---
    if home_fouls_avg is not None and away_fouls_avg is not None:
        total_fouls = home_fouls_avg + away_fouls_avg
        for (lo, hi), stats in FOULS_TO_CARDS.items():
            if lo <= total_fouls <= hi:
                pred.cards = 0.65 * stats["cards"] + 0.35 * pred.cards
                pred.reds = 0.65 * stats["reds"] + 0.35 * pred.reds
                pred.fouls = total_fouls
                pred.notes.append(f"Foul chain ({total_fouls:.0f} fouls): cards→{stats['cards']:.1f}")
                break

        if total_fouls > 0:
            home_foul_ratio = home_fouls_avg / total_fouls
            pred.home_cards = pred.cards * home_foul_ratio
            pred.away_cards = pred.cards - pred.home_cards

    # --- Position matchup adjustment ---
    if home_position is not None and away_position is not None:
        h_cat = get_position_category(home_position, total_teams)
        a_cat = get_position_category(away_position, total_teams)
        matchup = POSITION_MATCHUP_STATS.get((h_cat, a_cat))
        if matchup:
            pred.corners *= matchup.get("corners", 1.0)
            pred.cards *= matchup.get("cards", 1.0)
            pred.fouls *= matchup.get("fouls", 1.0) if "fouls" in matchup else 1.0
            pred.shots *= matchup.get("shots", 1.0)
            pred.notes.append(f"Position: {h_cat} vs {a_cat} (HW%={matchup.get('hw%', '?')})")

    # --- Expected goal difference adjustment ---
    if expected_gd is not None:
        abs_gd = min(int(abs(expected_gd) + 0.5), 5)
        gd_adj = GOAL_DIFF_ADJUSTMENTS.get(abs_gd, GOAL_DIFF_ADJUSTMENTS[1])
        pred.cards *= gd_adj["cards"]
        pred.fouls *= gd_adj["fouls"]
        pred.reds *= gd_adj["reds"]
        if abs_gd >= 3:
            pred.notes.append(f"Blowout expected (GD~{abs_gd}): cards ×{gd_adj['cards']:.2f}")

    # --- HT score in-play adjustment ---
    if ht_score is not None:
        ht_profile = HT_SCORE_PROFILES.get(ht_score)
        if ht_profile:
            # Strong override — we have actual HT data
            pred.corners = 0.7 * ht_profile["corners"] + 0.3 * pred.corners
            pred.cards = 0.7 * ht_profile["cards"] + 0.3 * pred.cards
            pred.fouls = 0.7 * ht_profile["fouls"] + 0.3 * pred.fouls
            pred.notes.append(f"HT {ht_score}: corners→{ht_profile['corners']:.1f}, cards→{ht_profile['cards']:.1f}")

    # --- Determine match profile ---
    if expected_goals is not None:
        if expected_goals < 1.8:
            pred.expected_profile = "low_scoring"
        elif expected_goals < 2.5:
            pred.expected_profile = "average"
        elif expected_goals < 3.2:
            pred.expected_profile = "moderate"
        elif expected_goals < 4.0:
            pred.expected_profile = "high_scoring"
        else:
            pred.expected_profile = "thriller"

    # --- Generate O/U probabilities ---
    corner_base = CORNER_OU_PROBS.get(league, CORNER_OU_PROBS["Premier League"])
    card_base = CARD_OU_PROBS.get(league, CARD_OU_PROBS["Premier League"])

    # Shift O/U probabilities based on our predicted total vs league avg
    corner_shift = (pred.corners - baseline["avg_corners"]) / baseline["avg_corners"]
    card_shift = (pred.cards - baseline["avg_cards"]) / baseline["avg_cards"]

    for line, base_prob in corner_base.items():
        # Positive shift = more corners = higher over probability
        adjusted = base_prob * (1 + corner_shift * 0.5)
        pred.corner_ou[line] = max(0.05, min(0.95, adjusted))

    for line, base_prob in card_base.items():
        adjusted = base_prob * (1 + card_shift * 0.5)
        pred.card_ou[line] = max(0.05, min(0.95, adjusted))

    # --- Confidence ---
    evidence_count = sum([
        home_shots_avg is not None,
        home_fouls_avg is not None,
        home_position is not None,
        expected_goals is not None,
        ht_score is not None,
    ])
    pred.confidence = min(0.95, 0.5 + evidence_count * 0.1)

    # Round everything
    pred.corners = round(pred.corners, 1)
    pred.home_corners = round(pred.home_corners, 1)
    pred.away_corners = round(pred.away_corners, 1)
    pred.cards = round(pred.cards, 1)
    pred.home_cards = round(pred.home_cards, 1)
    pred.away_cards = round(pred.away_cards, 1)
    pred.fouls = round(pred.fouls, 1)
    pred.shots = round(pred.shots, 1)
    pred.sot = round(pred.sot, 1)
    pred.reds = round(pred.reds, 2)

    return pred


def predict_live_stats(
    league: str,
    minute: int,
    ht_score: str,
    current_corners: int = 0,
    current_cards: int = 0,
    current_fouls: int = 0,
    current_shots: int = 0,
) -> Dict:
    """
    Predict remaining stats for live in-play markets.
    Uses current pace + HT profile to project final totals.
    """
    baseline = LEAGUE_STAT_BASELINES.get(league, LEAGUE_STAT_BASELINES["Premier League"])
    ht_profile = HT_SCORE_PROFILES.get(ht_score)

    # Time fraction elapsed (roughly)
    fraction_elapsed = min(minute / 90.0, 1.0)
    fraction_remaining = 1.0 - fraction_elapsed

    # Current pace
    if fraction_elapsed > 0.1:
        pace_corners = current_corners / fraction_elapsed
        pace_cards = current_cards / fraction_elapsed
        pace_fouls = current_fouls / fraction_elapsed
        pace_shots = current_shots / fraction_elapsed
    else:
        pace_corners = baseline["avg_corners"]
        pace_cards = baseline["avg_cards"]
        pace_fouls = baseline["avg_fouls"]
        pace_shots = baseline["avg_shots"]

    # Expected final totals from HT profile (if available)
    if ht_profile:
        ht_corners = ht_profile["corners"]
        ht_cards = ht_profile["cards"]
        ht_fouls = ht_profile["fouls"]
    else:
        ht_corners = baseline["avg_corners"]
        ht_cards = baseline["avg_cards"]
        ht_fouls = baseline["avg_fouls"]

    # Blend pace-based projection with HT profile
    # More weight on pace as game progresses
    pace_weight = min(0.8, fraction_elapsed)
    profile_weight = 1.0 - pace_weight

    projected_corners = current_corners + (
        pace_weight * (pace_corners * fraction_remaining) +
        profile_weight * max(0, ht_corners - current_corners)
    )
    projected_cards = current_cards + (
        pace_weight * (pace_cards * fraction_remaining) +
        profile_weight * max(0, ht_cards - current_cards)
    )
    projected_fouls = current_fouls + (
        pace_weight * (pace_fouls * fraction_remaining) +
        profile_weight * max(0, ht_fouls - current_fouls)
    )

    return {
        "projected_corners": round(projected_corners, 1),
        "projected_cards": round(projected_cards, 1),
        "projected_fouls": round(projected_fouls, 1),
        "remaining_corners": round(projected_corners - current_corners, 1),
        "remaining_cards": round(projected_cards - current_cards, 1),
        "pace_corners_90": round(pace_corners, 1),
        "pace_cards_90": round(pace_cards, 1),
        "minute": minute,
        "ht_score": ht_score,
    }


# ═══════════════════════════════════════════════════════════════════════
# CALIBRATION CORRECTION (Platt scaling / shrinkage)
# ═══════════════════════════════════════════════════════════════════════

# V4 Calibration: Aggressive shrinkage toward base rates
# From V4 backtest: model predicts 70% but actual is only 44%.
# The model is overconfident by ~25% at high probabilities.
#
# Solution: Linear shrinkage toward base rate (33.3% for 1X2).
# shrinkage_factor controls how much to pull toward base rate.
# 0.0 = no shrinkage (raw model), 1.0 = always predict base rate
SHRINKAGE_FACTOR = 0.35  # Pull 35% toward base rate

# Base rates for 1X2 markets (from 4,888 match analysis)
BASE_RATES = {
    "home_win": 0.431,  # ~43% of matches are home wins
    "draw": 0.256,       # ~26% draws
    "away_win": 0.313,   # ~31% away wins
    "over_25": 0.54,     # ~54% of matches have over 2.5 goals
}


def calibrate_probability(raw_prob: float, base_rate: float = 0.5) -> float:
    """
    Apply shrinkage calibration: pull raw probability toward base rate.

    This is simpler and more robust than point-to-point calibration.
    Formula: calibrated = raw * (1 - shrinkage) + base_rate * shrinkage
    """
    if raw_prob <= 0.0:
        return 0.01
    if raw_prob >= 1.0:
        return 0.99
    calibrated = raw_prob * (1 - SHRINKAGE_FACTOR) + base_rate * SHRINKAGE_FACTOR
    return max(0.01, min(0.99, calibrated))


def calibrate_match_probs(home_win: float, draw: float, away_win: float) -> Dict[str, float]:
    """
    Calibrate 1X2 probabilities with shrinkage toward base rates.
    Keeps probabilities summing to 1.
    """
    cal_hw = calibrate_probability(home_win, BASE_RATES["home_win"])
    cal_d = calibrate_probability(draw, BASE_RATES["draw"])
    cal_aw = calibrate_probability(away_win, BASE_RATES["away_win"])

    # Renormalize
    total = cal_hw + cal_d + cal_aw
    if total > 0:
        cal_hw /= total
        cal_d /= total
        cal_aw /= total

    return {
        "home_win": round(cal_hw, 4),
        "draw": round(cal_d, 4),
        "away_win": round(cal_aw, 4),
        "shrinkage_applied": True,
    }


# ═══════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 80)
    print("MATCH STATS MODEL — Test Cases")
    print("=" * 80)

    # Test 1: Arsenal vs Crystal Palace (EPL, top3 vs lower_mid)
    print("\n--- Test 1: Arsenal vs Crystal Palace (EPL) ---")
    pred = predict_match_stats(
        league="Premier League",
        home_shots_avg=16.5,
        away_shots_avg=10.2,
        home_fouls_avg=10.5,
        away_fouls_avg=12.8,
        home_position=2,
        away_position=14,
        expected_goals=2.7,
        expected_gd=1.5,
    )
    print(f"  Corners: {pred.corners} (H:{pred.home_corners} A:{pred.away_corners})")
    print(f"  Cards: {pred.cards} (H:{pred.home_cards} A:{pred.away_cards})")
    print(f"  Fouls: {pred.fouls}")
    print(f"  Shots: {pred.shots}, SOT: {pred.sot}")
    print(f"  Reds: {pred.reds}")
    print(f"  Profile: {pred.expected_profile}")
    print(f"  Corner O/U: {pred.corner_ou}")
    print(f"  Card O/U: {pred.card_ou}")
    print(f"  Notes: {pred.notes}")

    # Test 2: Juve vs Napoli (Serie A, top3 vs top3, expected tight)
    print("\n--- Test 2: Juventus vs Napoli (Serie A, top3 vs top3) ---")
    pred2 = predict_match_stats(
        league="Serie A",
        home_shots_avg=13.0,
        away_shots_avg=12.5,
        home_fouls_avg=13.5,
        away_fouls_avg=14.0,
        home_position=3,
        away_position=1,
        expected_goals=2.1,
        expected_gd=0.3,
    )
    print(f"  Corners: {pred2.corners} (H:{pred2.home_corners} A:{pred2.away_corners})")
    print(f"  Cards: {pred2.cards} (H:{pred2.home_cards} A:{pred2.away_cards})")
    print(f"  Fouls: {pred2.fouls}")
    print(f"  Profile: {pred2.expected_profile}")
    print(f"  Notes: {pred2.notes}")

    # Test 3: Live — PSG 2-1 at min 70 (Ligue 1)
    print("\n--- Test 3: Live — PSG 2-1 at min 70 ---")
    live = predict_live_stats(
        league="Ligue 1",
        minute=70,
        ht_score="2-1",
        current_corners=7,
        current_cards=3,
        current_fouls=18,
        current_shots=22,
    )
    print(f"  Projected corners: {live['projected_corners']}")
    print(f"  Projected cards: {live['projected_cards']}")
    print(f"  Remaining corners: {live['remaining_corners']}")
    print(f"  Pace corners/90: {live['pace_corners_90']}")

    # Test 4: Calibration
    print("\n--- Test 4: Calibration Correction ---")
    for raw in [0.30, 0.50, 0.60, 0.70, 0.80]:
        cal = calibrate_probability(raw)
        print(f"  Raw {raw:.0%} → Calibrated {cal:.1%} (shrink {raw-cal:.1%})")

    print("\n--- Test 5: Full 1X2 Calibration ---")
    result = calibrate_match_probs(0.65, 0.20, 0.15)
    print(f"  Raw: HW=65% D=20% AW=15%")
    print(f"  Calibrated: HW={result['home_win']:.1%} D={result['draw']:.1%} AW={result['away_win']:.1%}")

    print("\n✅ Match stats model ready")
