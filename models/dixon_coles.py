"""
Dixon-Coles Model — The gold standard for football match prediction.

Key improvements over basic Poisson:
1. Correlation parameter (rho) for low-scoring outcomes
   - P(0-0), P(1-0), P(0-1), P(1-1) are adjusted because game-state effects
     make these scores more/less likely than independent Poisson predicts
2. Time-decay weighting — recent matches count more than old ones
3. Attack/defense decomposition — each team has separate attack and defense ratings

Reference: Dixon, M.J. & Coles, S.G. (1997) "Modelling Association Football Scores
and Inefficiencies in the Football Betting Market"
"""
import math
from typing import Dict, Tuple, List
from scipy.stats import poisson


def dixon_coles_correction(home_goals: int, away_goals: int,
                            home_exp: float, away_exp: float,
                            rho: float = -0.13) -> float:
    """
    Apply the Dixon-Coles correction factor to bivariate Poisson probability.

    The correction adjusts P(X=x, Y=y) for low-scoring outcomes where
    independence assumption breaks down.

    rho: correlation parameter (typically -0.13 to -0.10 for football)
         Negative rho means low-low scores are more common than independent Poisson.
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - home_exp * away_exp * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + away_exp * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + home_exp * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0


def dixon_coles_match_probs(home_exp: float, away_exp: float,
                             rho: float = -0.13,
                             max_goals: int = 8) -> Dict[str, float]:
    """
    Calculate full match probability matrix using Dixon-Coles model.

    Returns dict with:
    - 'home_win', 'draw', 'away_win' probabilities
    - 'score_probs': dict of (i,j) -> probability for exact scores
    - 'total_goals_probs': probability of 0, 1, 2, ... total goals
    """
    score_probs = {}
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            # Base independent Poisson probability
            base_prob = poisson.pmf(i, home_exp) * poisson.pmf(j, away_exp)

            # Apply Dixon-Coles correction for low scores
            correction = dixon_coles_correction(i, j, home_exp, away_exp, rho)

            prob = base_prob * correction
            prob = max(prob, 0)  # Ensure non-negative
            score_probs[(i, j)] = prob

            if i > j:
                home_win += prob
            elif i == j:
                draw += prob
            else:
                away_win += prob

    # Normalize (corrections can slightly shift total)
    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total

    # Total goals distribution
    total_goals_probs = {}
    for g in range(max_goals * 2 + 1):
        p = sum(score_probs.get((i, g - i), 0) for i in range(g + 1) if g - i >= 0)
        total_goals_probs[g] = p

    # Normalize total goals probs
    tg_total = sum(total_goals_probs.values())
    if tg_total > 0:
        total_goals_probs = {k: v / tg_total for k, v in total_goals_probs.items()}

    return {
        'home_win': home_win,
        'draw': draw,
        'away_win': away_win,
        'score_probs': score_probs,
        'total_goals_probs': total_goals_probs,
        'home_exp': home_exp,
        'away_exp': away_exp,
    }


def prob_over_goals(match_probs: Dict, line: float) -> float:
    """Probability of over X goals from Dixon-Coles output."""
    total_probs = match_probs['total_goals_probs']
    under_prob = sum(p for g, p in total_probs.items() if g <= int(line))
    return max(0, min(1, 1 - under_prob))


def prob_btts(match_probs: Dict) -> float:
    """Probability that both teams score."""
    score_probs = match_probs['score_probs']
    btts_prob = 0
    for (i, j), p in score_probs.items():
        if i > 0 and j > 0:
            btts_prob += p
    return max(0, min(1, btts_prob))


def prob_clean_sheet(match_probs: Dict, team: str = 'home') -> float:
    """Probability of clean sheet for home or away team."""
    score_probs = match_probs['score_probs']
    cs_prob = 0
    for (i, j), p in score_probs.items():
        if team == 'home' and j == 0:
            cs_prob += p
        elif team == 'away' and i == 0:
            cs_prob += p
    return max(0, min(1, cs_prob))


def prob_exact_score(match_probs: Dict, home_goals: int, away_goals: int) -> float:
    """Probability of an exact score."""
    return match_probs['score_probs'].get((home_goals, away_goals), 0)


def prob_first_half_goals_over(home_exp: float, away_exp: float, line: float,
                                rho: float = -0.13) -> float:
    """
    First half goal probability.
    Research shows ~42% of goals occur in first half, but with higher variance.
    """
    fh_home = home_exp * 0.42
    fh_away = away_exp * 0.42
    fh_probs = dixon_coles_match_probs(fh_home, fh_away, rho * 0.7)
    return prob_over_goals(fh_probs, line)


def prob_double_chance(match_probs: Dict) -> Dict[str, float]:
    """Double chance probabilities."""
    return {
        '1X': match_probs['home_win'] + match_probs['draw'],
        'X2': match_probs['draw'] + match_probs['away_win'],
        '12': match_probs['home_win'] + match_probs['away_win'],
    }


# ─── Elo Rating System ───────────────────────────────────────────────
class EloRating:
    """
    Elo rating system for football teams.

    Key properties:
    - Average rating is 1500
    - Home advantage is worth ~65 Elo points
    - K-factor of 20 for gradual updates (32 for cups)
    - Goal difference scaling (winning 3-0 matters more than 1-0)
    """

    def __init__(self, k_factor: float = 20, home_advantage: float = 65):
        self.k = k_factor
        self.home_advantage = home_advantage
        self.ratings: Dict[str, float] = {}

    def get_rating(self, team: str) -> float:
        """Get team's current Elo rating (default 1500 for new teams)."""
        return self.ratings.get(team, 1500.0)

    def expected_score(self, team_a: str, team_b: str, team_a_home: bool = True) -> float:
        """
        Expected score (probability of team A winning) based on Elo.
        Includes home advantage adjustment.
        """
        ra = self.get_rating(team_a)
        rb = self.get_rating(team_b)

        if team_a_home:
            ra += self.home_advantage

        return 1 / (1 + 10 ** ((rb - ra) / 400))

    def update(self, home_team: str, away_team: str,
               home_goals: int, away_goals: int):
        """Update ratings after a match result."""
        # Actual result (1 = win, 0.5 = draw, 0 = loss for home)
        if home_goals > away_goals:
            actual_home = 1.0
        elif home_goals == away_goals:
            actual_home = 0.5
        else:
            actual_home = 0.0

        expected_home = self.expected_score(home_team, away_team, team_a_home=True)

        # Goal difference multiplier (bigger wins = bigger updates)
        gd = abs(home_goals - away_goals)
        if gd <= 1:
            gd_mult = 1.0
        elif gd == 2:
            gd_mult = 1.5
        else:
            gd_mult = (11 + gd) / 8  # Formula from World Football Elo

        # Update both teams
        delta = self.k * gd_mult * (actual_home - expected_home)
        self.ratings[home_team] = self.get_rating(home_team) + delta
        self.ratings[away_team] = self.get_rating(away_team) - delta

    def predict_match(self, home_team: str, away_team: str) -> Dict[str, float]:
        """
        Predict match outcome using Elo ratings.
        Returns home_win, draw, away_win probabilities.
        """
        exp_home = self.expected_score(home_team, away_team, team_a_home=True)

        # Convert expected score to 1X2 probabilities
        # Using empirical mapping from Elo expectation to actual outcomes
        # Draw probability peaks when teams are equal, ~25-28%
        draw_prob = 0.28 - 0.08 * abs(exp_home - 0.5)
        draw_prob = max(0.15, min(0.33, draw_prob))

        home_win = max(0.05, exp_home - draw_prob * 0.4)
        away_win = max(0.05, 1 - exp_home - draw_prob * 0.6)

        # Normalize
        total = home_win + draw_prob + away_win
        return {
            'home_win': home_win / total,
            'draw': draw_prob / total,
            'away_win': away_win / total,
        }

    def team_strength_ratio(self, team_a: str, team_b: str) -> float:
        """
        Ratio of team strengths (useful for adjusting expected goals).
        Returns multiplier for team_a relative to average.
        1.0 = equal, >1 = team_a stronger, <1 = team_a weaker.
        """
        ra = self.get_rating(team_a)
        rb = self.get_rating(team_b)
        avg = (ra + rb) / 2
        if avg == 0:
            return 1.0
        return ra / avg

    def initialize_from_standings(self, standings: Dict[str, int]):
        """
        Initialize Elo from league standings (points).
        Maps points to Elo range 1350-1650.
        """
        if not standings:
            return

        max_pts = max(standings.values())
        min_pts = min(standings.values())
        pts_range = max(max_pts - min_pts, 1)

        for team, pts in standings.items():
            # Map points to Elo 1350-1650 range
            normalized = (pts - min_pts) / pts_range
            self.ratings[team] = 1350 + normalized * 300

    def initialize_top5_defaults(self):
        """
        Initialize with reasonable defaults for top 5 league teams.
        Based on historical Elo ratings.
        """
        defaults = {
            # Premier League
            "Manchester City": 1680, "Arsenal": 1650, "Liverpool": 1660,
            "Chelsea": 1580, "Manchester United": 1560, "Tottenham": 1570,
            "Newcastle": 1570, "Aston Villa": 1550, "Brighton": 1540,
            "West Ham": 1520, "Crystal Palace": 1500, "Bournemouth": 1500,
            "Fulham": 1510, "Wolves": 1490, "Everton": 1480,
            "Brentford": 1510, "Nottingham Forest": 1490, "Ipswich": 1430,
            "Leicester": 1450, "Southampton": 1420,
            # La Liga
            "Real Madrid": 1690, "Barcelona": 1680, "Atletico Madrid": 1610,
            "Real Sociedad": 1560, "Athletic Club": 1560, "Villarreal": 1550,
            "Betis": 1530, "Girona": 1530, "Sevilla": 1520,
            "Mallorca": 1490, "Rayo Vallecano": 1490, "Osasuna": 1490,
            "Celta Vigo": 1480, "Valencia": 1470, "Getafe": 1480,
            "Alaves": 1440, "Espanyol": 1450, "Valladolid": 1430,
            "Las Palmas": 1440, "Leganes": 1420,
            # Bundesliga
            "Bayern Munich": 1680, "Bayer Leverkusen": 1650,
            "Borussia Dortmund": 1610, "RB Leipzig": 1590,
            "Stuttgart": 1560, "SC Freiburg": 1530,
            "Eintracht Frankfurt": 1550, "Wolfsburg": 1510,
            "Union Berlin": 1490, "Hoffenheim": 1500,
            "Werder Bremen": 1500, "Mainz 05": 1490,
            "Augsburg": 1470, "Borussia Monchengladbach": 1490,
            "FC Heidenheim": 1450, "VfL Bochum": 1420,
            "Holstein Kiel": 1410, "St. Pauli": 1430,
            # Serie A
            "Inter Milan": 1650, "Napoli": 1620, "AC Milan": 1590,
            "Juventus": 1600, "Atalanta": 1610, "Roma": 1560,
            "Lazio": 1560, "Fiorentina": 1540, "Bologna": 1530,
            "Torino": 1510, "Monza": 1470, "Udinese": 1490,
            "Genoa": 1480, "Cagliari": 1470, "Lecce": 1460,
            "Empoli": 1460, "Verona": 1450, "Parma": 1440,
            "Como": 1430, "Venezia": 1420,
            # Ligue 1
            "Paris Saint-Germain": 1670, "Monaco": 1580, "Marseille": 1570,
            "Lille": 1560, "Lyon": 1540, "Nice": 1530,
            "Lens": 1530, "Rennes": 1520, "Strasbourg": 1490,
            "Toulouse": 1500, "Montpellier": 1460, "Nantes": 1480,
            "Reims": 1480, "Le Havre": 1450, "Auxerre": 1440,
            "Angers": 1430, "Saint-Etienne": 1440,
        }

        for team, elo in defaults.items():
            if team not in self.ratings:
                self.ratings[team] = elo


