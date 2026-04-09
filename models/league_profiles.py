"""League profiles for match prediction calibration."""

LEAGUE_PROFILES = {
    "Premier League": {
        "goals_factor": 1.0,
        "home_advantage": 0.25,
        "draw_tendency": 0.24,
        "avg_goals": 2.82,
    },
    "La Liga": {
        "goals_factor": 0.94,
        "home_advantage": 0.27,
        "draw_tendency": 0.26,
        "avg_goals": 2.64,
    },
    "Bundesliga": {
        "goals_factor": 1.09,
        "home_advantage": 0.24,
        "draw_tendency": 0.22,
        "avg_goals": 3.08,
    },
    "Serie A": {
        "goals_factor": 0.91,
        "home_advantage": 0.26,
        "draw_tendency": 0.27,
        "avg_goals": 2.58,
    },
    "Ligue 1": {
        "goals_factor": 0.99,
        "home_advantage": 0.26,
        "draw_tendency": 0.24,
        "avg_goals": 2.78,
    },
}

DEFAULT_PROFILE = {
    "goals_factor": 1.0,
    "home_advantage": 0.25,
    "draw_tendency": 0.25,
    "avg_goals": 2.70,
}


def get_league_profile(league: str) -> dict:
    """Get league-specific profile for calibration."""
    return LEAGUE_PROFILES.get(league, DEFAULT_PROFILE)
