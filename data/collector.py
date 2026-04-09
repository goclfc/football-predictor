"""
Data Collection Layer
Fetches match data, odds, statistics from multiple sources.
Supports: API-Football, The Odds API, and fallback simulation for demo.
"""
import requests
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class OddsCollector:
    """Fetches real-time odds from multiple bookmakers via The Odds API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"

    def get_upcoming_odds(self, sport="soccer_epl", regions="eu", markets="h2h,totals,spreads"):
        """Fetch upcoming match odds from The Odds API."""
        if not self.api_key:
            return self._generate_realistic_odds()

        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "decimal"
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[OddsCollector] API error: {e}, falling back to simulation")
            return self._generate_realistic_odds()

    def _generate_realistic_odds(self) -> List[Dict]:
        """Generate realistic odds data for demonstration/testing."""
        matches = [
            {"home": "Newcastle", "away": "Sunderland", "league": "Premier League"},
            {"home": "Arsenal", "away": "Chelsea", "league": "Premier League"},
            {"home": "Liverpool", "away": "Everton", "league": "Premier League"},
            {"home": "Barcelona", "away": "Real Madrid", "league": "La Liga"},
            {"home": "Bayern Munich", "away": "Dortmund", "league": "Bundesliga"},
            {"home": "Juventus", "away": "AC Milan", "league": "Serie A"},
            {"home": "PSG", "away": "Marseille", "league": "Ligue 1"},
            {"home": "Benfica", "away": "Porto", "league": "Primeira Liga"},
            {"home": "Ajax", "away": "PSV", "league": "Eredivisie"},
            {"home": "Celtic", "away": "Rangers", "league": "Scottish Premiership"},
        ]

        bookmakers = ["Bet365", "Pinnacle", "1xBet", "William Hill", "Unibet"]

        result = []
        base_time = datetime.now() + timedelta(hours=random.randint(2, 48))

        for i, match in enumerate(matches):
            match_time = base_time + timedelta(hours=i * 3)

            # Generate correlated odds across bookmakers
            home_strength = random.uniform(0.3, 0.6)
            draw_base = random.uniform(0.2, 0.3)
            away_strength = 1 - home_strength - draw_base

            match_data = {
                "id": f"match_{i+1}",
                "home_team": match["home"],
                "away_team": match["away"],
                "league": match["league"],
                "commence_time": match_time.isoformat(),
                "bookmakers": [],
                "markets": self._generate_all_markets(match, bookmakers, home_strength)
            }
            result.append(match_data)

        return result

    def _generate_all_markets(self, match: Dict, bookmakers: List[str], home_strength: float) -> Dict:
        """Generate odds for ALL betting markets including niche ones."""
        markets = {}

        # 1X2 (Match Result)
        markets["match_result"] = self._gen_market_odds(bookmakers, {
            f"{match['home']} Win": 1 / (home_strength + random.uniform(-0.05, 0.05)),
            "Draw": 1 / (0.25 + random.uniform(-0.03, 0.03)),
            f"{match['away']} Win": 1 / (1 - home_strength - 0.25 + random.uniform(-0.05, 0.05)),
        })

        # Over/Under Goals
        for line in [1.5, 2.5, 3.5]:
            over_prob = 0.75 if line == 1.5 else (0.55 if line == 2.5 else 0.35)
            over_prob += random.uniform(-0.08, 0.08)
            markets[f"goals_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / over_prob,
                f"Under {line}": 1 / (1 - over_prob),
            })

        # BTTS (Both Teams to Score)
        btts_prob = 0.52 + random.uniform(-0.1, 0.1)
        markets["btts"] = self._gen_market_odds(bookmakers, {
            "Yes": 1 / btts_prob,
            "No": 1 / (1 - btts_prob),
        })

        # Corners Over/Under
        for line in [8.5, 9.5, 10.5, 11.5]:
            base_prob = {8.5: 0.7, 9.5: 0.55, 10.5: 0.4, 11.5: 0.28}[line]
            base_prob += random.uniform(-0.08, 0.08)
            markets[f"corners_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / base_prob,
                f"Under {line}": 1 / (1 - base_prob),
            })

        # Corners: Home vs Away
        home_corner_pct = home_strength + random.uniform(-0.1, 0.1)
        markets["corners_home_away"] = self._gen_market_odds(bookmakers, {
            f"{match['home']} More Corners": 1 / (home_corner_pct),
            f"{match['away']} More Corners": 1 / (1 - home_corner_pct),
        })

        # Cards Over/Under
        for line in [3.5, 4.5, 5.5]:
            base_prob = {3.5: 0.6, 4.5: 0.42, 5.5: 0.25}[line]
            base_prob += random.uniform(-0.06, 0.06)
            markets[f"cards_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / base_prob,
                f"Under {line}": 1 / (1 - base_prob),
            })

        # Throw-ins Over/Under
        for line in [21.5, 23.5, 25.5]:
            base_prob = {21.5: 0.65, 23.5: 0.5, 25.5: 0.35}[line]
            base_prob += random.uniform(-0.08, 0.08)
            markets[f"throwins_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / base_prob,
                f"Under {line}": 1 / (1 - base_prob),
            })

        # Shots on Target Over/Under
        for line in [4.5, 5.5, 6.5]:
            base_prob = {4.5: 0.7, 5.5: 0.55, 6.5: 0.38}[line]
            base_prob += random.uniform(-0.07, 0.07)
            markets[f"shots_on_target_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / base_prob,
                f"Under {line}": 1 / (1 - base_prob),
            })

        # First Half Goals Over/Under
        for line in [0.5, 1.5]:
            base_prob = {0.5: 0.72, 1.5: 0.38}[line]
            base_prob += random.uniform(-0.06, 0.06)
            markets[f"first_half_goals_over_under_{line}"] = self._gen_market_odds(bookmakers, {
                f"Over {line}": 1 / base_prob,
                f"Under {line}": 1 / (1 - base_prob),
            })

        # Double Chance
        markets["double_chance"] = self._gen_market_odds(bookmakers, {
            f"{match['home']} or Draw": 1 / (home_strength + 0.25 + random.uniform(-0.03, 0.03)),
            f"{match['away']} or Draw": 1 / (1 - home_strength + random.uniform(-0.03, 0.03)),
            f"{match['home']} or {match['away']}": 1 / (1 - 0.25 + random.uniform(-0.03, 0.03)),
        })

        return markets

    def _gen_market_odds(self, bookmakers: List[str], base_odds: Dict) -> List[Dict]:
        """Generate odds for each bookmaker with slight variations."""
        result = []
        for bookie in bookmakers:
            bookie_odds = {}
            for outcome, odds in base_odds.items():
                # Each bookmaker has slightly different odds (margin + variation)
                margin = random.uniform(1.02, 1.08)  # bookmaker margin
                variation = random.uniform(0.95, 1.05)
                final_odds = max(1.01, round(odds * margin * variation, 2))
                bookie_odds[outcome] = final_odds
            result.append({"bookmaker": bookie, "odds": bookie_odds})
        return result


class StatsCollector:
    """Fetches team/match statistics for analysis."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def get_team_form(self, team_name: str) -> Dict:
        """Get recent form data for a team (last 10 matches)."""
        # In production: call API-Football /fixtures?team={id}&last=10
        return self._simulate_team_form(team_name)

    def get_head_to_head(self, home: str, away: str) -> Dict:
        """Get H2H history between two teams."""
        return self._simulate_h2h(home, away)

    def get_team_stats(self, team_name: str) -> Dict:
        """Get detailed team statistics for the current season."""
        return self._simulate_team_stats(team_name)

    def _simulate_team_form(self, team: str) -> Dict:
        """Simulate realistic team form data."""
        form_string = "".join(random.choices(["W", "D", "L"], weights=[0.45, 0.25, 0.3], k=10))
        matches = []
        for i in range(10):
            goals_for = random.choices([0,1,2,3,4], weights=[0.15,0.3,0.3,0.15,0.1])[0]
            goals_against = random.choices([0,1,2,3], weights=[0.25,0.35,0.25,0.15])[0]
            matches.append({
                "goals_for": goals_for,
                "goals_against": goals_against,
                "corners": random.randint(3, 9),
                "cards_yellow": random.randint(0, 4),
                "cards_red": random.choices([0, 1], weights=[0.9, 0.1])[0],
                "shots_on_target": random.randint(2, 8),
                "shots_total": random.randint(8, 20),
                "possession": random.randint(35, 65),
                "throw_ins": random.randint(15, 30),
                "fouls": random.randint(8, 18),
                "result": form_string[i],
                "home": random.choice([True, False]),
            })

        wins = form_string.count("W")
        draws = form_string.count("D")
        losses = form_string.count("L")

        return {
            "team": team,
            "form_string": form_string,
            "wins": wins, "draws": draws, "losses": losses,
            "points_last_10": wins * 3 + draws,
            "goals_scored_avg": round(sum(m["goals_for"] for m in matches) / 10, 2),
            "goals_conceded_avg": round(sum(m["goals_against"] for m in matches) / 10, 2),
            "corners_avg": round(sum(m["corners"] for m in matches) / 10, 2),
            "cards_avg": round(sum(m["cards_yellow"] + m["cards_red"] for m in matches) / 10, 2),
            "shots_on_target_avg": round(sum(m["shots_on_target"] for m in matches) / 10, 2),
            "throw_ins_avg": round(sum(m["throw_ins"] for m in matches) / 10, 2),
            "fouls_avg": round(sum(m["fouls"] for m in matches) / 10, 2),
            "matches": matches,
        }

    def _simulate_h2h(self, home: str, away: str) -> Dict:
        """Simulate head-to-head record."""
        total = random.randint(8, 20)
        home_wins = random.randint(2, total - 2)
        away_wins = random.randint(1, total - home_wins)
        draws = total - home_wins - away_wins

        avg_goals = round(random.uniform(2.0, 3.5), 2)
        avg_corners = round(random.uniform(8.0, 12.0), 2)
        avg_cards = round(random.uniform(3.0, 6.0), 2)

        return {
            "home": home, "away": away,
            "total_matches": total,
            "home_wins": home_wins, "away_wins": away_wins, "draws": draws,
            "avg_goals_per_match": avg_goals,
            "avg_corners_per_match": avg_corners,
            "avg_cards_per_match": avg_cards,
            "btts_percentage": round(random.uniform(40, 70), 1),
            "over_2_5_percentage": round(random.uniform(40, 65), 1),
        }

    def _simulate_team_stats(self, team: str) -> Dict:
        """Simulate current season stats."""
        played = random.randint(25, 34)
        return {
            "team": team,
            "season": "2025/26",
            "played": played,
            "home_corners_avg": round(random.uniform(4.5, 7.5), 2),
            "away_corners_avg": round(random.uniform(3.5, 6.5), 2),
            "home_cards_avg": round(random.uniform(1.5, 3.0), 2),
            "away_cards_avg": round(random.uniform(1.8, 3.5), 2),
            "home_goals_avg": round(random.uniform(1.2, 2.5), 2),
            "away_goals_avg": round(random.uniform(0.8, 1.8), 2),
            "home_conceded_avg": round(random.uniform(0.5, 1.5), 2),
            "away_conceded_avg": round(random.uniform(0.8, 2.0), 2),
            "clean_sheets_pct": round(random.uniform(20, 45), 1),
            "btts_pct": round(random.uniform(40, 65), 1),
            "over_2_5_pct": round(random.uniform(40, 65), 1),
            "avg_throw_ins": round(random.uniform(18, 28), 2),
            "avg_fouls": round(random.uniform(10, 16), 2),
            "avg_shots_on_target": round(random.uniform(3.5, 6.5), 2),
        }
