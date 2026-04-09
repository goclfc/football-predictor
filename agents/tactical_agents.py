"""
Tactical Analysis Agents for Football Match Prediction
Provides 4 specialized agents analyzing tactical, set piece, defensive, and attacking dimensions
"""


class TacticalAgent:
    """Analyzes formation compatibility, tactical matchups, and pressing dynamics"""
    name = "tactical_agent"
    specialty = "formation_compatibility and tactical_matchups"
    weight = 0.70
    reliability_score = 0.65

    TEAM_TACTICS = {
        # English Premier League
        "Manchester City": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "Liverpool": {
            "formation": "4-3-3",
            "style": "pressing",
            "pressing_intensity": 9,
            "defensive_line": "high",
            "build_up": "mixed",
            "width": "wide"
        },
        "Manchester United": {
            "formation": "4-2-3-1",
            "style": "balanced",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "Chelsea": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "Arsenal": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "Tottenham": {
            "formation": "4-2-3-1",
            "style": "counter_attack",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "long",
            "width": "wide"
        },
        "Newcastle United": {
            "formation": "4-3-3",
            "style": "defensive",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "long",
            "width": "narrow"
        },
        "Brighton": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 7,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "Aston Villa": {
            "formation": "4-2-3-1",
            "style": "balanced",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "West Ham": {
            "formation": "4-2-3-1",
            "style": "counter_attack",
            "pressing_intensity": 5,
            "defensive_line": "low",
            "build_up": "long",
            "width": "narrow"
        },
        # La Liga
        "Real Madrid": {
            "formation": "4-3-3",
            "style": "balanced",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "Barcelona": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "Atletico Madrid": {
            "formation": "4-4-2",
            "style": "defensive",
            "pressing_intensity": 6,
            "defensive_line": "low",
            "build_up": "long",
            "width": "narrow"
        },
        "Sevilla": {
            "formation": "4-3-3",
            "style": "balanced",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "Villarreal": {
            "formation": "4-4-2",
            "style": "defensive",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "long",
            "width": "narrow"
        },
        "Real Betis": {
            "formation": "4-2-3-1",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "Valencia": {
            "formation": "4-3-3",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        # Serie A
        "Inter Milan": {
            "formation": "3-5-2",
            "style": "possession",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "AC Milan": {
            "formation": "4-2-3-1",
            "style": "balanced",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "Juventus": {
            "formation": "4-3-3",
            "style": "defensive",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "narrow"
        },
        "Roma": {
            "formation": "3-4-2-1",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "Lazio": {
            "formation": "4-3-3",
            "style": "counter_attack",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "long",
            "width": "wide"
        },
        "Napoli": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        # Bundesliga
        "Bayern Munich": {
            "formation": "4-2-3-1",
            "style": "possession",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "Borussia Dortmund": {
            "formation": "4-2-3-1",
            "style": "counter_attack",
            "pressing_intensity": 8,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
        "Bayer Leverkusen": {
            "formation": "4-3-3",
            "style": "pressing",
            "pressing_intensity": 8,
            "defensive_line": "high",
            "build_up": "short",
            "width": "wide"
        },
        "RB Leipzig": {
            "formation": "4-3-3",
            "style": "pressing",
            "pressing_intensity": 9,
            "defensive_line": "high",
            "build_up": "mixed",
            "width": "wide"
        },
        "Schalke 04": {
            "formation": "4-4-2",
            "style": "defensive",
            "pressing_intensity": 5,
            "defensive_line": "low",
            "build_up": "long",
            "width": "narrow"
        },
        # Ligue 1
        "Paris Saint-Germain": {
            "formation": "4-3-3",
            "style": "possession",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "Marseille": {
            "formation": "4-2-3-1",
            "style": "counter_attack",
            "pressing_intensity": 7,
            "defensive_line": "mid",
            "build_up": "long",
            "width": "wide"
        },
        "AS Monaco": {
            "formation": "4-4-2",
            "style": "counter_attack",
            "pressing_intensity": 6,
            "defensive_line": "low",
            "build_up": "long",
            "width": "wide"
        },
        "Lyon": {
            "formation": "3-5-2",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "short",
            "width": "wide"
        },
        "Nice": {
            "formation": "4-3-3",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide"
        },
    }

    STYLE_MATCHUP_MATRIX = {
        ("possession", "possession"): 0.0,
        ("possession", "pressing"): -0.15,
        ("possession", "counter_attack"): -0.10,
        ("possession", "defensive"): 0.10,
        ("possession", "balanced"): 0.05,
        ("pressing", "possession"): 0.15,
        ("pressing", "pressing"): 0.0,
        ("pressing", "counter_attack"): -0.12,
        ("pressing", "defensive"): -0.08,
        ("pressing", "balanced"): 0.05,
        ("counter_attack", "possession"): 0.10,
        ("counter_attack", "pressing"): 0.12,
        ("counter_attack", "counter_attack"): 0.0,
        ("counter_attack", "defensive"): 0.05,
        ("counter_attack", "balanced"): 0.08,
        ("defensive", "possession"): -0.10,
        ("defensive", "pressing"): 0.08,
        ("defensive", "counter_attack"): -0.05,
        ("defensive", "defensive"): 0.0,
        ("defensive", "balanced"): 0.02,
        ("balanced", "possession"): -0.05,
        ("balanced", "pressing"): -0.05,
        ("balanced", "counter_attack"): -0.08,
        ("balanced", "defensive"): -0.02,
        ("balanced", "balanced"): 0.0,
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        """
        Analyze tactical matchup between teams

        Returns dict with:
        - agent: agent name
        - predictions: tactical predictions
        - confidence: confidence score
        - insights: tactical insights
        - adjustments: suggested probability adjustments
        """
        home_team = match_data.get("home_team")
        away_team = match_data.get("away_team")

        # Get tactical profiles
        home_tactics = self.TEAM_TACTICS.get(home_team, self._get_default_tactics())
        away_tactics = self.TEAM_TACTICS.get(away_team, self._get_default_tactics())

        # Calculate tactical matchup advantage
        matchup_key = (home_tactics["style"], away_tactics["style"])
        tactical_edge = self.STYLE_MATCHUP_MATRIX.get(matchup_key, 0.0)

        # Formation compatibility analysis
        formation_clash_score = self._calculate_formation_clash(home_tactics, away_tactics)

        # Possession prediction based on styles
        possession_prediction = self._predict_possession(home_tactics, away_tactics)

        # Pressing duel prediction
        pressing_winner = self._predict_pressing_winner(home_tactics, away_tactics)

        # Confidence based on data quality
        confidence = 0.65
        if home_form and away_form:
            confidence += 0.05
        if h2h:
            confidence += 0.05

        predictions = {
            "tactical_edge": tactical_edge,
            "possession_prediction": possession_prediction,
            "pressing_winner": pressing_winner,
            "formation_clash_score": formation_clash_score,
            "home_tactics": home_tactics,
            "away_tactics": away_tactics,
        }

        insights = [
            f"Home team plays {home_tactics['style']} style with {home_tactics['formation']} formation",
            f"Away team plays {away_tactics['style']} style with {away_tactics['formation']} formation",
            f"Tactical matchup advantage: {('Home' if tactical_edge > 0 else 'Away')} ({abs(tactical_edge):.2f})",
            f"Expected possession: Home {possession_prediction*100:.0f}%, Away {(1-possession_prediction)*100:.0f}%",
            f"Pressing intensity match: Home {home_tactics['pressing_intensity']}/10 vs Away {away_tactics['pressing_intensity']}/10",
        ]

        adjustments = {
            "xg_adjustment": tactical_edge * 0.3,
            "possession_adjustment": (possession_prediction - 0.5) * 0.2,
            "pressing_adjustment": (1.0 if pressing_winner == "home" else -1.0) * 0.1,
        }

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": confidence,
            "insights": insights,
            "adjustments": adjustments,
        }

    def _get_default_tactics(self):
        return {
            "formation": "4-3-3",
            "style": "balanced",
            "pressing_intensity": 6,
            "defensive_line": "mid",
            "build_up": "mixed",
            "width": "wide",
        }

    def _calculate_formation_clash(self, home_tactics, away_tactics):
        """Calculate how well formations match up (0-1)"""
        home_def = int(home_tactics["formation"].split("-")[0])
        away_def = int(away_tactics["formation"].split("-")[0])
        clash = 1.0 - (abs(home_def - away_def) * 0.1)
        return max(0.0, min(1.0, clash))

    def _predict_possession(self, home_tactics, away_tactics):
        """Predict possession share for home team (0-1)"""
        style_possession_map = {
            "possession": 0.7,
            "pressing": 0.6,
            "balanced": 0.5,
            "counter_attack": 0.35,
            "defensive": 0.3,
        }
        home_possession = style_possession_map.get(home_tactics["style"], 0.5)
        away_possession = style_possession_map.get(away_tactics["style"], 0.5)
        total = home_possession + away_possession
        return home_possession / total if total > 0 else 0.5

    def _predict_pressing_winner(self, home_tactics, away_tactics):
        """Predict which team wins the pressing duel"""
        if home_tactics["pressing_intensity"] > away_tactics["pressing_intensity"] + 1:
            return "home"
        elif away_tactics["pressing_intensity"] > home_tactics["pressing_intensity"] + 1:
            return "away"
        else:
            return "neutral"


class SetPieceAgent:
    """Analyzes set piece threats, corner dangers, and dead ball opportunities"""
    name = "set_piece_agent"
    specialty = "corner_threats and dead_ball_opportunities"
    weight = 0.55
    reliability_score = 0.55

    SET_PIECE_RATINGS = {
        # English Premier League
        "Manchester City": {
            "corner_threat": 7,
            "free_kick_specialists": ["De Bruyne", "Foden", "Alvarez"],
            "penalty_taker": "Haaland",
            "penalty_conversion_pct": 0.88,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "Liverpool": {
            "corner_threat": 8,
            "free_kick_specialists": ["Alexander-Arnold", "Salah", "Van Dijk"],
            "penalty_taker": "Salah",
            "penalty_conversion_pct": 0.82,
            "corner_goals_per_game": 0.18,
            "aerial_threat": 7,
            "defensive_set_piece": 8,
        },
        "Manchester United": {
            "corner_threat": 7,
            "free_kick_specialists": ["Bruno Fernandes", "Shaw", "Rashford"],
            "penalty_taker": "Bruno Fernandes",
            "penalty_conversion_pct": 0.85,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 7,
            "defensive_set_piece": 6,
        },
        "Chelsea": {
            "corner_threat": 7,
            "free_kick_specialists": ["Mount", "Reece James", "Mudryk"],
            "penalty_taker": "Palmer",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.13,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "Arsenal": {
            "corner_threat": 8,
            "free_kick_specialists": ["Saka", "Odegaard", "Martinelli"],
            "penalty_taker": "Odegaard",
            "penalty_conversion_pct": 0.83,
            "corner_goals_per_game": 0.16,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "Tottenham": {
            "corner_threat": 6,
            "free_kick_specialists": ["Maddison", "Sarr", "Son"],
            "penalty_taker": "Son",
            "penalty_conversion_pct": 0.81,
            "corner_goals_per_game": 0.10,
            "aerial_threat": 5,
            "defensive_set_piece": 6,
        },
        "Newcastle United": {
            "corner_threat": 7,
            "free_kick_specialists": ["Trippier", "De Bruyne", "Joelinton"],
            "penalty_taker": "Isak",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.15,
            "aerial_threat": 7,
            "defensive_set_piece": 7,
        },
        "Brighton": {
            "corner_threat": 6,
            "free_kick_specialists": ["Moder", "Trossard", "Caicedo"],
            "penalty_taker": "Mitoma",
            "penalty_conversion_pct": 0.78,
            "corner_goals_per_game": 0.09,
            "aerial_threat": 5,
            "defensive_set_piece": 6,
        },
        "Aston Villa": {
            "corner_threat": 7,
            "free_kick_specialists": ["McGinn", "Rogers", "Buendia"],
            "penalty_taker": "Watkins",
            "penalty_conversion_pct": 0.82,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 7,
            "defensive_set_piece": 6,
        },
        "West Ham": {
            "corner_threat": 6,
            "free_kick_specialists": ["Bowen", "Soucek", "Ayew"],
            "penalty_taker": "Bowen",
            "penalty_conversion_pct": 0.77,
            "corner_goals_per_game": 0.11,
            "aerial_threat": 6,
            "defensive_set_piece": 5,
        },
        # La Liga
        "Real Madrid": {
            "corner_threat": 8,
            "free_kick_specialists": ["Modric", "Kroos", "Benzema"],
            "penalty_taker": "Benzema",
            "penalty_conversion_pct": 0.86,
            "corner_goals_per_game": 0.17,
            "aerial_threat": 7,
            "defensive_set_piece": 8,
        },
        "Barcelona": {
            "corner_threat": 7,
            "free_kick_specialists": ["Pedri", "Gavi", "Lewandowski"],
            "penalty_taker": "Lewandowski",
            "penalty_conversion_pct": 0.87,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "Atletico Madrid": {
            "corner_threat": 7,
            "free_kick_specialists": ["Griezmann", "De Paul", "Savic"],
            "penalty_taker": "Morata",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.16,
            "aerial_threat": 8,
            "defensive_set_piece": 8,
        },
        "Sevilla": {
            "corner_threat": 6,
            "free_kick_specialists": ["Nacho Fernandez", "Suso", "Lamela"],
            "penalty_taker": "En-Nesyri",
            "penalty_conversion_pct": 0.79,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "Villarreal": {
            "corner_threat": 6,
            "free_kick_specialists": ["Yeremy Pino", "Parejo", "Capoue"],
            "penalty_taker": "Nicolas Jackson",
            "penalty_conversion_pct": 0.81,
            "corner_goals_per_game": 0.11,
            "aerial_threat": 5,
            "defensive_set_piece": 7,
        },
        "Real Betis": {
            "corner_threat": 6,
            "free_kick_specialists": ["Canales", "Ruibal", "Fekir"],
            "penalty_taker": "Fekir",
            "penalty_conversion_pct": 0.83,
            "corner_goals_per_game": 0.13,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "Valencia": {
            "corner_threat": 5,
            "free_kick_specialists": ["Gaya", "Musah", "Castillejo"],
            "penalty_taker": "Castillejo",
            "penalty_conversion_pct": 0.76,
            "corner_goals_per_game": 0.09,
            "aerial_threat": 5,
            "defensive_set_piece": 5,
        },
        # Serie A
        "Inter Milan": {
            "corner_threat": 7,
            "free_kick_specialists": ["Calhanoglu", "Barella", "De Vrij"],
            "penalty_taker": "Calhanoglu",
            "penalty_conversion_pct": 0.84,
            "corner_goals_per_game": 0.15,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "AC Milan": {
            "corner_threat": 7,
            "free_kick_specialists": ["Tonali", "Pulisic", "Theo Hernandez"],
            "penalty_taker": "Ibrahimovic",
            "penalty_conversion_pct": 0.88,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 7,
            "defensive_set_piece": 7,
        },
        "Juventus": {
            "corner_threat": 7,
            "free_kick_specialists": ["Pjanic", "Cuadrado", "De Sciglio"],
            "penalty_taker": "Vlahovic",
            "penalty_conversion_pct": 0.82,
            "corner_goals_per_game": 0.13,
            "aerial_threat": 7,
            "defensive_set_piece": 8,
        },
        "Roma": {
            "corner_threat": 6,
            "free_kick_specialists": ["Pellegrini", "Dybala", "Mancini"],
            "penalty_taker": "Pellegrini",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.11,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "Lazio": {
            "corner_threat": 6,
            "free_kick_specialists": ["Luis Alberto", "Zaccagni", "Gila"],
            "penalty_taker": "Immobile",
            "penalty_conversion_pct": 0.81,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 5,
            "defensive_set_piece": 5,
        },
        "Napoli": {
            "corner_threat": 7,
            "free_kick_specialists": ["Kvaratskhelia", "Lobotka", "Kim"],
            "penalty_taker": "Osimhen",
            "penalty_conversion_pct": 0.83,
            "corner_goals_per_game": 0.15,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        # Bundesliga
        "Bayern Munich": {
            "corner_threat": 8,
            "free_kick_specialists": ["Muller", "Sane", "Goretzka"],
            "penalty_taker": "Muller",
            "penalty_conversion_pct": 0.89,
            "corner_goals_per_game": 0.18,
            "aerial_threat": 7,
            "defensive_set_piece": 8,
        },
        "Borussia Dortmund": {
            "corner_threat": 7,
            "free_kick_specialists": ["Reus", "Bellingham", "Sancho"],
            "penalty_taker": "Sancho",
            "penalty_conversion_pct": 0.85,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "Bayer Leverkusen": {
            "corner_threat": 7,
            "free_kick_specialists": ["Wirtz", "Grimaldo", "Tapsoba"],
            "penalty_taker": "Schick",
            "penalty_conversion_pct": 0.84,
            "corner_goals_per_game": 0.15,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "RB Leipzig": {
            "corner_threat": 6,
            "free_kick_specialists": ["Sabitzer", "Nkunku", "Gvardiol"],
            "penalty_taker": "Nkunku",
            "penalty_conversion_pct": 0.82,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 6,
            "defensive_set_piece": 7,
        },
        "Schalke 04": {
            "corner_threat": 5,
            "free_kick_specialists": ["Frimpong", "Schopf", "Thiaw"],
            "penalty_taker": "Schopf",
            "penalty_conversion_pct": 0.75,
            "corner_goals_per_game": 0.08,
            "aerial_threat": 5,
            "defensive_set_piece": 5,
        },
        # Ligue 1
        "Paris Saint-Germain": {
            "corner_threat": 7,
            "free_kick_specialists": ["Mbappe", "Neymar", "Marquinhos"],
            "penalty_taker": "Mbappe",
            "penalty_conversion_pct": 0.90,
            "corner_goals_per_game": 0.14,
            "aerial_threat": 7,
            "defensive_set_piece": 7,
        },
        "Marseille": {
            "corner_threat": 6,
            "free_kick_specialists": ["Sanchez", "Guendouzi", "Sarr"],
            "penalty_taker": "Sanchez",
            "penalty_conversion_pct": 0.81,
            "corner_goals_per_game": 0.11,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "AS Monaco": {
            "corner_threat": 6,
            "free_kick_specialists": ["Akliouche", "Disasi", "Embolo"],
            "penalty_taker": "Embolo",
            "penalty_conversion_pct": 0.79,
            "corner_goals_per_game": 0.10,
            "aerial_threat": 5,
            "defensive_set_piece": 6,
        },
        "Lyon": {
            "corner_threat": 6,
            "free_kick_specialists": ["Tolisso", "Tete", "Mangala"],
            "penalty_taker": "Tolisso",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 6,
            "defensive_set_piece": 6,
        },
        "Nice": {
            "corner_threat": 5,
            "free_kick_specialists": ["Lotomba", "Claude-Makele", "Stengs"],
            "penalty_taker": "Stengs",
            "penalty_conversion_pct": 0.77,
            "corner_goals_per_game": 0.09,
            "aerial_threat": 5,
            "defensive_set_piece": 5,
        },
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        """
        Analyze set piece opportunities and threats

        Returns dict with:
        - agent: agent name
        - predictions: set piece predictions
        - confidence: confidence score
        - insights: set piece insights
        - adjustments: probability adjustments for set piece goals
        """
        home_team = match_data.get("home_team")
        away_team = match_data.get("away_team")

        # Get set piece ratings
        home_sp = self.SET_PIECE_RATINGS.get(home_team, self._get_default_sp())
        away_sp = self.SET_PIECE_RATINGS.get(away_team, self._get_default_sp())

        # Calculate set piece advantage
        home_corner_threat = home_sp["corner_threat"]
        away_corner_threat = away_sp["corner_threat"]
        corner_advantage = (home_corner_threat - away_corner_threat) / 10.0

        # Penalty likelihood from fouls (use cards_avg as proxy for fouls)
        home_fouls_avg = home_form.get("fouls_avg", 10.0) if home_form else 10.0
        away_fouls_avg = away_form.get("fouls_avg", 10.0) if away_form else 10.0

        penalty_probability = ((home_fouls_avg + away_fouls_avg) / 20.0) * 0.15
        penalty_probability = min(0.20, max(0.05, penalty_probability))

        # Corner goal probabilities
        home_corners_avg = home_stats.get("home_corners_avg", 5.0) if home_stats else 5.0
        away_corners_avg = away_stats.get("away_corners_avg", 5.0) if away_stats else 5.0

        corner_goal_prob_home = (home_sp["corner_goals_per_game"] / home_corners_avg) * 100 if home_corners_avg > 0 else 0.015
        corner_goal_prob_away = (away_sp["corner_goals_per_game"] / away_corners_avg) * 100 if away_corners_avg > 0 else 0.015
        corner_goal_prob_home = min(0.025, max(0.008, corner_goal_prob_home))
        corner_goal_prob_away = min(0.025, max(0.008, corner_goal_prob_away))

        # Dead ball threat rating
        dead_ball_threat_rating = (home_sp["corner_threat"] + home_sp["aerial_threat"]) / 2.0

        confidence = 0.55
        if h2h:
            confidence += 0.05

        predictions = {
            "set_piece_advantage": "home" if corner_advantage > 0 else ("away" if corner_advantage < 0 else "neutral"),
            "corner_advantage_score": corner_advantage,
            "corner_goal_prob_home": corner_goal_prob_home,
            "corner_goal_prob_away": corner_goal_prob_away,
            "penalty_probability": penalty_probability,
            "dead_ball_threat_rating": dead_ball_threat_rating,
            "home_sp_rating": home_sp,
            "away_sp_rating": away_sp,
        }

        insights = [
            f"Home corner threat: {home_sp['corner_threat']}/10 | Away: {away_sp['corner_threat']}/10",
            f"Home aerial ability: {home_sp['aerial_threat']}/10 | Away: {away_sp['aerial_threat']}/10",
            f"Penalty specialist: Home {home_sp['penalty_taker']} ({home_sp['penalty_conversion_pct']*100:.0f}%) vs Away {away_sp['penalty_taker']} ({away_sp['penalty_conversion_pct']*100:.0f}%)",
            f"Corner goal frequency: Home {home_sp['corner_goals_per_game']:.2f}/game, Away {away_sp['corner_goals_per_game']:.2f}/game",
            f"Set piece defense: Home {home_sp['defensive_set_piece']}/10 vs Away {away_sp['defensive_set_piece']}/10",
        ]

        adjustments = {
            "corner_goal_adjustment": (corner_goal_prob_home - corner_goal_prob_away) * 0.1,
            "penalty_xg_adjustment": penalty_probability * 0.3,
            "dead_ball_adjustment": (dead_ball_threat_rating / 10.0) * 0.15,
        }

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": confidence,
            "insights": insights,
            "adjustments": adjustments,
        }

    def _get_default_sp(self):
        return {
            "corner_threat": 5,
            "free_kick_specialists": ["Unknown"],
            "penalty_taker": "Unknown",
            "penalty_conversion_pct": 0.80,
            "corner_goals_per_game": 0.12,
            "aerial_threat": 5,
            "defensive_set_piece": 5,
        }


class DefensiveProfileAgent:
    """Analyzes defensive vulnerabilities, clean sheet probability, and defensive patterns"""
    name = "defensive_profile_agent"
    specialty = "defensive_vulnerabilities and clean_sheet_probability"
    weight = 0.60
    reliability_score = 0.60

    DEFENSIVE_PROFILES = {
        # English Premier League
        "Manchester City": {
            "style": "aggressive",
            "weak_period": "late",
            "vulnerability": "none",
            "goals_conceded_1h_pct": 0.35,
            "defensive_errors_per_game": 0.2,
        },
        "Liverpool": {
            "style": "aggressive",
            "weak_period": "consistent",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.40,
            "defensive_errors_per_game": 0.25,
        },
        "Manchester United": {
            "style": "compact",
            "weak_period": "early",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.45,
            "defensive_errors_per_game": 0.35,
        },
        "Chelsea": {
            "style": "mixed",
            "weak_period": "late",
            "vulnerability": "crosses",
            "goals_conceded_1h_pct": 0.42,
            "defensive_errors_per_game": 0.30,
        },
        "Arsenal": {
            "style": "aggressive",
            "weak_period": "early",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.38,
            "defensive_errors_per_game": 0.28,
        },
        "Tottenham": {
            "style": "mixed",
            "weak_period": "late",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.48,
            "defensive_errors_per_game": 0.40,
        },
        "Newcastle United": {
            "style": "compact",
            "weak_period": "consistent",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.44,
            "defensive_errors_per_game": 0.32,
        },
        "Brighton": {
            "style": "zonal",
            "weak_period": "early",
            "vulnerability": "crosses",
            "goals_conceded_1h_pct": 0.46,
            "defensive_errors_per_game": 0.33,
        },
        "Aston Villa": {
            "style": "mixed",
            "weak_period": "late",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.43,
            "defensive_errors_per_game": 0.31,
        },
        "West Ham": {
            "style": "compact",
            "weak_period": "consistent",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.50,
            "defensive_errors_per_game": 0.42,
        },
        # La Liga
        "Real Madrid": {
            "style": "mixed",
            "weak_period": "early",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.45,
            "defensive_errors_per_game": 0.30,
        },
        "Barcelona": {
            "style": "aggressive",
            "weak_period": "consistent",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.40,
            "defensive_errors_per_game": 0.28,
        },
        "Atletico Madrid": {
            "style": "compact",
            "weak_period": "late",
            "vulnerability": "none",
            "goals_conceded_1h_pct": 0.38,
            "defensive_errors_per_game": 0.18,
        },
        "Sevilla": {
            "style": "zonal",
            "weak_period": "early",
            "vulnerability": "crosses",
            "goals_conceded_1h_pct": 0.48,
            "defensive_errors_per_game": 0.35,
        },
        "Villarreal": {
            "style": "compact",
            "weak_period": "consistent",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.42,
            "defensive_errors_per_game": 0.28,
        },
        "Real Betis": {
            "style": "mixed",
            "weak_period": "late",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.46,
            "defensive_errors_per_game": 0.36,
        },
        "Valencia": {
            "style": "compact",
            "weak_period": "early",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.50,
            "defensive_errors_per_game": 0.40,
        },
        # Serie A
        "Inter Milan": {
            "style": "mixed",
            "weak_period": "late",
            "vulnerability": "crosses",
            "goals_conceded_1h_pct": 0.41,
            "defensive_errors_per_game": 0.27,
        },
        "AC Milan": {
            "style": "mixed",
            "weak_period": "early",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.43,
            "defensive_errors_per_game": 0.29,
        },
        "Juventus": {
            "style": "compact",
            "weak_period": "late",
            "vulnerability": "none",
            "goals_conceded_1h_pct": 0.37,
            "defensive_errors_per_game": 0.20,
        },
        "Roma": {
            "style": "mixed",
            "weak_period": "consistent",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.47,
            "defensive_errors_per_game": 0.38,
        },
        "Lazio": {
            "style": "zonal",
            "weak_period": "early",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.49,
            "defensive_errors_per_game": 0.41,
        },
        "Napoli": {
            "style": "aggressive",
            "weak_period": "consistent",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.39,
            "defensive_errors_per_game": 0.26,
        },
        # Bundesliga
        "Bayern Munich": {
            "style": "aggressive",
            "weak_period": "late",
            "vulnerability": "none",
            "goals_conceded_1h_pct": 0.32,
            "defensive_errors_per_game": 0.18,
        },
        "Borussia Dortmund": {
            "style": "aggressive",
            "weak_period": "early",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.44,
            "defensive_errors_per_game": 0.33,
        },
        "Bayer Leverkusen": {
            "style": "aggressive",
            "weak_period": "consistent",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.41,
            "defensive_errors_per_game": 0.30,
        },
        "RB Leipzig": {
            "style": "aggressive",
            "weak_period": "early",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.43,
            "defensive_errors_per_game": 0.32,
        },
        "Schalke 04": {
            "style": "compact",
            "weak_period": "consistent",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.52,
            "defensive_errors_per_game": 0.45,
        },
        # Ligue 1
        "Paris Saint-Germain": {
            "style": "mixed",
            "weak_period": "early",
            "vulnerability": "crosses",
            "goals_conceded_1h_pct": 0.42,
            "defensive_errors_per_game": 0.28,
        },
        "Marseille": {
            "style": "aggressive",
            "weak_period": "late",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.45,
            "defensive_errors_per_game": 0.35,
        },
        "AS Monaco": {
            "style": "compact",
            "weak_period": "early",
            "vulnerability": "set_pieces",
            "goals_conceded_1h_pct": 0.48,
            "defensive_errors_per_game": 0.39,
        },
        "Lyon": {
            "style": "mixed",
            "weak_period": "consistent",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.46,
            "defensive_errors_per_game": 0.36,
        },
        "Nice": {
            "style": "zonal",
            "weak_period": "late",
            "vulnerability": "through_balls",
            "goals_conceded_1h_pct": 0.50,
            "defensive_errors_per_game": 0.42,
        },
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        """
        Analyze defensive capabilities and vulnerabilities

        Returns dict with:
        - agent: agent name
        - predictions: defensive predictions
        - confidence: confidence score
        - insights: defensive insights
        - adjustments: probability adjustments for defensive performance
        """
        home_team = match_data.get("home_team")
        away_team = match_data.get("away_team")

        # Get defensive profiles
        home_def = self.DEFENSIVE_PROFILES.get(home_team, self._get_default_def())
        away_def = self.DEFENSIVE_PROFILES.get(away_team, self._get_default_def())

        # Calculate clean sheet probabilities
        home_clean_sheet_prob = self._calculate_clean_sheet_prob(
            home_def, away_form, away_stats, is_home=True
        )
        away_clean_sheet_prob = self._calculate_clean_sheet_prob(
            away_def, home_form, home_stats, is_home=False
        )

        # Goals conceded timing prediction
        home_timing = self._predict_concede_timing(home_def)
        away_timing = self._predict_concede_timing(away_def)

        # Vulnerability exploit probability
        home_vulnerability = home_def.get("vulnerability", "none")
        away_vulnerability = away_def.get("vulnerability", "none")

        home_exploit_prob = 0.5 if away_vulnerability != "none" else 0.3
        away_exploit_prob = 0.5 if home_vulnerability != "none" else 0.3

        confidence = 0.60
        if home_stats:
            confidence += 0.05
        if away_stats:
            confidence += 0.05

        predictions = {
            "clean_sheet_prob_home": home_clean_sheet_prob,
            "clean_sheet_prob_away": away_clean_sheet_prob,
            "goals_conceded_timing_home": home_timing,
            "goals_conceded_timing_away": away_timing,
            "home_vulnerability": home_vulnerability,
            "away_vulnerability": away_vulnerability,
            "home_vulnerability_exploit_prob": home_exploit_prob,
            "away_vulnerability_exploit_prob": away_exploit_prob,
            "home_def_profile": home_def,
            "away_def_profile": away_def,
        }

        insights = [
            f"Home defensive style: {home_def['style']} | Away: {away_def['style']}",
            f"Home weak period: {home_def['weak_period']} | Away: {away_def['weak_period']}",
            f"Home vulnerability: {home_vulnerability} | Away: {away_vulnerability}",
            f"Clean sheet probability: Home {home_clean_sheet_prob*100:.0f}%, Away {away_clean_sheet_prob*100:.0f}%",
            f"Defensive errors: Home {home_def['defensive_errors_per_game']:.2f}/game, Away {away_def['defensive_errors_per_game']:.2f}/game",
        ]

        adjustments = {
            "clean_sheet_adjustment": (home_clean_sheet_prob - away_clean_sheet_prob) * 0.25,
            "vulnerability_adjustment": (home_exploit_prob - away_exploit_prob) * 0.15,
            "error_adjustment": (away_def['defensive_errors_per_game'] - home_def['defensive_errors_per_game']) * 0.1,
        }

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": confidence,
            "insights": insights,
            "adjustments": adjustments,
        }

    def _get_default_def(self):
        return {
            "style": "mixed",
            "weak_period": "consistent",
            "vulnerability": "pace",
            "goals_conceded_1h_pct": 0.45,
            "defensive_errors_per_game": 0.35,
        }

    def _calculate_clean_sheet_prob(self, def_profile, opponent_form, opponent_stats, is_home):
        """Calculate probability of clean sheet (0-1)"""
        base_prob = 0.35

        # Adjust by defensive errors
        error_adjustment = (0.4 - def_profile["defensive_errors_per_game"]) / 0.2
        error_adjustment = max(-0.2, min(0.2, error_adjustment))

        # Adjust by opponent's goals
        if opponent_form:
            opp_goals_avg = opponent_form.get("goals_scored_avg", 1.2)
            goal_adjustment = (1.2 - opp_goals_avg) / 2.0
            goal_adjustment = max(-0.2, min(0.2, goal_adjustment))
        else:
            goal_adjustment = 0

        # Home advantage
        home_adjustment = 0.1 if is_home else -0.05

        clean_sheet_prob = base_prob + error_adjustment + goal_adjustment + home_adjustment
        return max(0.15, min(0.60, clean_sheet_prob))

    def _predict_concede_timing(self, def_profile):
        """Predict when goals are conceded (timing distribution)"""
        weak_period = def_profile["weak_period"]

        if weak_period == "early":
            return {
                "1-15_min": 0.25,
                "16-30_min": 0.22,
                "31-45_min": 0.18,
                "46-60_min": 0.12,
                "61-75_min": 0.13,
                "76-90_min": 0.10,
            }
        elif weak_period == "late":
            return {
                "1-15_min": 0.10,
                "16-30_min": 0.12,
                "31-45_min": 0.15,
                "46-60_min": 0.18,
                "61-75_min": 0.22,
                "76-90_min": 0.23,
            }
        else:  # consistent
            return {
                "1-15_min": 0.16,
                "16-30_min": 0.16,
                "31-45_min": 0.17,
                "46-60_min": 0.17,
                "61-75_min": 0.17,
                "76-90_min": 0.17,
            }


class AttackingProfileAgent:
    """Analyzes attacking patterns, expected goals, and scoring opportunities"""
    name = "attacking_profile_agent"
    specialty = "attacking_patterns and expected_goals"
    weight = 0.65
    reliability_score = 0.60

    ATTACKING_PROFILES = {
        # English Premier League
        "Manchester City": {
            "primary_threat": "central",
            "xg_per_game": 2.3,
            "chance_creation_rating": 9,
            "finishing_quality": 9,
            "late_goal_tendency": 0.35,
            "first_goal_scorer_diversity": 0.8,
            "counter_attack_speed": 7,
        },
        "Liverpool": {
            "primary_threat": "wide",
            "xg_per_game": 2.1,
            "chance_creation_rating": 9,
            "finishing_quality": 8,
            "late_goal_tendency": 0.40,
            "first_goal_scorer_diversity": 0.75,
            "counter_attack_speed": 8,
        },
        "Manchester United": {
            "primary_threat": "counter",
            "xg_per_game": 1.8,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.38,
            "first_goal_scorer_diversity": 0.6,
            "counter_attack_speed": 8,
        },
        "Chelsea": {
            "primary_threat": "central",
            "xg_per_game": 1.9,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.36,
            "first_goal_scorer_diversity": 0.65,
            "counter_attack_speed": 7,
        },
        "Arsenal": {
            "primary_threat": "wide",
            "xg_per_game": 2.2,
            "chance_creation_rating": 9,
            "finishing_quality": 8,
            "late_goal_tendency": 0.32,
            "first_goal_scorer_diversity": 0.72,
            "counter_attack_speed": 7,
        },
        "Tottenham": {
            "primary_threat": "counter",
            "xg_per_game": 1.7,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.42,
            "first_goal_scorer_diversity": 0.55,
            "counter_attack_speed": 9,
        },
        "Newcastle United": {
            "primary_threat": "set_piece",
            "xg_per_game": 1.6,
            "chance_creation_rating": 6,
            "finishing_quality": 6,
            "late_goal_tendency": 0.40,
            "first_goal_scorer_diversity": 0.50,
            "counter_attack_speed": 8,
        },
        "Brighton": {
            "primary_threat": "central",
            "xg_per_game": 1.5,
            "chance_creation_rating": 7,
            "finishing_quality": 6,
            "late_goal_tendency": 0.33,
            "first_goal_scorer_diversity": 0.68,
            "counter_attack_speed": 6,
        },
        "Aston Villa": {
            "primary_threat": "wide",
            "xg_per_game": 1.8,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.37,
            "first_goal_scorer_diversity": 0.62,
            "counter_attack_speed": 7,
        },
        "West Ham": {
            "primary_threat": "counter",
            "xg_per_game": 1.4,
            "chance_creation_rating": 5,
            "finishing_quality": 6,
            "late_goal_tendency": 0.45,
            "first_goal_scorer_diversity": 0.48,
            "counter_attack_speed": 7,
        },
        # La Liga
        "Real Madrid": {
            "primary_threat": "central",
            "xg_per_game": 2.2,
            "chance_creation_rating": 8,
            "finishing_quality": 9,
            "late_goal_tendency": 0.44,
            "first_goal_scorer_diversity": 0.7,
            "counter_attack_speed": 8,
        },
        "Barcelona": {
            "primary_threat": "central",
            "xg_per_game": 2.1,
            "chance_creation_rating": 9,
            "finishing_quality": 8,
            "late_goal_tendency": 0.30,
            "first_goal_scorer_diversity": 0.76,
            "counter_attack_speed": 6,
        },
        "Atletico Madrid": {
            "primary_threat": "counter",
            "xg_per_game": 1.5,
            "chance_creation_rating": 6,
            "finishing_quality": 8,
            "late_goal_tendency": 0.35,
            "first_goal_scorer_diversity": 0.58,
            "counter_attack_speed": 8,
        },
        "Sevilla": {
            "primary_threat": "wide",
            "xg_per_game": 1.6,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.38,
            "first_goal_scorer_diversity": 0.61,
            "counter_attack_speed": 7,
        },
        "Villarreal": {
            "primary_threat": "central",
            "xg_per_game": 1.4,
            "chance_creation_rating": 6,
            "finishing_quality": 6,
            "late_goal_tendency": 0.36,
            "first_goal_scorer_diversity": 0.59,
            "counter_attack_speed": 6,
        },
        "Real Betis": {
            "primary_threat": "wide",
            "xg_per_game": 1.7,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.39,
            "first_goal_scorer_diversity": 0.67,
            "counter_attack_speed": 7,
        },
        "Valencia": {
            "primary_threat": "counter",
            "xg_per_game": 1.3,
            "chance_creation_rating": 5,
            "finishing_quality": 6,
            "late_goal_tendency": 0.41,
            "first_goal_scorer_diversity": 0.52,
            "counter_attack_speed": 7,
        },
        # Serie A
        "Inter Milan": {
            "primary_threat": "central",
            "xg_per_game": 2.0,
            "chance_creation_rating": 8,
            "finishing_quality": 8,
            "late_goal_tendency": 0.37,
            "first_goal_scorer_diversity": 0.68,
            "counter_attack_speed": 7,
        },
        "AC Milan": {
            "primary_threat": "wide",
            "xg_per_game": 1.9,
            "chance_creation_rating": 7,
            "finishing_quality": 8,
            "late_goal_tendency": 0.35,
            "first_goal_scorer_diversity": 0.64,
            "counter_attack_speed": 7,
        },
        "Juventus": {
            "primary_threat": "central",
            "xg_per_game": 1.7,
            "chance_creation_rating": 7,
            "finishing_quality": 8,
            "late_goal_tendency": 0.33,
            "first_goal_scorer_diversity": 0.60,
            "counter_attack_speed": 6,
        },
        "Roma": {
            "primary_threat": "wide",
            "xg_per_game": 1.6,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.40,
            "first_goal_scorer_diversity": 0.63,
            "counter_attack_speed": 7,
        },
        "Lazio": {
            "primary_threat": "counter",
            "xg_per_game": 1.5,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.42,
            "first_goal_scorer_diversity": 0.57,
            "counter_attack_speed": 8,
        },
        "Napoli": {
            "primary_threat": "central",
            "xg_per_game": 2.2,
            "chance_creation_rating": 8,
            "finishing_quality": 8,
            "late_goal_tendency": 0.31,
            "first_goal_scorer_diversity": 0.71,
            "counter_attack_speed": 8,
        },
        # Bundesliga
        "Bayern Munich": {
            "primary_threat": "central",
            "xg_per_game": 2.5,
            "chance_creation_rating": 9,
            "finishing_quality": 9,
            "late_goal_tendency": 0.38,
            "first_goal_scorer_diversity": 0.77,
            "counter_attack_speed": 7,
        },
        "Borussia Dortmund": {
            "primary_threat": "counter",
            "xg_per_game": 2.0,
            "chance_creation_rating": 8,
            "finishing_quality": 8,
            "late_goal_tendency": 0.40,
            "first_goal_scorer_diversity": 0.69,
            "counter_attack_speed": 9,
        },
        "Bayer Leverkusen": {
            "primary_threat": "wide",
            "xg_per_game": 1.9,
            "chance_creation_rating": 8,
            "finishing_quality": 7,
            "late_goal_tendency": 0.36,
            "first_goal_scorer_diversity": 0.66,
            "counter_attack_speed": 8,
        },
        "RB Leipzig": {
            "primary_threat": "counter",
            "xg_per_game": 1.8,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.39,
            "first_goal_scorer_diversity": 0.61,
            "counter_attack_speed": 9,
        },
        "Schalke 04": {
            "primary_threat": "set_piece",
            "xg_per_game": 1.2,
            "chance_creation_rating": 4,
            "finishing_quality": 5,
            "late_goal_tendency": 0.43,
            "first_goal_scorer_diversity": 0.45,
            "counter_attack_speed": 6,
        },
        # Ligue 1
        "Paris Saint-Germain": {
            "primary_threat": "central",
            "xg_per_game": 2.2,
            "chance_creation_rating": 8,
            "finishing_quality": 9,
            "late_goal_tendency": 0.36,
            "first_goal_scorer_diversity": 0.72,
            "counter_attack_speed": 8,
        },
        "Marseille": {
            "primary_threat": "wide",
            "xg_per_game": 1.7,
            "chance_creation_rating": 7,
            "finishing_quality": 7,
            "late_goal_tendency": 0.39,
            "first_goal_scorer_diversity": 0.60,
            "counter_attack_speed": 8,
        },
        "AS Monaco": {
            "primary_threat": "counter",
            "xg_per_game": 1.5,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.41,
            "first_goal_scorer_diversity": 0.56,
            "counter_attack_speed": 8,
        },
        "Lyon": {
            "primary_threat": "central",
            "xg_per_game": 1.6,
            "chance_creation_rating": 6,
            "finishing_quality": 7,
            "late_goal_tendency": 0.38,
            "first_goal_scorer_diversity": 0.59,
            "counter_attack_speed": 7,
        },
        "Nice": {
            "primary_threat": "wide",
            "xg_per_game": 1.4,
            "chance_creation_rating": 5,
            "finishing_quality": 6,
            "late_goal_tendency": 0.40,
            "first_goal_scorer_diversity": 0.54,
            "counter_attack_speed": 6,
        },
    }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        """
        Analyze attacking capabilities and expected goals

        Returns dict with:
        - agent: agent name
        - predictions: attacking predictions
        - confidence: confidence score
        - insights: attacking insights
        - adjustments: probability adjustments for scoring
        """
        home_team = match_data.get("home_team")
        away_team = match_data.get("away_team")

        # Get attacking profiles
        home_att = self.ATTACKING_PROFILES.get(home_team, self._get_default_att())
        away_att = self.ATTACKING_PROFILES.get(away_team, self._get_default_att())

        # Calculate expected goals with form adjustment
        xg_home = self._calculate_xg(home_att, home_form, is_home=True)
        xg_away = self._calculate_xg(away_att, away_form, is_home=False)

        # First goal probabilities
        total_xg = xg_home + xg_away
        first_goal_prob_home = (xg_home / total_xg) if total_xg > 0 else 0.5
        first_goal_prob_away = 1.0 - first_goal_prob_home

        # Scoring pattern prediction
        home_scoring = self._predict_scoring_pattern(home_att)
        away_scoring = self._predict_scoring_pattern(away_att)

        # BTTS probability
        btts_probability = self._calculate_btts_prob(xg_home, xg_away)

        confidence = 0.60
        if home_form and home_stats:
            confidence += 0.05
        if away_form and away_stats:
            confidence += 0.05

        predictions = {
            "xg_home": xg_home,
            "xg_away": xg_away,
            "first_goal_prob_home": first_goal_prob_home,
            "first_goal_prob_away": first_goal_prob_away,
            "home_scoring_pattern": home_scoring,
            "away_scoring_pattern": away_scoring,
            "btts_probability": btts_probability,
            "home_att_profile": home_att,
            "away_att_profile": away_att,
        }

        insights = [
            f"Expected goals: Home {xg_home:.2f} vs Away {xg_away:.2f}",
            f"Home primary threat: {home_att['primary_threat']} | Away: {away_att['primary_threat']}",
            f"Chance creation: Home {home_att['chance_creation_rating']}/10 vs Away {away_att['chance_creation_rating']}/10",
            f"Finishing quality: Home {home_att['finishing_quality']}/10 vs Away {away_att['finishing_quality']}/10",
            f"Late goal tendency: Home {home_att['late_goal_tendency']:.0%}, Away {away_att['late_goal_tendency']:.0%}",
            f"BTTS probability: {btts_probability*100:.0f}%",
        ]

        adjustments = {
            "xg_adjustment": (xg_home - xg_away) * 0.4,
            "first_goal_adjustment": (first_goal_prob_home - 0.5) * 0.25,
            "btts_adjustment": (btts_probability - 0.5) * 0.2,
        }

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": confidence,
            "insights": insights,
            "adjustments": adjustments,
        }

    def _get_default_att(self):
        return {
            "primary_threat": "central",
            "xg_per_game": 1.6,
            "chance_creation_rating": 6,
            "finishing_quality": 6,
            "late_goal_tendency": 0.37,
            "first_goal_scorer_diversity": 0.60,
            "counter_attack_speed": 7,
        }

    def _calculate_xg(self, att_profile, form_data, is_home):
        """Calculate expected goals with form adjustment"""
        base_xg = att_profile["xg_per_game"]

        # Adjust by recent form
        if form_data:
            goals_avg = form_data.get("goals_scored_avg", 1.2)
            form_adjustment = (goals_avg - 1.2) / 2.0
            form_adjustment = max(-0.3, min(0.3, form_adjustment))
        else:
            form_adjustment = 0

        # Home advantage
        home_adjustment = 0.2 if is_home else 0.0

        xg = base_xg + form_adjustment + home_adjustment
        return max(0.8, min(3.0, xg))

    def _predict_scoring_pattern(self, att_profile):
        """Predict which periods team is likely to score"""
        if att_profile["late_goal_tendency"] > 0.40:
            return {
                "1-15_min": 0.12,
                "16-30_min": 0.13,
                "31-45_min": 0.15,
                "46-60_min": 0.17,
                "61-75_min": 0.18,
                "76-90_min": 0.25,
            }
        elif att_profile["late_goal_tendency"] < 0.33:
            return {
                "1-15_min": 0.18,
                "16-30_min": 0.17,
                "31-45_min": 0.16,
                "46-60_min": 0.16,
                "61-75_min": 0.17,
                "76-90_min": 0.16,
            }
        else:
            return {
                "1-15_min": 0.15,
                "16-30_min": 0.16,
                "31-45_min": 0.16,
                "46-60_min": 0.17,
                "61-75_min": 0.18,
                "76-90_min": 0.18,
            }

    def _calculate_btts_prob(self, xg_home, xg_away):
        """Calculate Both Teams to Score probability"""
        # Poisson approximation for BTTS
        prob_home_scores = 1.0 - self._poisson_0(xg_home)
        prob_away_scores = 1.0 - self._poisson_0(xg_away)
        btts_prob = prob_home_scores * prob_away_scores
        return max(0.15, min(0.75, btts_prob))

    def _poisson_0(self, lam):
        """Calculate Poisson probability of 0 events"""
        import math
        return math.exp(-lam)