# ─── Referee Card Model ──────────────────────────────────────────────
# Average cards per match by referee tendency category
REFEREE_PROFILES = {
    # Strict referees: avg 5-6 yellows per match
    "strict": {"avg_yellows": 5.5, "avg_reds": 0.15, "foul_threshold": "low"},
    # Average referees: 3.5-4.5 yellows
    "average": {"avg_yellows": 4.0, "avg_reds": 0.08, "foul_threshold": "medium"},
    # Lenient referees: 2-3 yellows
    "lenient": {"avg_yellows": 2.5, "avg_reds": 0.04, "foul_threshold": "high"},
}

# Known referee tendencies (major European league refs)
KNOWN_REFEREES = {
    # Premier League
    "Anthony Taylor": "strict", "Michael Oliver": "average",
    "Craig Pawson": "strict", "Simon Hooper": "average",
    "Robert Jones": "average", "Chris Kavanagh": "strict",
    "Andy Madley": "average", "David Coote": "strict",
    "John Brooks": "average", "Paul Tierney": "strict",
    "Peter Bankes": "average", "Darren England": "average",
    "Stuart Attwell": "average", "Thomas Bramall": "lenient",
    "Sam Barrott": "lenient", "Tim Robinson": "average",
    # La Liga
    "Mateu Lahoz": "strict", "Gil Manzano": "strict",
    "Del Cerro Grande": "strict", "Hernandez Hernandez": "strict",
    "Martinez Munuera": "average", "Cuadra Fernandez": "average",
    # Bundesliga
    "Felix Zwayer": "strict", "Daniel Siebert": "average",
    "Deniz Aytekin": "average", "Sascha Stegemann": "average",
    # Serie A
    "Daniele Orsato": "average", "Marco Guida": "strict",
    "Gianluca Manganiello": "strict", "Michael Fabbri": "average",
    # Ligue 1
    "Clement Turpin": "strict", "Francois Letexier": "average",
    "Benoit Bastien": "strict", "Stephanie Frappart": "average",
    "Eric Wattellier": "average",
}


