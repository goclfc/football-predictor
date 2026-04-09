"""
Situational Football Agents
Specialized agents for analyzing contextual factors affecting match outcomes
"""

from typing import Dict, Any, Optional
import random
from datetime import datetime, timedelta


class StakesAgent:
    """Analyzes what's at stake in the match (title race, CL qualification, relegation battle, etc.)"""
    name = "stakes_agent"
    specialty = "Match stakes and motivation factors"
    weight = 0.65
    reliability_score = 0.60

    LEAGUE_TABLE_2526 = {
        "Premier League": {
            "Manchester City": {"position": 1, "points": 89, "gd": 68},
            "Liverpool": {"position": 2, "points": 86, "gd": 62},
            "Arsenal": {"position": 3, "points": 84, "gd": 59},
            "Chelsea": {"position": 4, "points": 71, "gd": 44},
            "Manchester United": {"position": 5, "points": 68, "gd": 35},
            "Tottenham": {"position": 6, "points": 65, "gd": 32},
            "Aston Villa": {"position": 7, "points": 63, "gd": 28},
            "Newcastle": {"position": 8, "points": 61, "gd": 25},
            "Brighton": {"position": 9, "points": 57, "gd": 18},
            "Fulham": {"position": 10, "points": 56, "gd": 16},
            "Bournemouth": {"position": 18, "points": 34, "gd": -28},
            "Nottingham": {"position": 19, "points": 31, "gd": -35},
            "Southampton": {"position": 20, "points": 24, "gd": -48},
        },
        "La Liga": {
            "Real Madrid": {"position": 1, "points": 90, "gd": 71},
            "Barcelona": {"position": 2, "points": 87, "gd": 68},
            "Atletico Madrid": {"position": 3, "points": 79, "gd": 52},
            "Girona": {"position": 4, "points": 75, "gd": 48},
            "Athletic Bilbao": {"position": 5, "points": 72, "gd": 42},
            "Valencia": {"position": 18, "points": 36, "gd": -32},
            "Cádiz": {"position": 19, "points": 33, "gd": -42},
            "Almería": {"position": 20, "points": 28, "gd": -55},
        },
        "Serie A": {
            "Inter Milan": {"position": 1, "points": 88, "gd": 65},
            "Juventus": {"position": 2, "points": 85, "gd": 58},
            "AC Milan": {"position": 3, "points": 82, "gd": 54},
            "Napoli": {"position": 4, "points": 76, "gd": 48},
            "Lazio": {"position": 5, "points": 72, "gd": 40},
            "Salernitana": {"position": 18, "points": 35, "gd": -38},
            "Lecce": {"position": 19, "points": 32, "gd": -45},
            "Venezia": {"position": 20, "points": 28, "gd": -52},
        },
        "Bundesliga": {
            "Bayern Munich": {"position": 1, "points": 91, "gd": 72},
            "Bayer Leverkusen": {"position": 2, "points": 83, "gd": 55},
            "Borussia Dortmund": {"position": 3, "points": 80, "gd": 50},
            "VfB Stuttgart": {"position": 4, "points": 75, "gd": 42},
            "RB Leipzig": {"position": 5, "points": 71, "gd": 38},
            "Schalke 04": {"position": 18, "points": 33, "gd": -40},
            "Darmstadt": {"position": 19, "points": 31, "gd": -48},
            "VfL Bochum": {"position": 20, "points": 26, "gd": -56},
        },
        "Ligue 1": {
            "Paris Saint-Germain": {"position": 1, "points": 89, "gd": 70},
            "Monaco": {"position": 2, "points": 81, "gd": 56},
            "Marseille": {"position": 3, "points": 78, "gd": 48},
            "Lyon": {"position": 4, "points": 75, "gd": 44},
            "Lens": {"position": 5, "points": 72, "gd": 40},
            "Montpellier": {"position": 18, "points": 36, "gd": -35},
            "Le Havre": {"position": 19, "points": 33, "gd": -42},
            "Clermont": {"position": 20, "points": 29, "gd": -48},
        }
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        league = match_data.get("league", "")
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        league_table = self.LEAGUE_TABLE_2526.get(league, {})
        home_info = league_table.get(home_team, {})
        away_info = league_table.get(away_team, {})

        home_pos = home_info.get("position", 11)
        away_pos = away_info.get("position", 11)
        home_points = home_info.get("points", 45)
        away_points = away_info.get("points", 45)

        stakes_level_home = 5
        stakes_level_away = 5
        motivation_home = 1.0
        motivation_away = 1.0
        match_intensity = 5
        stakes_type = "mid_table"

        if home_pos <= 4:
            stakes_level_home = 10
            motivation_home = 1.12
            stakes_type = "title_race" if home_pos <= 2 else "cl_qualification"
        elif home_pos <= 6:
            stakes_level_home = 8
            motivation_home = 1.08
            stakes_type = "cl_qualification"
        elif home_pos >= 18:
            stakes_level_home = 9
            motivation_home = 1.10
            stakes_type = "relegation_battle"

        if away_pos <= 4:
            stakes_level_away = 10
            motivation_away = 1.12
        elif away_pos <= 6:
            stakes_level_away = 8
            motivation_away = 1.08
        elif away_pos >= 18:
            stakes_level_away = 9
            motivation_away = 1.10

        if stakes_level_home >= 9 or stakes_level_away >= 9:
            match_intensity = 9
        elif stakes_level_home >= 8 or stakes_level_away >= 8:
            match_intensity = 8

        if home_pos > 10 and away_pos > 10:
            motivation_home = 0.92
            motivation_away = 0.92

        insights = []
        if stakes_type == "title_race":
            insights.append(f"{home_team} in title race - maximum motivation and focus expected")
        elif stakes_type == "relegation_battle":
            insights.append(f"{home_team} fighting relegation - desperation factor present")
        elif stakes_type == "cl_qualification":
            insights.append(f"{home_team} chasing {home_pos} position - strong motivation for European places")

        if away_pos <= 4:
            insights.append(f"{away_team} top 4 team - high quality opposition expected")

        if home_pos > 10 and away_pos > 10:
            insights.append("Both teams with little to play for - potential for cautious approach")

        return {
            "agent": self.name,
            "predictions": {
                "stakes_level_home": stakes_level_home,
                "stakes_level_away": stakes_level_away,
                "motivation_multiplier_home": round(motivation_home, 3),
                "motivation_multiplier_away": round(motivation_away, 3),
                "match_intensity_prediction": match_intensity,
                "stakes_type": stakes_type
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "goal_expectancy_multiplier_home": motivation_home,
                "goal_expectancy_multiplier_away": motivation_away,
                "intensity_boost": (match_intensity - 5) * 0.05
            }
        }


class RivalryIntensityAgent:
    """Analyzes rivalry dynamics and their impact on match characteristics"""
    name = "rivalry_agent"
    specialty = "Rivalry intensity and aggression factors"
    weight = 0.55
    reliability_score = 0.55

    RIVALRIES = {
        frozenset(["Manchester United", "Liverpool"]): {
            "intensity": 5,
            "avg_cards_h2h": 3.8,
            "avg_red_cards_h2h": 0.22,
            "fan_hostility": 9,
            "name": "Northwest Derby"
        },
        frozenset(["Manchester United", "Manchester City"]): {
            "intensity": 5,
            "avg_cards_h2h": 3.6,
            "avg_red_cards_h2h": 0.18,
            "fan_hostility": 9,
            "name": "Manchester Derby"
        },
        frozenset(["Arsenal", "Tottenham"]): {
            "intensity": 5,
            "avg_cards_h2h": 4.1,
            "avg_red_cards_h2h": 0.25,
            "fan_hostility": 9,
            "name": "North London Derby"
        },
        frozenset(["Chelsea", "Tottenham"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.4,
            "avg_red_cards_h2h": 0.15,
            "fan_hostility": 8,
            "name": "West London Derby"
        },
        frozenset(["Liverpool", "Everton"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.2,
            "avg_red_cards_h2h": 0.12,
            "fan_hostility": 8,
            "name": "Merseyside Derby"
        },
        frozenset(["Barcelona", "Real Madrid"]): {
            "intensity": 5,
            "avg_cards_h2h": 4.3,
            "avg_red_cards_h2h": 0.28,
            "fan_hostility": 10,
            "name": "El Clasico"
        },
        frozenset(["Barcelona", "Espanyol"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.7,
            "avg_red_cards_h2h": 0.18,
            "fan_hostility": 8,
            "name": "Barcelona Derby"
        },
        frozenset(["Real Madrid", "Atletico Madrid"]): {
            "intensity": 5,
            "avg_cards_h2h": 3.9,
            "avg_red_cards_h2h": 0.21,
            "fan_hostility": 9,
            "name": "Madrid Derby"
        },
        frozenset(["Valencia", "Real Madrid"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.5,
            "avg_red_cards_h2h": 0.16,
            "fan_hostility": 8,
            "name": "Valencia-Madrid"
        },
        frozenset(["Athletic Bilbao", "Real Sociedad"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.3,
            "avg_red_cards_h2h": 0.14,
            "fan_hostility": 8,
            "name": "Basque Derby"
        },
        frozenset(["Inter Milan", "AC Milan"]): {
            "intensity": 5,
            "avg_cards_h2h": 4.2,
            "avg_red_cards_h2h": 0.24,
            "fan_hostility": 9,
            "name": "Derby della Madonnina"
        },
        frozenset(["Inter Milan", "Juventus"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.6,
            "avg_red_cards_h2h": 0.18,
            "fan_hostility": 8,
            "name": "Inter-Juventus"
        },
        frozenset(["AC Milan", "Juventus"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.5,
            "avg_red_cards_h2h": 0.16,
            "fan_hostility": 8,
            "name": "Milan-Turin"
        },
        frozenset(["AS Roma", "Lazio"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.8,
            "avg_red_cards_h2h": 0.19,
            "fan_hostility": 9,
            "name": "Rome Derby"
        },
        frozenset(["Napoli", "AS Roma"]): {
            "intensity": 3,
            "avg_cards_h2h": 3.1,
            "avg_red_cards_h2h": 0.11,
            "fan_hostility": 7,
            "name": "Naples-Rome"
        },
        frozenset(["Bayern Munich", "Borussia Dortmund"]): {
            "intensity": 5,
            "avg_cards_h2h": 3.7,
            "avg_red_cards_h2h": 0.19,
            "fan_hostility": 9,
            "name": "Bavarian Classic"
        },
        frozenset(["Bayern Munich", "RB Leipzig"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.4,
            "avg_red_cards_h2h": 0.14,
            "fan_hostility": 7,
            "name": "Munich-Leipzig"
        },
        frozenset(["Borussia Dortmund", "Schalke 04"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.9,
            "avg_red_cards_h2h": 0.20,
            "fan_hostility": 9,
            "name": "Ruhr Derby"
        },
        frozenset(["Bayer Leverkusen", "Borussia Mönchengladbach"]): {
            "intensity": 3,
            "avg_cards_h2h": 3.1,
            "avg_red_cards_h2h": 0.12,
            "fan_hostility": 7,
            "name": "Rhine Derby"
        },
        frozenset(["VfB Stuttgart", "Karlsruhe"]): {
            "intensity": 3,
            "avg_cards_h2h": 2.9,
            "avg_red_cards_h2h": 0.10,
            "fan_hostility": 6,
            "name": "Baden-Württemberg Derby"
        },
        frozenset(["Paris Saint-Germain", "Marseille"]): {
            "intensity": 5,
            "avg_cards_h2h": 4.4,
            "avg_red_cards_h2h": 0.26,
            "fan_hostility": 10,
            "name": "Le Classique"
        },
        frozenset(["Paris Saint-Germain", "Lyon"]): {
            "intensity": 4,
            "avg_cards_h2h": 3.5,
            "avg_red_cards_h2h": 0.16,
            "fan_hostility": 8,
            "name": "PSG-Lyon"
        },
        frozenset(["Marseille", "Monaco"]): {
            "intensity": 3,
            "avg_cards_h2h": 3.2,
            "avg_red_cards_h2h": 0.13,
            "fan_hostility": 7,
            "name": "South Coast"
        },
        frozenset(["Lens", "Lille"]): {
            "intensity": 3,
            "avg_cards_h2h": 3.0,
            "avg_red_cards_h2h": 0.11,
            "fan_hostility": 7,
            "name": "Northern Derby"
        },
        frozenset(["Nice", "Monaco"]): {
            "intensity": 3,
            "avg_cards_h2h": 2.8,
            "avg_red_cards_h2h": 0.09,
            "fan_hostility": 6,
            "name": "Côte d'Azur"
        }
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        team_pair = frozenset([home_team, away_team])

        rivalry_data = self.RIVALRIES.get(team_pair, None)

        if rivalry_data:
            rivalry_score = rivalry_data["intensity"] / 5.0
            card_multiplier = 1.0 + (rivalry_data["avg_cards_h2h"] - 3.0) * 0.15
            aggression_boost = (rivalry_data["intensity"] - 2) * 0.08
            atmosphere_intensity = rivalry_data["fan_hostility"]
            rivalry_name = rivalry_data["name"]

            insights = [
                f"Major rivalry: {rivalry_name}",
                f"Expected high intensity with {rivalry_data['avg_cards_h2h']:.1f} avg cards historically",
                f"Fan hostility level: {atmosphere_intensity}/10 - expect charged atmosphere"
            ]
        else:
            rivalry_score = 0.3
            card_multiplier = 1.0
            aggression_boost = 0.0
            atmosphere_intensity = 4
            rivalry_name = "None"

            insights = [
                "Not a major recognized rivalry",
                "Standard professional intensity expected",
                "Normal disciplinary expectations"
            ]

        return {
            "agent": self.name,
            "predictions": {
                "rivalry_score": round(rivalry_score, 2),
                "card_multiplier": round(card_multiplier, 3),
                "atmosphere_intensity": atmosphere_intensity,
                "aggression_boost": round(aggression_boost, 3),
                "rivalry_name": rivalry_name
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "yellow_card_expectancy_multiplier": card_multiplier,
                "red_card_risk_multiplier": card_multiplier * 0.6,
                "intensity_multiplier": 1.0 + aggression_boost
            }
        }


class RefereeAgent:
    """Analyzes referee tendencies and their impact on match characteristics"""
    name = "referee_agent"
    specialty = "Referee tendencies and disciplinary impact"
    weight = 0.50
    reliability_score = 0.50

    TOP_REFEREES = {
        "Premier League": [
            {"name": "Michael Oliver", "avg_yellows": 3.8, "avg_reds": 0.15, "penalty_per_game": 0.32, "home_bias": 1.02, "strictness": 7},
            {"name": "Anthony Taylor", "avg_yellows": 4.2, "avg_reds": 0.18, "penalty_per_game": 0.35, "home_bias": 1.01, "strictness": 8},
            {"name": "Craig Pawson", "avg_yellows": 3.6, "avg_reds": 0.12, "penalty_per_game": 0.28, "home_bias": 1.00, "strictness": 6},
            {"name": "Martin Atkinson", "avg_yellows": 3.9, "avg_reds": 0.14, "penalty_per_game": 0.31, "home_bias": 1.03, "strictness": 7},
            {"name": "Andre Marriner", "avg_yellows": 4.1, "avg_reds": 0.16, "penalty_per_game": 0.33, "home_bias": 1.02, "strictness": 7},
        ],
        "La Liga": [
            {"name": "José Luis Munuera Montero", "avg_yellows": 4.3, "avg_reds": 0.19, "penalty_per_game": 0.38, "home_bias": 1.01, "strictness": 8},
            {"name": "Guillermo Cuadra Fernández", "avg_yellows": 3.9, "avg_reds": 0.14, "penalty_per_game": 0.29, "home_bias": 1.00, "strictness": 7},
            {"name": "Mateo Busquets Ferrer", "avg_yellows": 3.7, "avg_reds": 0.13, "penalty_per_game": 0.27, "home_bias": 0.99, "strictness": 6},
            {"name": "Ricardo de Burgos Benítez", "avg_yellows": 4.4, "avg_reds": 0.20, "penalty_per_game": 0.40, "home_bias": 1.02, "strictness": 9},
            {"name": "Xavier Estrada Fernández", "avg_yellows": 3.8, "avg_reds": 0.15, "penalty_per_game": 0.30, "home_bias": 1.00, "strictness": 7},
        ],
        "Serie A": [
            {"name": "Pierluigi Chiffi", "avg_yellows": 4.0, "avg_reds": 0.16, "penalty_per_game": 0.33, "home_bias": 1.01, "strictness": 7},
            {"name": "Matteo Marchetti", "avg_yellows": 3.8, "avg_reds": 0.14, "penalty_per_game": 0.30, "home_bias": 1.00, "strictness": 6},
            {"name": "Daniele Orsato", "avg_yellows": 4.2, "avg_reds": 0.18, "penalty_per_game": 0.36, "home_bias": 1.02, "strictness": 8},
            {"name": "Marco Guida", "avg_yellows": 4.1, "avg_reds": 0.17, "penalty_per_game": 0.34, "home_bias": 1.01, "strictness": 8},
            {"name": "Massimiliano Irrati", "avg_yellows": 3.9, "avg_reds": 0.15, "penalty_per_game": 0.31, "home_bias": 1.00, "strictness": 7},
        ],
        "Bundesliga": [
            {"name": "Felix Zwayer", "avg_yellows": 3.9, "avg_reds": 0.15, "penalty_per_game": 0.32, "home_bias": 1.00, "strictness": 7},
            {"name": "Manuel Gräfe", "avg_yellows": 3.7, "avg_reds": 0.13, "penalty_per_game": 0.29, "home_bias": 0.99, "strictness": 6},
            {"name": "Christian Dingert", "avg_yellows": 4.0, "avg_reds": 0.16, "penalty_per_game": 0.33, "home_bias": 1.01, "strictness": 7},
            {"name": "Tobias Stieler", "avg_yellows": 4.3, "avg_reds": 0.19, "penalty_per_game": 0.37, "home_bias": 1.02, "strictness": 8},
            {"name": "Bastian Dankert", "avg_yellows": 3.8, "avg_reds": 0.14, "penalty_per_game": 0.30, "home_bias": 1.00, "strictness": 7},
        ],
        "Ligue 1": [
            {"name": "François Letexier", "avg_yellows": 4.1, "avg_reds": 0.17, "penalty_per_game": 0.34, "home_bias": 1.01, "strictness": 7},
            {"name": "Clément Turpin", "avg_yellows": 4.2, "avg_reds": 0.18, "penalty_per_game": 0.36, "home_bias": 1.02, "strictness": 8},
            {"name": "Benoît Bastien", "avg_yellows": 3.9, "avg_reds": 0.15, "penalty_per_game": 0.31, "home_bias": 1.00, "strictness": 7},
            {"name": "Léon Dutoit", "avg_yellows": 3.8, "avg_reds": 0.14, "penalty_per_game": 0.30, "home_bias": 1.00, "strictness": 6},
            {"name": "Antony Gautier", "avg_yellows": 4.0, "avg_reds": 0.16, "penalty_per_game": 0.33, "home_bias": 1.01, "strictness": 7},
        ]
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        league = match_data.get("league", "")

        league_referees = self.TOP_REFEREES.get(league, [])
        if league_referees:
            referee = random.choice(league_referees)
        else:
            referee = {
                "name": "Unknown Referee",
                "avg_yellows": 3.9,
                "avg_reds": 0.15,
                "penalty_per_game": 0.32,
                "home_bias": 1.00,
                "strictness": 7
            }

        expected_yellows = referee["avg_yellows"]
        expected_reds = referee["avg_reds"]
        penalty_prob = referee["penalty_per_game"]
        strictness = referee["strictness"]
        home_bias = referee["home_bias"]

        card_adjustment = 1.0 + (strictness - 7) * 0.1

        insights = [
            f"Referee: {referee['name']}",
            f"Strictness level: {strictness}/10 - expect {'tight' if strictness >= 8 else 'moderate' if strictness >= 6 else 'lenient'} match control",
            f"Expected yellow cards: {expected_yellows:.1f}",
            f"Penalty frequency: {penalty_prob:.2f} per game"
        ]

        if home_bias > 1.02:
            insights.append(f"Known slight home bias ({home_bias:.2f}) - may favor home team")

        return {
            "agent": self.name,
            "predictions": {
                "expected_yellows": round(expected_yellows, 2),
                "expected_reds": round(expected_reds, 3),
                "penalty_probability": round(penalty_prob, 3),
                "card_adjustment_factor": round(card_adjustment, 3),
                "referee_strictness": strictness,
                "referee_name": referee["name"],
                "home_bias_factor": round(home_bias, 3)
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "yellow_card_multiplier": card_adjustment,
                "red_card_multiplier": card_adjustment * 0.7,
                "penalty_multiplier": 1.0 + (strictness - 7) * 0.08,
                "home_penalty_boost": max(0.98, home_bias)
            }
        }


class VenueAgent:
    """Analyzes stadium and venue factors affecting match dynamics"""
    name = "venue_agent"
    specialty = "Venue and home advantage factors"
    weight = 0.45
    reliability_score = 0.50

    STADIUMS = {
        "Manchester City": {"name": "Etihad Stadium", "capacity": 55097, "pitch_size": "standard", "surface": "grass", "altitude_m": 38, "avg_attendance_pct": 0.95},
        "Manchester United": {"name": "Old Trafford", "capacity": 74140, "pitch_size": "standard", "surface": "grass", "altitude_m": 36, "avg_attendance_pct": 0.96},
        "Liverpool": {"name": "Anfield", "capacity": 61276, "pitch_size": "standard", "surface": "grass", "altitude_m": 12, "avg_attendance_pct": 0.97},
        "Arsenal": {"name": "Emirates Stadium", "capacity": 60704, "pitch_size": "standard", "surface": "grass", "altitude_m": 6, "avg_attendance_pct": 0.92},
        "Chelsea": {"name": "Stamford Bridge", "capacity": 40341, "pitch_size": "narrow", "surface": "grass", "altitude_m": 13, "avg_attendance_pct": 0.94},
        "Tottenham": {"name": "Tottenham Hotspur Stadium", "capacity": 62850, "pitch_size": "standard", "surface": "grass", "altitude_m": 32, "avg_attendance_pct": 0.91},
        "Real Madrid": {"name": "Santiago Bernabéu", "capacity": 81044, "pitch_size": "standard", "surface": "grass", "altitude_m": 620, "avg_attendance_pct": 0.94},
        "Barcelona": {"name": "Estadi Olimpic", "capacity": 55926, "pitch_size": "standard", "surface": "grass", "altitude_m": 12, "avg_attendance_pct": 0.92},
        "Atletico Madrid": {"name": "Metropolitano", "capacity": 68456, "pitch_size": "standard", "surface": "grass", "altitude_m": 646, "avg_attendance_pct": 0.89},
        "Valencia": {"name": "Mestalla", "capacity": 55000, "pitch_size": "standard", "surface": "grass", "altitude_m": 4, "avg_attendance_pct": 0.78},
        "Inter Milan": {"name": "San Siro", "capacity": 75923, "pitch_size": "large", "surface": "grass", "altitude_m": 122, "avg_attendance_pct": 0.88},
        "AC Milan": {"name": "San Siro", "capacity": 75923, "pitch_size": "large", "surface": "grass", "altitude_m": 122, "avg_attendance_pct": 0.85},
        "Juventus": {"name": "Allianz Stadium", "capacity": 41507, "pitch_size": "standard", "surface": "hybrid", "altitude_m": 239, "avg_attendance_pct": 0.95},
        "Napoli": {"name": "San Paolo", "capacity": 54726, "pitch_size": "standard", "surface": "grass", "altitude_m": 17, "avg_attendance_pct": 0.81},
        "AS Roma": {"name": "Stadio Olimpico", "capacity": 70698, "pitch_size": "standard", "surface": "grass", "altitude_m": 60, "avg_attendance_pct": 0.82},
        "Bayern Munich": {"name": "Allianz Arena", "capacity": 75024, "pitch_size": "standard", "surface": "grass", "altitude_m": 515, "avg_attendance_pct": 0.98},
        "Borussia Dortmund": {"name": "Signal Iduna Park", "capacity": 81365, "pitch_size": "standard", "surface": "grass", "altitude_m": 131, "avg_attendance_pct": 0.97},
        "Bayer Leverkusen": {"name": "BayArena", "capacity": 30846, "pitch_size": "standard", "surface": "grass", "altitude_m": 63, "avg_attendance_pct": 0.85},
        "RB Leipzig": {"name": "Red Bull Arena", "capacity": 47748, "pitch_size": "standard", "surface": "grass", "altitude_m": 190, "avg_attendance_pct": 0.91},
        "VfB Stuttgart": {"name": "Mercedes-Benz Arena", "capacity": 60441, "pitch_size": "standard", "surface": "grass", "altitude_m": 245, "avg_attendance_pct": 0.86},
        "Paris Saint-Germain": {"name": "Parc des Princes", "capacity": 47929, "pitch_size": "standard", "surface": "grass", "altitude_m": 33, "avg_attendance_pct": 0.93},
        "Marseille": {"name": "Orange Vélodrome", "capacity": 67394, "pitch_size": "standard", "surface": "grass", "altitude_m": 0, "avg_attendance_pct": 0.85},
        "Monaco": {"name": "Stade Louis II", "capacity": 18640, "pitch_size": "standard", "surface": "grass", "altitude_m": 60, "avg_attendance_pct": 0.88},
        "Lyon": {"name": "Groupama Stadium", "capacity": 59286, "pitch_size": "standard", "surface": "grass", "altitude_m": 200, "avg_attendance_pct": 0.80},
        "Lens": {"name": "Stade Bollaert-Delelis", "capacity": 38223, "pitch_size": "standard", "surface": "grass", "altitude_m": 30, "avg_attendance_pct": 0.88},
        "Brighton": {"name": "Amex Stadium", "capacity": 31895, "pitch_size": "standard", "surface": "grass", "altitude_m": 8, "avg_attendance_pct": 0.92},
        "Aston Villa": {"name": "Villa Park", "capacity": 42682, "pitch_size": "standard", "surface": "grass", "altitude_m": 94, "avg_attendance_pct": 0.89},
        "Newcastle": {"name": "St James' Park", "capacity": 52305, "pitch_size": "standard", "surface": "grass", "altitude_m": 15, "avg_attendance_pct": 0.97},
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        home_stadium = self.STADIUMS.get(home_team, {})

        if not home_stadium:
            home_stadium = {
                "name": f"{home_team} Stadium",
                "capacity": 50000,
                "pitch_size": "standard",
                "surface": "grass",
                "altitude_m": 100,
                "avg_attendance_pct": 0.85
            }

        pitch_size = home_stadium.get("pitch_size", "standard")
        surface = home_stadium.get("surface", "grass")
        altitude = home_stadium.get("altitude_m", 0)
        attendance_pct = home_stadium.get("avg_attendance_pct", 0.85)

        home_advantage_base = 1.05 + (attendance_pct - 0.80) * 0.2

        if pitch_size == "large":
            pitch_factor = 1.05
            passing_style_help = 0.03
        elif pitch_size == "narrow":
            pitch_factor = 0.97
            passing_style_help = -0.02
        else:
            pitch_factor = 1.00
            passing_style_help = 0.00

        if surface == "hybrid":
            surface_factor = 0.99
        else:
            surface_factor = 1.00

        altitude_factor = 1.0
        if altitude > 500:
            altitude_factor = 0.98
            altitude_impact = "High altitude may affect away team fitness in second half"
        elif altitude > 200:
            altitude_factor = 0.99
            altitude_impact = "Moderate altitude - minor fitness consideration"
        else:
            altitude_impact = "Sea level - no altitude factor"

        home_advantage_modifier = home_advantage_base * pitch_factor * surface_factor * altitude_factor

        atmosphere_rating = int(5 + (attendance_pct - 0.80) * 20)
        atmosphere_rating = min(10, max(1, atmosphere_rating))

        insights = [
            f"Venue: {home_stadium['name']} (capacity: {home_stadium['capacity']:,})",
            f"Expected attendance: {int(home_stadium['capacity'] * attendance_pct):,}",
            f"Pitch type: {pitch_size.title()} {surface}",
            altitude_impact
        ]

        return {
            "agent": self.name,
            "predictions": {
                "home_advantage_modifier": round(home_advantage_modifier, 3),
                "pitch_factor": round(pitch_factor, 3),
                "atmosphere_rating": atmosphere_rating,
                "travel_impact_away": round(1.0 - (home_advantage_modifier - 1.0) * 0.5, 3),
                "expected_attendance": int(home_stadium['capacity'] * attendance_pct)
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "home_goal_multiplier": home_advantage_modifier,
                "away_goal_multiplier": 1.0 / home_advantage_modifier if home_advantage_modifier > 0 else 1.0,
                "passing_accuracy_home_boost": passing_style_help,
                "altitude_stamina_impact": altitude_factor
            }
        }


class WeatherAgent:
    """Analyzes weather conditions and their impact on match play"""
    name = "weather_agent"
    specialty = "Weather conditions and environmental factors"
    weight = 0.35
    reliability_score = 0.40

    LEAGUE_WEATHER = {
        "Premier League": {  # England
            1: {"avg_temp": 8, "rain_prob": 0.45, "wind_kmh": 18},
            2: {"avg_temp": 9, "rain_prob": 0.40, "wind_kmh": 17},
            3: {"avg_temp": 12, "rain_prob": 0.35, "wind_kmh": 15},
            4: {"avg_temp": 15, "rain_prob": 0.30, "wind_kmh": 13},
            5: {"avg_temp": 19, "rain_prob": 0.25, "wind_kmh": 12},
            6: {"avg_temp": 22, "rain_prob": 0.20, "wind_kmh": 11},
            7: {"avg_temp": 24, "rain_prob": 0.18, "wind_kmh": 10},
            8: {"avg_temp": 23, "rain_prob": 0.20, "wind_kmh": 11},
            9: {"avg_temp": 20, "rain_prob": 0.25, "wind_kmh": 13},
            10: {"avg_temp": 15, "rain_prob": 0.35, "wind_kmh": 15},
            11: {"avg_temp": 11, "rain_prob": 0.42, "wind_kmh": 17},
            12: {"avg_temp": 9, "rain_prob": 0.48, "wind_kmh": 18},
        },
        "La Liga": {  # Spain
            1: {"avg_temp": 10, "rain_prob": 0.25, "wind_kmh": 14},
            2: {"avg_temp": 12, "rain_prob": 0.22, "wind_kmh": 13},
            3: {"avg_temp": 15, "rain_prob": 0.20, "wind_kmh": 12},
            4: {"avg_temp": 18, "rain_prob": 0.15, "wind_kmh": 11},
            5: {"avg_temp": 23, "rain_prob": 0.10, "wind_kmh": 9},
            6: {"avg_temp": 28, "rain_prob": 0.05, "wind_kmh": 8},
            7: {"avg_temp": 32, "rain_prob": 0.02, "wind_kmh": 8},
            8: {"avg_temp": 31, "rain_prob": 0.03, "wind_kmh": 8},
            9: {"avg_temp": 27, "rain_prob": 0.08, "wind_kmh": 9},
            10: {"avg_temp": 21, "rain_prob": 0.15, "wind_kmh": 11},
            11: {"avg_temp": 15, "rain_prob": 0.22, "wind_kmh": 12},
            12: {"avg_temp": 11, "rain_prob": 0.28, "wind_kmh": 13},
        },
        "Serie A": {  # Italy
            1: {"avg_temp": 7, "rain_prob": 0.30, "wind_kmh": 13},
            2: {"avg_temp": 9, "rain_prob": 0.28, "wind_kmh": 12},
            3: {"avg_temp": 13, "rain_prob": 0.25, "wind_kmh": 11},
            4: {"avg_temp": 17, "rain_prob": 0.18, "wind_kmh": 10},
            5: {"avg_temp": 22, "rain_prob": 0.12, "wind_kmh": 8},
            6: {"avg_temp": 26, "rain_prob": 0.08, "wind_kmh": 7},
            7: {"avg_temp": 29, "rain_prob": 0.05, "wind_kmh": 7},
            8: {"avg_temp": 28, "rain_prob": 0.06, "wind_kmh": 7},
            9: {"avg_temp": 24, "rain_prob": 0.10, "wind_kmh": 8},
            10: {"avg_temp": 18, "rain_prob": 0.18, "wind_kmh": 10},
            11: {"avg_temp": 13, "rain_prob": 0.25, "wind_kmh": 11},
            12: {"avg_temp": 8, "rain_prob": 0.32, "wind_kmh": 13},
        },
        "Bundesliga": {  # Germany
            1: {"avg_temp": 1, "rain_prob": 0.50, "wind_kmh": 18},
            2: {"avg_temp": 3, "rain_prob": 0.48, "wind_kmh": 17},
            3: {"avg_temp": 7, "rain_prob": 0.40, "wind_kmh": 15},
            4: {"avg_temp": 12, "rain_prob": 0.32, "wind_kmh": 13},
            5: {"avg_temp": 17, "rain_prob": 0.25, "wind_kmh": 11},
            6: {"avg_temp": 21, "rain_prob": 0.20, "wind_kmh": 10},
            7: {"avg_temp": 23, "rain_prob": 0.18, "wind_kmh": 9},
            8: {"avg_temp": 22, "rain_prob": 0.20, "wind_kmh": 10},
            9: {"avg_temp": 18, "rain_prob": 0.28, "wind_kmh": 12},
            10: {"avg_temp": 12, "rain_prob": 0.38, "wind_kmh": 14},
            11: {"avg_temp": 7, "rain_prob": 0.45, "wind_kmh": 16},
            12: {"avg_temp": 3, "rain_prob": 0.52, "wind_kmh": 17},
        },
        "Ligue 1": {  # France
            1: {"avg_temp": 6, "rain_prob": 0.40, "wind_kmh": 16},
            2: {"avg_temp": 7, "rain_prob": 0.38, "wind_kmh": 15},
            3: {"avg_temp": 10, "rain_prob": 0.35, "wind_kmh": 14},
            4: {"avg_temp": 14, "rain_prob": 0.28, "wind_kmh": 12},
            5: {"avg_temp": 18, "rain_prob": 0.22, "wind_kmh": 11},
            6: {"avg_temp": 22, "rain_prob": 0.18, "wind_kmh": 10},
            7: {"avg_temp": 24, "rain_prob": 0.15, "wind_kmh": 9},
            8: {"avg_temp": 23, "rain_prob": 0.18, "wind_kmh": 10},
            9: {"avg_temp": 20, "rain_prob": 0.22, "wind_kmh": 11},
            10: {"avg_temp": 15, "rain_prob": 0.30, "wind_kmh": 13},
            11: {"avg_temp": 10, "rain_prob": 0.36, "wind_kmh": 14},
            12: {"avg_temp": 7, "rain_prob": 0.42, "wind_kmh": 15},
        }
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        league = match_data.get("league", "")
        commence_time = match_data.get("commence_time", "")

        try:
            match_date = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            month = match_date.month
        except:
            month = 4

        league_weather = self.LEAGUE_WEATHER.get(league, {})
        weather_data = league_weather.get(month, {"avg_temp": 15, "rain_prob": 0.25, "wind_kmh": 12})

        temp = weather_data["avg_temp"]
        rain_prob = weather_data["rain_prob"]
        wind = weather_data["wind_kmh"]

        if temp > 25:
            tempo_adjustment = 0.92
            intensity = "High heat will reduce intensity"
        elif temp < 5:
            tempo_adjustment = 0.95
            intensity = "Cold conditions may slow play"
        else:
            tempo_adjustment = 1.00
            intensity = "Normal temperature conditions"

        if rain_prob > 0.40:
            goal_impact = 0.90
            rain_description = "Heavy rain likely - wet pitch"
        elif rain_prob > 0.25:
            goal_impact = 0.95
            rain_description = "Moderate rain probable"
        else:
            goal_impact = 1.00
            rain_description = "Dry conditions expected"

        if wind > 16:
            crossing_impact = 0.88
            wind_description = "Strong wind - long ball play affected"
        elif wind > 12:
            crossing_impact = 0.94
            wind_description = "Moderate wind expected"
        else:
            crossing_impact = 1.00
            wind_description = "Light wind conditions"

        weather_impact = (tempo_adjustment + goal_impact + crossing_impact) / 3.0 - 1.0

        conditions = f"{rain_description}, {temp}°C, {wind} km/h wind"

        insights = [
            f"Expected conditions: {conditions}",
            intensity,
            wind_description,
        ]

        return {
            "agent": self.name,
            "predictions": {
                "weather_impact": round(weather_impact, 3),
                "conditions_description": conditions,
                "tempo_adjustment": round(tempo_adjustment, 3),
                "goal_scoring_impact": round(goal_impact, 3),
                "rain_probability": round(rain_prob, 2),
                "wind_kmh": wind,
                "avg_temp_celsius": temp,
                "crossing_impact": round(crossing_impact, 3)
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "intensity_multiplier": tempo_adjustment,
                "goal_expectancy_multiplier": goal_impact,
                "crossing_success_multiplier": crossing_impact,
                "passing_accuracy_multiplier": rain_prob < 0.35 and 1.00 or 0.97
            }
        }


class MomentumAgent:
    """Analyzes team momentum and recent form"""
    name = "momentum_agent"
    specialty = "Form momentum and confidence factors"
    weight = 0.65
    reliability_score = 0.65

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_form_string = home_form.get("form_string", "DDDDD")
        away_form_string = away_form.get("form_string", "DDDDD")

        def analyze_form(form_str):
            form_str = form_str[:10]

            winning_streak = 0
            losing_streak = 0
            unbeaten_run = 0
            winless_run = 0

            for char in form_str:
                if char == 'W':
                    winning_streak += 1
                    unbeaten_run += 1
                    winless_run = 0
                    losing_streak = 0
                elif char == 'D':
                    winning_streak = 0
                    unbeaten_run += 1
                    winless_run += 1
                    losing_streak = 0
                elif char == 'L':
                    losing_streak += 1
                    winless_run += 1
                    winning_streak = 0
                    unbeaten_run = 0

            momentum_score = 0.5

            momentum_score += winning_streak * 0.08
            momentum_score -= losing_streak * 0.10
            momentum_score += unbeaten_run * 0.03
            momentum_score -= winless_run * 0.02

            momentum_score = max(0.0, min(1.0, momentum_score))

            if form_str[0] == 'L' and form_str[1] == 'W':
                bounce_back = 0.15
            else:
                bounce_back = 0.0

            confidence = 0.5 + (winning_streak * 0.1) - (losing_streak * 0.12)
            confidence = max(0.0, min(1.0, confidence))

            return {
                "momentum": momentum_score + bounce_back,
                "winning_streak": winning_streak,
                "losing_streak": losing_streak,
                "unbeaten_run": unbeaten_run,
                "winless_run": winless_run,
                "confidence": confidence,
                "bounce_back": bounce_back
            }

        home_analysis = analyze_form(home_form_string)
        away_analysis = analyze_form(away_form_string)

        home_momentum = min(1.0, home_analysis["momentum"])
        away_momentum = min(1.0, away_analysis["momentum"])
        momentum_advantage = "home" if home_momentum > away_momentum else ("away" if away_momentum > home_momentum else "neutral")

        if home_analysis["winning_streak"] >= 3:
            home_streak_desc = f"Winning streak: {home_analysis['winning_streak']} matches"
        elif home_analysis["losing_streak"] >= 3:
            home_streak_desc = f"Losing streak: {home_analysis['losing_streak']} matches"
        elif home_analysis["unbeaten_run"] >= 5:
            home_streak_desc = f"Unbeaten: {home_analysis['unbeaten_run']} matches"
        else:
            home_streak_desc = "Mixed recent form"

        if away_analysis["winning_streak"] >= 3:
            away_streak_desc = f"Winning streak: {away_analysis['winning_streak']} matches"
        elif away_analysis["losing_streak"] >= 3:
            away_streak_desc = f"Losing streak: {away_analysis['losing_streak']} matches"
        elif away_analysis["unbeaten_run"] >= 5:
            away_streak_desc = f"Unbeaten: {away_analysis['unbeaten_run']} matches"
        else:
            away_streak_desc = "Mixed recent form"

        insights = [
            f"Home team: {home_streak_desc}",
            f"Away team: {away_streak_desc}",
            f"Momentum advantage: {momentum_advantage.title()}"
        ]

        if home_analysis["bounce_back"] > 0:
            insights.append("Home team may show bounce-back effect")
        if away_analysis["bounce_back"] > 0:
            insights.append("Away team may show bounce-back effect")

        return {
            "agent": self.name,
            "predictions": {
                "momentum_home": round(home_momentum, 3),
                "momentum_away": round(away_momentum, 3),
                "momentum_advantage": momentum_advantage,
                "confidence_rating_home": round(home_analysis["confidence"], 3),
                "confidence_rating_away": round(away_analysis["confidence"], 3),
                "winning_streak_home": home_analysis["winning_streak"],
                "losing_streak_home": home_analysis["losing_streak"],
                "winning_streak_away": away_analysis["winning_streak"],
                "losing_streak_away": away_analysis["losing_streak"],
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "goal_expectancy_home_multiplier": 0.92 + (home_momentum * 0.16),
                "goal_expectancy_away_multiplier": 0.92 + (away_momentum * 0.16),
                "confidence_multiplier_home": 0.95 + (home_analysis["confidence"] * 0.10),
                "confidence_multiplier_away": 0.95 + (away_analysis["confidence"] * 0.10),
            }
        }


class ManagerAgent:
    """Analyzes manager quality and tactical factors"""
    name = "manager_agent"
    specialty = "Manager quality and tactical battle"
    weight = 0.55
    reliability_score = 0.55

    MANAGERS = {
        # PREMIER LEAGUE
        "Manchester City": {"name": "Pep Guardiola", "experience_years": 20, "trophies": 38, "tactical_flexibility": 9, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["3-2-5", "4-1-4-1"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 9, "attacking_creativity": 9, "set_piece_coaching": 8, "mental_resilience": 9, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "Arsenal": {"name": "Mikel Arteta", "experience_years": 7, "trophies": 3, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-4-2-1"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 8, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Liverpool": {"name": "Arne Slot", "experience_years": 12, "trophies": 8, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-4-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 8, "set_piece_coaching": 7, "mental_resilience": 9, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Chelsea": {"name": "Enzo Maresca", "experience_years": 10, "trophies": 2, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-1-4-1", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 7, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": -1, "h2h_record_style": "adaptive"},
        "Manchester United": {"name": "Erik ten Hag", "experience_years": 15, "trophies": 8, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["3-4-3", "5-2-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "late", "defensive_organization": 7, "attacking_creativity": 7, "set_piece_coaching": 8, "mental_resilience": 7, "league_position_overperform": -1, "h2h_record_style": "conservative"},
        "Newcastle": {"name": "Eddie Howe", "experience_years": 15, "trophies": 2, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "4-1-4-1"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 6, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Tottenham": {"name": "Ange Postecoglou", "experience_years": 12, "trophies": 5, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-4-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "early", "defensive_organization": 6, "attacking_creativity": 8, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Aston Villa": {"name": "Unai Emery", "experience_years": 16, "trophies": 7, "tactical_flexibility": 8, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-1-4-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 7, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Brighton and Hove Albion": {"name": "Fabian Hürzeler", "experience_years": 7, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["3-4-3", "5-3-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "West Ham United": {"name": "Julen Lopetegui", "experience_years": 14, "trophies": 5, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["3-5-2", "4-3-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 7, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Bournemouth": {"name": "Andoni Iraola", "experience_years": 8, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-1-4-1", "3-4-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Crystal Palace": {"name": "Oliver Glasner", "experience_years": 10, "trophies": 2, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "3-4-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 5, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Wolverhampton Wanderers": {"name": "Gary O'Neil", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["3-5-2", "5-3-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 4, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": -1, "h2h_record_style": "defensive"},
        "Fulham": {"name": "Marco Silva", "experience_years": 11, "trophies": 3, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-1-4-1", "3-4-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Everton": {"name": "Sean Dyche", "experience_years": 14, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "4-4-2", "alt_formations": ["5-3-2", "3-5-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 3, "set_piece_coaching": 7, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Brentford": {"name": "Thomas Frank", "experience_years": 11, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 7, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "Nottingham Forest": {"name": "Nuno Espírito Santo", "experience_years": 13, "trophies": 3, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "3-4-3"], "management_style": "defensive", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 5, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Ipswich Town": {"name": "Kieran McKenna", "experience_years": 6, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Southampton": {"name": "Russell Martin", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["3-4-3", "5-2-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 6, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "aggressive"},

        # LA LIGA
        "Real Madrid": {"name": "Carlo Ancelotti", "experience_years": 25, "trophies": 24, "tactical_flexibility": 9, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 9, "set_piece_coaching": 8, "mental_resilience": 10, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Barcelona": {"name": "Hansi Flick", "experience_years": 15, "trophies": 10, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 9, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "Atletico Madrid": {"name": "Diego Simeone", "experience_years": 18, "trophies": 11, "tactical_flexibility": 7, "big_game_record": "strong", "preferred_formation": "4-4-2", "alt_formations": ["3-5-2", "5-3-2"], "management_style": "defensive", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 9, "attacking_creativity": 5, "set_piece_coaching": 7, "mental_resilience": 9, "league_position_overperform": 0, "h2h_record_style": "neutralizer"},
        "Real Sociedad": {"name": "Imanol Alguacil", "experience_years": 9, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-4-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 7, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Athletic Bilbao": {"name": "Ernesto Valverde", "experience_years": 20, "trophies": 8, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-4-2", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 6, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Real Betis": {"name": "Manuel Pellegrini", "experience_years": 16, "trophies": 9, "tactical_flexibility": 8, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-4-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 8, "set_piece_coaching": 6, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Villarreal": {"name": "Marcelino García Toral", "experience_years": 12, "trophies": 2, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Girona": {"name": "Michel", "experience_years": 10, "trophies": 3, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["3-4-3", "4-2-3-1"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "Sevilla": {"name": "García Pimienta", "experience_years": 8, "trophies": 2, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Valencia": {"name": "Carlos Corberán", "experience_years": 8, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "5-3-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Celta Vigo": {"name": "Rafael Benítez", "experience_years": 16, "trophies": 10, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "RCD Mallorca": {"name": "Javier Aguirre", "experience_years": 20, "trophies": 3, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-4-2", "3-5-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 3, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "CA Osasuna": {"name": "Jagoba Arrasate", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "3-4-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Getafe": {"name": "José Bordalás", "experience_years": 12, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "4-4-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 9, "attacking_creativity": 2, "set_piece_coaching": 7, "mental_resilience": 7, "league_position_overperform": 1, "h2h_record_style": "neutralizer"},
        "Rayo Vallecano": {"name": "Iñigo Pérez", "experience_years": 6, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 6, "set_piece_coaching": 4, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Las Palmas": {"name": "Luis Carrión", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Alaves": {"name": "Luis García Plaza", "experience_years": 9, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "4-4-2", "alt_formations": ["5-3-2", "3-5-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 2, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},

        # SERIE A
        "Inter": {"name": "Simone Inzaghi", "experience_years": 12, "trophies": 6, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "3-5-2", "alt_formations": ["4-2-3-1", "5-3-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 9, "set_piece_coaching": 8, "mental_resilience": 8, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "AC Milan": {"name": "Paulo Fonseca", "experience_years": 10, "trophies": 3, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-4-3"], "management_style": "pragmatic", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 7, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Juventus": {"name": "Thiago Motta", "experience_years": 5, "trophies": 0, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["3-5-2", "4-3-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Napoli": {"name": "Antonio Conte", "experience_years": 17, "trophies": 14, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "4-2-3-1"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 7, "set_piece_coaching": 8, "mental_resilience": 9, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "AS Roma": {"name": "Ivan Juric", "experience_years": 8, "trophies": 2, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-4-2-1", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "early", "defensive_organization": 5, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Lazio": {"name": "Marco Baroni", "experience_years": 9, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Atalanta": {"name": "Gian Piero Gasperini", "experience_years": 14, "trophies": 4, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "3-4-2-1", "alt_formations": ["4-3-3", "5-2-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 9, "set_piece_coaching": 6, "mental_resilience": 8, "league_position_overperform": 1, "h2h_record_style": "aggressive"},
        "Fiorentina": {"name": "Raffaele Palladino", "experience_years": 8, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Bologna": {"name": "Vincenzo Italiano", "experience_years": 8, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Torino": {"name": "Paolo Vanoli", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "defensive", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Monza": {"name": "Alessandro Nesta", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Udinese": {"name": "Kosta Runjaic", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "4-2-3-1"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Sassuolo": {"name": "Fabio Grosso", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 6, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Empoli": {"name": "Roberto D'Aversa", "experience_years": 9, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "4-2-3-1"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Cagliari": {"name": "Davide Nicola", "experience_years": 10, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["3-5-2", "5-3-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 7, "attacking_creativity": 3, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Lecce": {"name": "Marco Giampaolo", "experience_years": 9, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Genoa": {"name": "Alberto Gilardino", "experience_years": 4, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 7, "attacking_creativity": 3, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Verona": {"name": "Marco Baroni", "experience_years": 9, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["3-5-2", "4-2-3-1"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},

        # BUNDESLIGA
        "Bayern Munich": {"name": "Vincent Kompany", "experience_years": 4, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["3-5-2", "4-3-3"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 8, "set_piece_coaching": 7, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Borussia Dortmund": {"name": "Nuri Sahin", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Bayer Leverkusen": {"name": "Xabi Alonso", "experience_years": 6, "trophies": 2, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "4-1-4-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 8, "set_piece_coaching": 6, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "RB Leipzig": {"name": "Marco Rose", "experience_years": 10, "trophies": 4, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-4-2", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "VfB Stuttgart": {"name": "Sebastian Hoeneß", "experience_years": 8, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 7, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 1, "h2h_record_style": "adaptive"},
        "Eintracht Frankfurt": {"name": "Dino Toppmöller", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-4-2", "alt_formations": ["3-5-2", "4-3-3"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "VfL Wolfsburg": {"name": "Ralph Hasenhüttl", "experience_years": 11, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "SC Freiburg": {"name": "Christian Streich", "experience_years": 14, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-4-2", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "TSG Hoffenheim": {"name": "Pellegrino Matarazzo", "experience_years": 6, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 6, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "1. FSV Mainz 05": {"name": "Bo Henriksen", "experience_years": 4, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "FC Augsburg": {"name": "Jess Thorup", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "3-5-2", "alt_formations": ["4-3-3", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Heidenheim 1846": {"name": "Frank Schmidt", "experience_years": 12, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "5-3-2", "alt_formations": ["3-5-2", "4-3-3"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "late", "defensive_organization": 8, "attacking_creativity": 2, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Werder Bremen": {"name": "Ole Werner", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "VfL Bochum": {"name": "Peter Zeidler", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Union Berlin": {"name": "Urs Fischer", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["5-3-2", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Darmstadt 98": {"name": "Florian Kohfeldt", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 4, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "1. FC Cologne": {"name": "Gerhard Struber", "experience_years": 7, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Borussia Mönchengladbach": {"name": "Daniel Farke", "experience_years": 9, "trophies": 1, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},

        # LIGUE 1
        "Paris Saint-Germain": {"name": "Luis Enrique", "experience_years": 12, "trophies": 9, "tactical_flexibility": 8, "big_game_record": "strong", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "low", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 8, "attacking_creativity": 9, "set_piece_coaching": 7, "mental_resilience": 8, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Olympique de Marseille": {"name": "Jean-Louis Gasset", "experience_years": 30, "trophies": 6, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 7, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "AS Monaco": {"name": "Adi Hütter", "experience_years": 10, "trophies": 3, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-4-2", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 6, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "Olympique Lyonnais": {"name": "Pierre Sage", "experience_years": 6, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "LOSC Lille": {"name": "Paulo Fonseca", "experience_years": 10, "trophies": 3, "tactical_flexibility": 7, "big_game_record": "average", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 6, "set_piece_coaching": 6, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "adaptive"},
        "OGC Nice": {"name": "Franck Haise", "experience_years": 7, "trophies": 1, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "RC Lens": {"name": "Will Still", "experience_years": 4, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "attacking", "pressing_intensity": "high", "counter_attack_tendency": "high", "youth_trust": "high", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 6, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "aggressive"},
        "Stade Rennes": {"name": "Julien Stéphan", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "RC Strasbourg": {"name": "Liam Rosenior", "experience_years": 5, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-2-3-1", "alt_formations": ["4-3-3", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 5, "set_piece_coaching": 5, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Montpellier HSC": {"name": "Jean-Louis Gasset", "experience_years": 30, "trophies": 6, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Toulouse FC": {"name": "Philippe Montanier", "experience_years": 12, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "FC Nantes": {"name": "Antoine Kombouaré", "experience_years": 9, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "medium", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Stade de Reims": {"name": "Luka Elsner", "experience_years": 5, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "pragmatic", "pressing_intensity": "low", "counter_attack_tendency": "medium", "youth_trust": "low", "sub_timing": "normal", "defensive_organization": 6, "attacking_creativity": 3, "set_piece_coaching": 4, "mental_resilience": 5, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Stade Brest": {"name": "Eric Roy", "experience_years": 8, "trophies": 0, "tactical_flexibility": 6, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "3-5-2"], "management_style": "defensive", "pressing_intensity": "low", "counter_attack_tendency": "high", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 7, "attacking_creativity": 4, "set_piece_coaching": 5, "mental_resilience": 6, "league_position_overperform": 0, "h2h_record_style": "defensive"},
        "Le Havre AC": {"name": "Didier Digard", "experience_years": 4, "trophies": 0, "tactical_flexibility": 5, "big_game_record": "weak", "preferred_formation": "4-3-3", "alt_formations": ["4-2-3-1", "5-3-2"], "management_style": "pragmatic", "pressing_intensity": "low", "counter_attack_tendency": "medium", "youth_trust": "medium", "sub_timing": "normal", "defensive_organization": 5, "attacking_creativity": 3, "set_piece_coaching": 4, "mental_resilience": 4, "league_position_overperform": 0, "h2h_record_style": "defensive"},
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        home_mgr = self.MANAGERS.get(home_team, {
            "name": "Unknown Manager",
            "experience_years": 5,
            "trophies": 1,
            "tactical_flexibility": 5,
            "big_game_record": "average",
            "preferred_formation": "4-3-3",
            "alt_formations": ["4-2-3-1"],
            "management_style": "pragmatic",
            "pressing_intensity": "medium",
            "counter_attack_tendency": "medium",
            "youth_trust": "low",
            "sub_timing": "normal",
            "defensive_organization": 6,
            "attacking_creativity": 5,
            "set_piece_coaching": 5,
            "mental_resilience": 6,
            "league_position_overperform": 0,
            "h2h_record_style": "adaptive"
        })

        away_mgr = self.MANAGERS.get(away_team, {
            "name": "Unknown Manager",
            "experience_years": 5,
            "trophies": 1,
            "tactical_flexibility": 5,
            "big_game_record": "average",
            "preferred_formation": "4-3-3",
            "alt_formations": ["4-2-3-1"],
            "management_style": "pragmatic",
            "pressing_intensity": "medium",
            "counter_attack_tendency": "medium",
            "youth_trust": "low",
            "sub_timing": "normal",
            "defensive_organization": 6,
            "attacking_creativity": 5,
            "set_piece_coaching": 5,
            "mental_resilience": 6,
            "league_position_overperform": 0,
            "h2h_record_style": "adaptive"
        })

        home_quality = (home_mgr["experience_years"] * 0.3 + home_mgr["trophies"] * 0.4 + home_mgr["tactical_flexibility"] * 2) / 10
        away_quality = (away_mgr["experience_years"] * 0.3 + away_mgr["trophies"] * 0.4 + away_mgr["tactical_flexibility"] * 2) / 10

        if home_quality > away_quality + 1.5:
            manager_advantage = "home"
            advantage_size = min(0.12, (home_quality - away_quality) * 0.02)
        elif away_quality > home_quality + 1.5:
            manager_advantage = "away"
            advantage_size = min(0.12, (away_quality - home_quality) * 0.02)
        else:
            manager_advantage = "neutral"
            advantage_size = 0.0

        if home_mgr["big_game_record"] == "strong" and away_mgr["big_game_record"] != "strong":
            tactical_winner = "home"
        elif away_mgr["big_game_record"] == "strong" and home_mgr["big_game_record"] != "strong":
            tactical_winner = "away"
        else:
            tactical_winner = "even"

        home_adjustment = min(9, max(3, (home_mgr["tactical_flexibility"] + home_mgr["experience_years"] / 5)))
        away_adjustment = min(9, max(3, (away_mgr["tactical_flexibility"] + away_mgr["experience_years"] / 5)))

        insights = [
            f"Home manager: {home_mgr['name']} ({home_mgr['experience_years']} years, {home_mgr['trophies']} trophies)",
            f"Away manager: {away_mgr['name']} ({away_mgr['experience_years']} years, {away_mgr['trophies']} trophies)",
            f"Tactical battle: {tactical_winner.title()}, {home_mgr['preferred_formation']} vs {away_mgr['preferred_formation']}"
        ]

        if home_mgr["management_style"] != away_mgr["management_style"]:
            insights.append(f"Contrasting styles: {home_mgr['management_style']} vs {away_mgr['management_style']}")

        if home_mgr["pressing_intensity"] != away_mgr["pressing_intensity"]:
            insights.append(f"Pressing intensity mismatch: {home_mgr['pressing_intensity']} vs {away_mgr['pressing_intensity']}")

        return {
            "agent": self.name,
            "predictions": {
                "manager_advantage": manager_advantage,
                "advantage_magnitude": round(advantage_size, 3),
                "tactical_battle_winner": tactical_winner,
                "in_game_adjustment_rating_home": int(home_adjustment),
                "in_game_adjustment_rating_away": int(away_adjustment),
                "home_manager": home_mgr["name"],
                "away_manager": away_mgr["name"],
                "home_pressing_intensity": home_mgr["pressing_intensity"],
                "away_pressing_intensity": away_mgr["pressing_intensity"],
                "home_counter_attack_tendency": home_mgr["counter_attack_tendency"],
                "away_counter_attack_tendency": away_mgr["counter_attack_tendency"],
                "home_youth_trust": home_mgr["youth_trust"],
                "away_youth_trust": away_mgr["youth_trust"],
                "home_sub_timing": home_mgr["sub_timing"],
                "away_sub_timing": away_mgr["sub_timing"],
                "home_defensive_organization": home_mgr["defensive_organization"],
                "away_defensive_organization": away_mgr["defensive_organization"],
                "home_attacking_creativity": home_mgr["attacking_creativity"],
                "away_attacking_creativity": away_mgr["attacking_creativity"],
                "home_set_piece_coaching": home_mgr["set_piece_coaching"],
                "away_set_piece_coaching": away_mgr["set_piece_coaching"],
                "home_mental_resilience": home_mgr["mental_resilience"],
                "away_mental_resilience": away_mgr["mental_resilience"],
                "home_league_position_overperform": home_mgr["league_position_overperform"],
                "away_league_position_overperform": away_mgr["league_position_overperform"],
                "home_h2h_record_style": home_mgr["h2h_record_style"],
                "away_h2h_record_style": away_mgr["h2h_record_style"],
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "manager_tactical_advantage": 1.0 + advantage_size if manager_advantage == "home" else (1.0 - advantage_size if manager_advantage == "away" else 1.0),
                "in_game_adaptation_home": 1.0 + (home_adjustment - 6) * 0.02,
                "in_game_adaptation_away": 1.0 + (away_adjustment - 6) * 0.02,
                "defensive_organization_home": 0.95 + (home_mgr["defensive_organization"] * 0.01),
                "defensive_organization_away": 0.95 + (away_mgr["defensive_organization"] * 0.01),
                "attacking_creativity_home": 0.95 + (home_mgr["attacking_creativity"] * 0.01),
                "attacking_creativity_away": 0.95 + (away_mgr["attacking_creativity"] * 0.01),
            }
        }


class MediaPressureAgent:
    """Analyzes external media pressure and its impact on performance"""
    name = "media_pressure_agent"
    specialty = "External pressure and media factors"
    weight = 0.35
    reliability_score = 0.35

    BIG_CLUBS = {
        "Manchester City", "Manchester United", "Liverpool", "Arsenal", "Chelsea",
        "Real Madrid", "Barcelona", "Atletico Madrid",
        "Bayern Munich", "Borussia Dortmund",
        "Paris Saint-Germain", "Marseille",
        "Inter Milan", "AC Milan", "Juventus", "Napoli", "AS Roma"
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        home_pressure = 0.3
        away_pressure = 0.3

        if home_team in self.BIG_CLUBS:
            home_pressure += 0.25
        if away_team in self.BIG_CLUBS:
            away_pressure += 0.25

        home_form_str = home_form.get("form_string", "")
        away_form_str = away_form.get("form_string", "")

        if home_form_str and home_form_str[:3].count('L') >= 2:
            home_pressure += 0.15
        if away_form_str and away_form_str[:3].count('L') >= 2:
            away_pressure += 0.15

        home_distraction = min(0.20, home_pressure * 0.4)
        away_distraction = min(0.20, away_pressure * 0.4)

        home_focus = 1.0 - home_distraction
        away_focus = 1.0 - away_distraction

        if home_pressure > away_pressure:
            pressure_advantage = "away"
        elif away_pressure > home_pressure:
            pressure_advantage = "home"
        else:
            pressure_advantage = "neutral"

        insights = []

        if home_team in self.BIG_CLUBS:
            insights.append(f"{home_team} - major club under constant scrutiny")
        else:
            insights.append(f"{home_team} - moderate media attention")

        if away_team in self.BIG_CLUBS:
            insights.append(f"{away_team} - major club under constant scrutiny")
        else:
            insights.append(f"{away_team} - moderate media attention")

        if home_form_str and home_form_str[:3].count('L') >= 2:
            insights.append("Home team in poor form - increased pressure to perform")

        if away_form_str and away_form_str[:3].count('L') >= 2:
            insights.append("Away team in poor form - increased pressure to perform")

        return {
            "agent": self.name,
            "predictions": {
                "pressure_level_home": round(home_pressure, 2),
                "pressure_level_away": round(away_pressure, 2),
                "distraction_factor_home": round(home_distraction, 3),
                "distraction_factor_away": round(away_distraction, 3),
                "focus_rating_home": round(home_focus, 3),
                "focus_rating_away": round(away_focus, 3),
                "pressure_advantage": pressure_advantage
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "focus_multiplier_home": 1.0 - (home_distraction * 0.5),
                "focus_multiplier_away": 1.0 - (away_distraction * 0.5),
                "performance_under_pressure_home": 0.98,
                "performance_under_pressure_away": 0.98,
            }
        }


class RestDaysAgent:
    """Analyzes rest and recovery factors"""
    name = "rest_days_agent"
    specialty = "Rest and fixture congestion factors"
    weight = 0.55
    reliability_score = 0.55

    CONTINENTAL_TEAMS = {
        "Manchester City", "Manchester United", "Liverpool", "Arsenal", "Chelsea",
        "Real Madrid", "Barcelona", "Atletico Madrid",
        "Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig",
        "Paris Saint-Germain", "Marseille", "Lyon",
        "Inter Milan", "AC Milan", "Juventus", "Napoli", "AS Roma",
        "Girona", "Athletic Bilbao", "Valencia"
    }

    TYPICAL_REST_DAYS = {
        "league": {"min": 4, "max": 7, "typical": 5},
        "european_week": {"min": 2, "max": 4, "typical": 3},
        "congestion": {"min": 1, "max": 3, "typical": 2}
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")

        home_continental = home_team in self.CONTINENTAL_TEAMS
        away_continental = away_team in self.CONTINENTAL_TEAMS

        home_form_str = home_form.get("form_string", "")
        away_form_str = away_form.get("form_string", "")

        if home_continental:
            rest_days_home = random.randint(2, 4)
        else:
            rest_days_home = random.randint(4, 7)

        if away_continental:
            rest_days_away = random.randint(2, 4)
        else:
            rest_days_away = random.randint(4, 7)

        ideal_rest = 5
        rest_diff = rest_days_home - rest_days_away

        if abs(rest_diff) >= 3:
            if rest_diff > 0:
                rest_advantage = "home"
                rest_advantage_val = 0.08
            else:
                rest_advantage = "away"
                rest_advantage_val = 0.08
        else:
            rest_advantage = "neutral"
            rest_advantage_val = 0.0

        freshness_home = 0.5 + (min(abs(rest_days_home - ideal_rest), 3) / 3.0) * 0.3
        freshness_away = 0.5 + (min(abs(rest_days_away - ideal_rest), 3) / 3.0) * 0.3

        if rest_days_home < 3:
            freshness_home = 0.6
        if rest_days_away < 3:
            freshness_away = 0.6

        second_half_energy_home = "high" if rest_days_home >= 5 else ("moderate" if rest_days_home >= 3 else "low")
        second_half_energy_away = "high" if rest_days_away >= 5 else ("moderate" if rest_days_away >= 3 else "low")

        insights = [
            f"Home team rest: {rest_days_home} days - {second_half_energy_home.title()} second half energy expected",
            f"Away team rest: {rest_days_away} days - {second_half_energy_away.title()} second half energy expected",
        ]

        if rest_advantage != "neutral":
            insights.append(f"Rest advantage: {rest_advantage.title()} team")

        if home_continental or away_continental:
            insights.append("European competition fixture congestion may impact recovery")

        return {
            "agent": self.name,
            "predictions": {
                "rest_days_home": rest_days_home,
                "rest_days_away": rest_days_away,
                "rest_advantage_team": rest_advantage,
                "rest_advantage_magnitude": round(rest_advantage_val, 3),
                "freshness_home": round(freshness_home, 3),
                "freshness_away": round(freshness_away, 3),
                "second_half_energy_home": second_half_energy_home,
                "second_half_energy_away": second_half_energy_away,
                "home_continental_competition": home_continental,
                "away_continental_competition": away_continental
            },
            "confidence": self.reliability_score,
            "insights": insights,
            "adjustments": {
                "freshness_multiplier_home": 0.95 + (freshness_home * 0.10),
                "freshness_multiplier_away": 0.95 + (freshness_away * 0.10),
                "second_half_intensity_home": 0.98 if second_half_energy_home == "high" else (1.0 if second_half_energy_home == "moderate" else 1.02),
                "second_half_intensity_away": 0.98 if second_half_energy_away == "high" else (1.0 if second_half_energy_away == "moderate" else 1.02),
            }
        }