def referee_adjusted_cards(base_cards_expected: float,
                            referee_name: str = None,
                            is_derby: bool = False,
                            is_rivalry: bool = False) -> float:
    """
    Adjust expected cards based on referee tendency + match context.

    This is one of the biggest edges in cards markets because:
    - Bookmakers often use team averages without proper referee adjustment
    - Referee variance is HUGE (2.5 to 5.5 avg yellows per match)
    """
    # Get referee profile
    profile_name = "average"
    if referee_name:
        profile_name = KNOWN_REFEREES.get(referee_name, "average")
    profile = REFEREE_PROFILES[profile_name]

    # Referee-adjusted expectation
    # Blend team-based expectation with referee tendency
    referee_avg_total = profile["avg_yellows"]
    adjusted = base_cards_expected * 0.5 + referee_avg_total * 0.5

    # Context adjustments
    if is_derby:
        adjusted *= 1.25  # Derbies have ~25% more cards
    elif is_rivalry:
        adjusted *= 1.15  # Rivalries ~15% more

    return adjusted


# ─── Corners-Specific Model ──────────────────────────────────────────
def corners_model(home_possession: float, away_possession: float,
                   home_shots_avg: float, away_shots_avg: float,
                   home_corners_avg: float, away_corners_avg: float,
                   home_attack_strength: float = 1.0,
                   away_attack_strength: float = 1.0) -> float:
    """
    Corners-specific prediction model.

    Key insight: Corners correlate with ATTACKING INTENT, not goals.
    A team with high possession + high shots + blocked shots = more corners.
    """
    # Base from historical averages (team-specific)
    base_total = home_corners_avg + away_corners_avg

    # Possession-based adjustment
    # Teams with 55-65% possession tend to win more corners
    # But extreme possession (70%+) can mean less corners (slow buildup)
    home_poss = home_possession / 100 if home_possession > 1 else home_possession
    away_poss = away_possession / 100 if away_possession > 1 else away_possession

    # Attacking intensity: shots attempted correlate with corners
    total_shots = home_shots_avg + away_shots_avg
    shot_factor = total_shots / 24.0  # 24 shots is roughly league average total
    shot_factor = max(0.7, min(1.3, shot_factor))  # Cap adjustment

    # Attack strength adjustment (stronger attackers create more corners)
    attack_factor = (home_attack_strength + away_attack_strength) / 2
    attack_factor = max(0.8, min(1.2, attack_factor))

    adjusted = base_total * shot_factor * attack_factor

    return max(5.0, min(16.0, adjusted))  # Clamp to reasonable range


# ─── Strength-Adjusted Expected Goals ────────────────────────────────
def strength_adjusted_xg(home_attack: float, home_defense: float,
                          away_attack: float, away_defense: float,
                          elo_system: EloRating = None,
                          home_team: str = None, away_team: str = None,
                          league_avg_goals: float = 2.65) -> Tuple[float, float]:
    """
    Calculate expected goals with opponent strength adjustment.

    Instead of just (attack + defense) / 2, we adjust for
    the quality of opposition each team has faced.
    """
    # Base expected goals
    home_exp = (home_attack + away_defense) / 2
    away_exp = (away_attack + home_defense) / 2

    # Elo-based strength adjustment
    if elo_system and home_team and away_team:
        home_elo = elo_system.get_rating(home_team)
        away_elo = elo_system.get_rating(away_team)

        # Elo difference → goal adjustment
        # Every 100 Elo points ≈ 0.15 goal advantage
        elo_diff = home_elo - away_elo
        elo_adj = elo_diff / 100 * 0.15

        # Apply symmetrically
        home_exp += elo_adj / 2
        away_exp -= elo_adj / 2

    # Home advantage (typically ~0.25 goals in major leagues)
    home_exp += 0.12  # Half of home advantage (other half in Elo already)

    # Clamp to reasonable range
    home_exp = max(0.3, min(3.5, home_exp))
    away_exp = max(0.2, min(3.0, away_exp))

    return home_exp, away_exp


# ─── Time-Decay Weighting ────────────────────────────────────────────
def time_decay_weight(days_ago: int, half_life: float = 30) -> float:
    """
    Exponential time decay — recent matches matter more.
    half_life=30 means a match 30 days ago counts half as much as today's.
    """
    return math.exp(-0.693 * days_ago / half_life)


def weighted_average(values: List[float], days_ago: List[int],
                      half_life: float = 30) -> float:
    """Calculate time-weighted average of a stat."""
    if not values:
        return 0.0

    weights = [time_decay_weight(d, half_life) for d in days_ago]
    total_weight = sum(weights)

    if total_weight == 0:
        return sum(values) / len(values)

    return sum(v * w for v, w in zip(values, weights)) / total_weight
