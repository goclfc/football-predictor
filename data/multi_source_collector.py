"""
Multi-Source Data Collector — Fetches data from EVERY available free source
to build the richest possible picture of each match.

Sources:
1. Understat       → xG, xGA, PPDA (pressing), deep completions, xPTS per match
2. ESPN            → Standings, discipline (cards per player), match stats
3. The Odds API    → Real-time bookmaker odds (existing)
4. API-Football    → Team form, H2H, season stats (existing)
5. Football-Data   → Historical results + closing odds (CSV downloads)
6. OpenWeatherMap  → Match-day weather (wind, rain, temperature)

Each source has its own collector class. The orchestrator combines them all.
"""
import requests
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# ─── 1. UNDERSTAT: xG Data ───────────────────────────────────────────
class UnderstatCollector:
    """
    Fetches Expected Goals (xG) data from Understat via understatapi.
    This is the HIGHEST VALUE data source we have — xG is far more
    predictive of future performance than actual goals.
    """

    LEAGUE_MAP = {
        "Premier League": "EPL",
        "La Liga": "La_Liga",
        "Bundesliga": "Bundesliga",
        "Serie A": "Serie_A",
        "Ligue 1": "Ligue_1",
    }

    def __init__(self):
        try:
            from understatapi import UnderstatClient
            self.client = UnderstatClient()
            self.available = True
        except ImportError:
            self.available = False
            print("  ⚠ understatapi not installed — xG data unavailable")

        self._cache = {}

    def get_team_xg(self, team_name: str, league: str, season: int = 2025) -> Dict:
        """
        Get comprehensive xG profile for a team.
        Returns season totals AND per-match breakdowns.
        """
        if not self.available:
            return self._empty_xg(team_name)

        cache_key = f"{league}_{season}"
        if cache_key not in self._cache:
            self._fetch_league_data(league, season)

        league_data = self._cache.get(cache_key, {})

        # Find team by name (fuzzy match)
        for tid, team_data in league_data.items():
            title = team_data.get("title", "")
            if self._fuzzy_match(team_name, title):
                return self._process_team_xg(team_data)

        return self._empty_xg(team_name)

    def get_match_xg(self, home_team: str, away_team: str, league: str,
                      season: int = 2025) -> Dict:
        """Get xG data for a specific matchup from historical meetings."""
        home_xg = self.get_team_xg(home_team, league, season)
        away_xg = self.get_team_xg(away_team, league, season)
        return {"home_xg": home_xg, "away_xg": away_xg}

    def _fetch_league_data(self, league: str, season: int):
        """Fetch all team data for a league from Understat."""
        understat_league = self.LEAGUE_MAP.get(league)
        if not understat_league:
            return

        cache_key = f"{league}_{season}"
        try:
            data = self.client.league(league=understat_league).get_team_data(season=str(season))
            self._cache[cache_key] = data
            print(f"    Understat: loaded {len(data)} teams for {league}")
        except Exception as e:
            print(f"    Understat error for {league}: {e}")
            self._cache[cache_key] = {}

    def _process_team_xg(self, team_data: Dict) -> Dict:
        """Process raw Understat team data into our format."""
        history = team_data.get("history", [])
        if not history:
            return self._empty_xg(team_data.get("title", "Unknown"))

        n = len(history)

        # Season totals
        total_xg = sum(m["xG"] for m in history)
        total_xga = sum(m["xGA"] for m in history)
        total_npxg = sum(m["npxG"] for m in history)
        total_npxga = sum(m["npxGA"] for m in history)
        total_scored = sum(m["scored"] for m in history)
        total_conceded = sum(m["missed"] for m in history)
        total_xpts = sum(m["xpts"] for m in history)
        total_deep = sum(m["deep"] for m in history)
        total_deep_allowed = sum(m["deep_allowed"] for m in history)

        # PPDA (Passes Per Defensive Action) — measures pressing intensity
        # Lower PPDA = more intense pressing
        ppda_att = sum(m["ppda"]["att"] for m in history)
        ppda_def = sum(m["ppda"]["def"] for m in history)
        avg_ppda = ppda_att / ppda_def if ppda_def > 0 else 10.0

        # Home/Away splits
        home_matches = [m for m in history if m["h_a"] == "h"]
        away_matches = [m for m in history if m["h_a"] == "a"]

        home_xg_avg = sum(m["xG"] for m in home_matches) / len(home_matches) if home_matches else 0
        away_xg_avg = sum(m["xG"] for m in away_matches) / len(away_matches) if away_matches else 0
        home_xga_avg = sum(m["xGA"] for m in home_matches) / len(home_matches) if home_matches else 0
        away_xga_avg = sum(m["xGA"] for m in away_matches) / len(away_matches) if away_matches else 0

        # Recent form (last 5 xG)
        last5 = history[-5:]
        recent_xg = sum(m["xG"] for m in last5) / len(last5)
        recent_xga = sum(m["xGA"] for m in last5) / len(last5)

        # xG overperformance (positive = clinical finishing, negative = wasteful)
        xg_overperformance = (total_scored - total_xg) / n

        return {
            "team": team_data.get("title", "Unknown"),
            "matches": n,
            # Season per-match averages
            "xg_per_match": round(total_xg / n, 3),
            "xga_per_match": round(total_xga / n, 3),
            "npxg_per_match": round(total_npxg / n, 3),
            "npxga_per_match": round(total_npxga / n, 3),
            "goals_per_match": round(total_scored / n, 2),
            "conceded_per_match": round(total_conceded / n, 2),
            "xpts_per_match": round(total_xpts / n, 2),
            # Home/Away splits
            "home_xg_avg": round(home_xg_avg, 3),
            "away_xg_avg": round(away_xg_avg, 3),
            "home_xga_avg": round(home_xga_avg, 3),
            "away_xga_avg": round(away_xga_avg, 3),
            # Recent form (last 5)
            "recent_xg_avg": round(recent_xg, 3),
            "recent_xga_avg": round(recent_xga, 3),
            # Advanced metrics
            "ppda": round(avg_ppda, 2),  # Pressing intensity
            "deep_completions_avg": round(total_deep / n, 2),
            "deep_allowed_avg": round(total_deep_allowed / n, 2),
            # xG performance gap
            "xg_overperformance": round(xg_overperformance, 3),
            "xga_overperformance": round((total_conceded - total_xga) / n, 3),
            # Per-match history (for trend analysis)
            "match_history": [{
                "date": m["date"][:10],
                "h_a": m["h_a"],
                "xg": round(m["xG"], 3),
                "xga": round(m["xGA"], 3),
                "scored": m["scored"],
                "conceded": m["missed"],
                "result": m["result"],
            } for m in history[-10:]],  # Last 10 matches
            "data_source": "understat",
        }

    def _fuzzy_match(self, query: str, title: str) -> bool:
        """Fuzzy match team names (handles 'PSG' vs 'Paris Saint Germain' etc.)"""
        query_lower = query.lower().strip()
        title_lower = title.lower().strip()

        if query_lower == title_lower:
            return True

        # Common abbreviations
        aliases = {
            "psg": "paris saint germain",
            "paris saint-germain": "paris saint germain",
            "man city": "manchester city",
            "man united": "manchester united",
            "man utd": "manchester united",
            "spurs": "tottenham",
            "wolves": "wolverhampton wanderers",
            "atletico": "atletico madrid",
            "real sociedad": "real sociedad",
            "inter": "inter milan",
            "ac milan": "ac milan",
            "bayern": "bayern munich",
            "dortmund": "borussia dortmund",
            "bvb": "borussia dortmund",
            "gladbach": "borussia monchengladbach",
            "leverkusen": "bayer leverkusen",
            "rb leipzig": "rasenballsport leipzig",
            "sc freiburg": "freiburg",
        }

        # Direct substring match
        if query_lower in title_lower or title_lower in query_lower:
            return True

        # Alias match
        resolved = aliases.get(query_lower, query_lower)
        if resolved in title_lower or title_lower in resolved:
            return True

        # Word overlap
        q_words = set(query_lower.split())
        t_words = set(title_lower.split())
        overlap = q_words & t_words
        if len(overlap) >= 1 and len(overlap) / max(len(q_words), 1) >= 0.5:
            return True

        return False

    def _empty_xg(self, team: str) -> Dict:
        return {
            "team": team, "matches": 0,
            "xg_per_match": 0, "xga_per_match": 0,
            "npxg_per_match": 0, "npxga_per_match": 0,
            "goals_per_match": 0, "conceded_per_match": 0,
            "xpts_per_match": 0,
            "home_xg_avg": 0, "away_xg_avg": 0,
            "home_xga_avg": 0, "away_xga_avg": 0,
            "recent_xg_avg": 0, "recent_xga_avg": 0,
            "ppda": 10.0, "deep_completions_avg": 0, "deep_allowed_avg": 0,
            "xg_overperformance": 0, "xga_overperformance": 0,
            "match_history": [], "data_source": "none",
        }


# ─── 2. ESPN: Standings + Discipline ─────────────────────────────────
class ESPNCollector:
    """
    Fetches from ESPN:
    - League standings (position, points, form)
    - Player discipline stats (cards per player)
    - Live match stats
    """

    LEAGUE_IDS = {
        "Premier League": ("eng.1", "39"),
        "La Liga": ("esp.1", "140"),
        "Bundesliga": ("ger.1", "78"),
        "Serie A": ("ita.1", "135"),
        "Ligue 1": ("fra.1", "61"),
    }

    ESPN_TEAM_IDS = {
        # Ligue 1
        "Paris Saint-Germain": 160, "PSG": 160,
        "Toulouse": 171, "Monaco": 174, "Marseille": 176,
        "Lyon": 167, "Lille": 166, "Lens": 2007,
        "Nice": 169, "Rennes": 177, "Strasbourg": 162,
        # EPL
        "Arsenal": 359, "Manchester City": 382, "Liverpool": 364,
        "Chelsea": 363, "Manchester United": 360, "Tottenham": 367,
        # Add more as needed...
    }

    def __init__(self):
        self._standings_cache = {}
        self._discipline_cache = {}

    def get_standings(self, league: str) -> List[Dict]:
        """Get league standings with position, points, form."""
        if league in self._standings_cache:
            return self._standings_cache[league]

        league_info = self.LEAGUE_IDS.get(league)
        if not league_info:
            return []

        espn_id = league_info[0]
        url = f"https://site.api.espn.com/apis/v2/sports/soccer/{espn_id}/standings"

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            standings = []
            for group in data.get("children", []):
                for entry in group.get("standings", {}).get("entries", []):
                    team = entry.get("team", {})
                    stats = {s["name"]: s["value"] for s in entry.get("stats", []) if "value" in s}
                    standings.append({
                        "team": team.get("displayName", ""),
                        "position": int(stats.get("rank", 0)),
                        "played": int(stats.get("gamesPlayed", 0)),
                        "wins": int(stats.get("wins", 0)),
                        "draws": int(stats.get("ties", 0)),
                        "losses": int(stats.get("losses", 0)),
                        "goals_for": int(stats.get("pointsFor", 0)),
                        "goals_against": int(stats.get("pointsAgainst", 0)),
                        "points": int(stats.get("points", 0)),
                        "goal_diff": int(stats.get("pointDifferential", 0)),
                    })

            self._standings_cache[league] = standings
            print(f"    ESPN: loaded standings for {league} ({len(standings)} teams)")
            return standings

        except Exception as e:
            print(f"    ESPN standings error: {e}")
            return []

    def get_team_position(self, team_name: str, league: str) -> Dict:
        """Get a team's league position and context (title race, relegation, etc.)"""
        standings = self.get_standings(league)
        total_teams = len(standings)

        for entry in standings:
            if self._name_match(team_name, entry["team"]):
                pos = entry["position"]
                # Motivation context
                if pos <= 4:
                    context = "title_race"
                elif pos <= 7:
                    context = "european_contention"
                elif pos >= total_teams - 2:
                    context = "relegation_battle"
                elif pos >= total_teams - 5:
                    context = "relegation_risk"
                else:
                    context = "mid_table"

                return {
                    **entry,
                    "context": context,
                    "total_teams": total_teams,
                }

        return {"team": team_name, "position": 0, "context": "unknown", "total_teams": 0}

    def get_discipline_stats(self, team_name: str, league: str) -> Dict:
        """Get team's card discipline data."""
        team_id = self.ESPN_TEAM_IDS.get(team_name)
        if not team_id:
            return {"team": team_name, "total_yellows": 0, "total_reds": 0,
                    "cards_per_match": 2.0, "data_source": "none"}

        league_info = self.LEAGUE_IDS.get(league)
        if not league_info:
            return {"team": team_name, "total_yellows": 0, "total_reds": 0,
                    "cards_per_match": 2.0, "data_source": "none"}

        espn_league = league_info[0]

        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league}/teams/{team_id}/statistics"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # Parse card stats from response
                stats = data.get("results", {}).get("stats", [])
                yellows = 0
                reds = 0
                for stat in stats:
                    if stat.get("name") == "yellowCards":
                        yellows = int(stat.get("value", 0))
                    elif stat.get("name") == "redCards":
                        reds = int(stat.get("value", 0))

                # Fallback: estimate from standings data
                position_data = self.get_team_position(team_name, league)
                played = position_data.get("played", 26)
                cards_pm = (yellows + reds * 2) / max(played, 1) if yellows > 0 else 2.0

                return {
                    "team": team_name,
                    "total_yellows": yellows,
                    "total_reds": reds,
                    "played": played,
                    "cards_per_match": round(cards_pm, 2),
                    "data_source": "espn",
                }
        except:
            pass

        return {"team": team_name, "total_yellows": 0, "total_reds": 0,
                "cards_per_match": 2.0, "data_source": "none"}

    # Common abbreviation aliases
    ALIASES = {
        "psg": "paris saint", "man utd": "manchester united",
        "man city": "manchester city", "spurs": "tottenham",
        "inter": "inter milan", "atletico": "atletico madrid",
        "real": "real madrid", "barca": "barcelona",
        "bayern": "bayern munich", "dortmund": "borussia dortmund",
        "gladbach": "borussia monchengladbach", "wolves": "wolverhampton",
        "saint-etienne": "saint-etienne",
    }

    def _name_match(self, query: str, name: str) -> bool:
        q = query.lower().replace("fc", "").replace(".", "").strip()
        n = name.lower().replace("fc", "").replace(".", "").strip()
        # Direct match
        if q in n or n in q:
            return True
        # Alias match
        alias = self.ALIASES.get(q, q)
        if alias != q and (alias in n or n in alias):
            return True
        # Word match (3+ char words)
        return any(w in n for w in q.split() if len(w) > 3)


# ─── 3. FOOTBALL-DATA.CO.UK: Historical Results + Odds ───────────────
class FootballDataCollector:
    """
    Downloads CSV files from football-data.co.uk
    Contains historical match results WITH closing odds from multiple bookmakers.
    This is THE source for backtesting with real odds.
    """

    BASE_URL = "https://www.football-data.co.uk"

    LEAGUE_CODES = {
        "Premier League": "E0",
        "La Liga": "SP1",
        "Bundesliga": "D1",
        "Serie A": "I1",
        "Ligue 1": "F1",
    }

    def __init__(self, cache_dir: str = "/tmp/football_data"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def download_season(self, league: str, season: str = "2526") -> Optional[str]:
        """
        Download season CSV data.
        Season format: "2526" for 2025/26.
        Returns path to CSV file.
        """
        league_code = self.LEAGUE_CODES.get(league)
        if not league_code:
            return None

        filename = f"{league_code}_{season}.csv"
        filepath = os.path.join(self.cache_dir, filename)

        if os.path.exists(filepath):
            return filepath

        url = f"{self.BASE_URL}/mmz4281/{season}/{league_code}.csv"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                with open(filepath, "w") as f:
                    f.write(resp.text)
                print(f"    Football-Data: downloaded {league} {season}")
                return filepath
            else:
                print(f"    Football-Data: {resp.status_code} for {league}")
        except Exception as e:
            print(f"    Football-Data error: {e}")

        return None

    def parse_csv(self, filepath: str) -> List[Dict]:
        """Parse CSV into list of match dicts with results + odds."""
        import csv

        matches = []
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        match = {
                            "date": row.get("Date", ""),
                            "home": row.get("HomeTeam", ""),
                            "away": row.get("AwayTeam", ""),
                            "home_goals": int(row.get("FTHG", 0) or 0),
                            "away_goals": int(row.get("FTAG", 0) or 0),
                            "result": row.get("FTR", ""),  # H/D/A
                            "ht_home_goals": int(row.get("HTHG", 0) or 0),
                            "ht_away_goals": int(row.get("HTAG", 0) or 0),
                            "home_shots": int(row.get("HS", 0) or 0),
                            "away_shots": int(row.get("AS", 0) or 0),
                            "home_shots_target": int(row.get("HST", 0) or 0),
                            "away_shots_target": int(row.get("AST", 0) or 0),
                            "home_corners": int(row.get("HC", 0) or 0),
                            "away_corners": int(row.get("AC", 0) or 0),
                            "home_fouls": int(row.get("HF", 0) or 0),
                            "away_fouls": int(row.get("AF", 0) or 0),
                            "home_yellows": int(row.get("HY", 0) or 0),
                            "away_yellows": int(row.get("AY", 0) or 0),
                            "home_reds": int(row.get("HR", 0) or 0),
                            "away_reds": int(row.get("AR", 0) or 0),
                            "referee": row.get("Referee", ""),
                            # Bookmaker odds
                            "odds_home_pinnacle": float(row.get("PSH", 0) or 0),
                            "odds_draw_pinnacle": float(row.get("PSD", 0) or 0),
                            "odds_away_pinnacle": float(row.get("PSA", 0) or 0),
                            "odds_home_bet365": float(row.get("B365H", 0) or 0),
                            "odds_draw_bet365": float(row.get("B365D", 0) or 0),
                            "odds_away_bet365": float(row.get("B365A", 0) or 0),
                            "odds_over_25": float(row.get("BbAv>2.5", 0) or row.get("Avg>2.5", 0) or 0),
                            "odds_under_25": float(row.get("BbAv<2.5", 0) or row.get("Avg<2.5", 0) or 0),
                            "max_home": float(row.get("BbMxH", 0) or row.get("MaxH", 0) or 0),
                            "max_draw": float(row.get("BbMxD", 0) or row.get("MaxD", 0) or 0),
                            "max_away": float(row.get("BbMxA", 0) or row.get("MaxA", 0) or 0),
                        }
                        matches.append(match)
                    except (ValueError, TypeError):
                        continue

        except Exception as e:
            print(f"    CSV parse error: {e}")

        return matches

    def get_historical_matches(self, league: str, season: str = "2526") -> List[Dict]:
        """Download and parse historical matches for a league/season."""
        filepath = self.download_season(league, season)
        if filepath:
            return self.parse_csv(filepath)
        return []

    def get_referee_stats(self, league: str, season: str = "2526") -> Dict[str, Dict]:
        """
        Calculate referee card averages from historical data.
        Returns {referee_name: {avg_yellows, avg_reds, matches_officiated}}.
        """
        matches = self.get_historical_matches(league, season)
        referee_data = defaultdict(lambda: {"yellows": 0, "reds": 0, "matches": 0})

        for m in matches:
            ref = m.get("referee", "").strip()
            if ref:
                referee_data[ref]["yellows"] += m["home_yellows"] + m["away_yellows"]
                referee_data[ref]["reds"] += m["home_reds"] + m["away_reds"]
                referee_data[ref]["matches"] += 1

        result = {}
        for ref, data in referee_data.items():
            n = data["matches"]
            if n >= 3:  # Only include refs with 3+ matches
                result[ref] = {
                    "avg_yellows": round(data["yellows"] / n, 2),
                    "avg_reds": round(data["reds"] / n, 2),
                    "avg_total_cards": round((data["yellows"] + data["reds"]) / n, 2),
                    "matches": n,
                }

        return result

    def get_team_corner_stats(self, team_name: str, league: str,
                               season: str = "2526") -> Dict:
        """Calculate per-match corner stats for a team from historical data."""
        matches = self.get_historical_matches(league, season)

        corners_for = []
        corners_against = []

        for m in matches:
            if self._name_match(team_name, m["home"]):
                corners_for.append(m["home_corners"])
                corners_against.append(m["away_corners"])
            elif self._name_match(team_name, m["away"]):
                corners_for.append(m["away_corners"])
                corners_against.append(m["home_corners"])

        n = len(corners_for)
        if n == 0:
            return {"team": team_name, "corners_for_avg": 5.0,
                    "corners_against_avg": 4.5, "total_avg": 9.5, "matches": 0}

        return {
            "team": team_name,
            "corners_for_avg": round(sum(corners_for) / n, 2),
            "corners_against_avg": round(sum(corners_against) / n, 2),
            "total_avg": round((sum(corners_for) + sum(corners_against)) / n, 2),
            "matches": n,
            "data_source": "football-data.co.uk",
        }

    def _name_match(self, query: str, name: str) -> bool:
        q = query.lower().replace("fc", "").strip()
        n = name.lower().replace("fc", "").strip()
        return q in n or n in q


# ─── 4. WEATHER: OpenWeatherMap ───────────────────────────────────────
class WeatherCollector:
    """
    Match-day weather affects play:
    - Rain → more fouls, more throw-ins, fewer goals
    - Wind → affects corners, long balls
    - Heat → slower pace, more substitutions
    """

    # Stadium city coordinates for major teams
    STADIUM_LOCATIONS = {
        "Paris Saint-Germain": (48.8414, 2.2530),  # Parc des Princes
        "Toulouse": (43.5833, 1.4340),
        "Arsenal": (51.5549, -0.1084),
        "Manchester City": (53.4831, -2.2004),
        "Liverpool": (53.4308, -2.9608),
        "Real Madrid": (40.4530, -3.6883),
        "Barcelona": (41.3809, 2.1228),
        "Bayern Munich": (48.2188, 11.6247),
        "Inter Milan": (45.4781, 9.1240),
        "Juventus": (45.1096, 7.6413),
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENWEATHER_API_KEY", "")
        self.available = bool(self.api_key)

    def get_match_weather(self, home_team: str, match_datetime: str = None) -> Dict:
        """Get weather for match location."""
        if not self.available:
            return self._default_weather()

        coords = self.STADIUM_LOCATIONS.get(home_team)
        if not coords:
            return self._default_weather()

        lat, lon = coords
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather"
            resp = requests.get(url, params={
                "lat": lat, "lon": lon,
                "appid": self.api_key,
                "units": "metric",
            }, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                weather = data.get("weather", [{}])[0]
                main = data.get("main", {})
                wind = data.get("wind", {})
                rain = data.get("rain", {})

                return {
                    "temperature": main.get("temp", 15),
                    "humidity": main.get("humidity", 60),
                    "wind_speed": wind.get("speed", 3),
                    "wind_gust": wind.get("gust", 5),
                    "condition": weather.get("main", "Clear"),
                    "description": weather.get("description", ""),
                    "rain_1h": rain.get("1h", 0),
                    "rain_3h": rain.get("3h", 0),
                    # Impact flags
                    "is_rainy": weather.get("main", "").lower() in ("rain", "drizzle", "thunderstorm"),
                    "is_windy": wind.get("speed", 0) > 8,
                    "is_hot": main.get("temp", 15) > 30,
                    "is_cold": main.get("temp", 15) < 5,
                    "data_source": "openweathermap",
                }
        except:
            pass

        return self._default_weather()

    def _default_weather(self) -> Dict:
        return {
            "temperature": 15, "humidity": 60, "wind_speed": 3,
            "wind_gust": 5, "condition": "Clear", "description": "",
            "rain_1h": 0, "rain_3h": 0,
            "is_rainy": False, "is_windy": False, "is_hot": False, "is_cold": False,
            "data_source": "default",
        }


# ─── 5. ORCHESTRATOR: Combines All Sources ────────────────────────────
class MultiSourceOrchestrator:
    """
    Orchestrates data collection from all sources and combines
    into a unified match profile.
    """

    def __init__(self, stats_api_key: str = None, odds_api_key: str = None,
                 weather_api_key: str = None):
        self.understat = UnderstatCollector()
        self.espn = ESPNCollector()
        self.football_data = FootballDataCollector()
        self.weather = WeatherCollector(api_key=weather_api_key)

        # Import existing collectors if available
        try:
            from data.live_collector import LiveOddsCollector, LiveStatsCollector
            self.odds_collector = LiveOddsCollector(odds_api_key) if odds_api_key else None
            self.stats_collector = LiveStatsCollector(stats_api_key) if stats_api_key else None
        except ImportError:
            self.odds_collector = None
            self.stats_collector = None

    def get_full_match_profile(self, home_team: str, away_team: str,
                                league: str, match_date: str = None,
                                referee: str = None) -> Dict:
        """
        Build the COMPLETE data profile for a match by querying all sources.
        This is what gets passed to the prediction agents.
        """
        print(f"\n  Collecting data for {home_team} vs {away_team} ({league})...")

        profile = {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "match_date": match_date,
            "referee": referee,
        }

        # 1. xG Data (Understat)
        print("    [1/5] Understat xG data...")
        profile["home_xg"] = self.understat.get_team_xg(home_team, league)
        profile["away_xg"] = self.understat.get_team_xg(away_team, league)

        # 2. League position + context (ESPN)
        print("    [2/5] ESPN standings + context...")
        profile["home_position"] = self.espn.get_team_position(home_team, league)
        profile["away_position"] = self.espn.get_team_position(away_team, league)

        # 3. Historical corners + referee (Football-Data.co.uk)
        print("    [3/5] Historical stats (corners, referee)...")
        profile["home_corners"] = self.football_data.get_team_corner_stats(home_team, league)
        profile["away_corners"] = self.football_data.get_team_corner_stats(away_team, league)

        if referee:
            ref_stats = self.football_data.get_referee_stats(league)
            profile["referee_stats"] = ref_stats.get(referee, {
                "avg_yellows": 4.0, "avg_reds": 0.08, "avg_total_cards": 4.08, "matches": 0
            })
        else:
            profile["referee_stats"] = None

        # 4. Weather (if API key available)
        print("    [4/5] Weather data...")
        profile["weather"] = self.weather.get_match_weather(home_team)

        # 5. API-Football form + H2H (existing collectors)
        print("    [5/5] API-Football form + H2H...")
        if self.stats_collector:
            try:
                profile["home_form"] = self.stats_collector.get_team_form(home_team)
                profile["away_form"] = self.stats_collector.get_team_form(away_team)
                profile["h2h"] = self.stats_collector.get_head_to_head(home_team, away_team)
                profile["home_stats"] = self.stats_collector.get_team_stats(home_team)
                profile["away_stats"] = self.stats_collector.get_team_stats(away_team)
            except:
                profile["home_form"] = None
                profile["away_form"] = None
                profile["h2h"] = None

        # Combine xG into team stats (for backward compatibility with agents)
        profile["enriched_home_stats"] = self._enrich_stats(
            profile.get("home_stats"), profile["home_xg"],
            profile["home_position"], profile["home_corners"]
        )
        profile["enriched_away_stats"] = self._enrich_stats(
            profile.get("away_stats"), profile["away_xg"],
            profile["away_position"], profile["away_corners"]
        )

        print(f"  ✓ Full profile complete — {self._count_sources(profile)} data sources used")
        return profile

    def _enrich_stats(self, base_stats: Dict, xg_data: Dict,
                       position_data: Dict, corners_data: Dict) -> Dict:
        """Merge all data sources into a unified stats dict."""
        if base_stats is None:
            base_stats = {}

        enriched = dict(base_stats)

        # Add xG data
        if xg_data and xg_data.get("data_source") != "none":
            enriched["xg_per_match"] = xg_data["xg_per_match"]
            enriched["xga_per_match"] = xg_data["xga_per_match"]
            enriched["home_xg_avg"] = xg_data["home_xg_avg"]
            enriched["away_xg_avg"] = xg_data["away_xg_avg"]
            enriched["home_xga_avg"] = xg_data["home_xga_avg"]
            enriched["away_xga_avg"] = xg_data["away_xga_avg"]
            enriched["recent_xg_avg"] = xg_data["recent_xg_avg"]
            enriched["recent_xga_avg"] = xg_data["recent_xga_avg"]
            enriched["ppda"] = xg_data["ppda"]
            enriched["xg_overperformance"] = xg_data["xg_overperformance"]
            enriched["has_xg_data"] = True
        else:
            enriched["has_xg_data"] = False

        # Add position/context
        if position_data:
            enriched["league_position"] = position_data.get("position", 0)
            enriched["motivation_context"] = position_data.get("context", "unknown")
            enriched["points"] = position_data.get("points", 0)

        # Add real corner stats
        if corners_data and corners_data.get("data_source"):
            enriched["real_corners_for_avg"] = corners_data["corners_for_avg"]
            enriched["real_corners_against_avg"] = corners_data["corners_against_avg"]

        return enriched

    def _count_sources(self, profile: Dict) -> int:
        """Count how many data sources contributed data."""
        sources = set()
        if profile.get("home_xg", {}).get("data_source") == "understat":
            sources.add("understat")
        if profile.get("home_position", {}).get("position", 0) > 0:
            sources.add("espn")
        if profile.get("home_corners", {}).get("data_source"):
            sources.add("football-data")
        if profile.get("weather", {}).get("data_source") != "default":
            sources.add("openweathermap")
        if profile.get("home_form"):
            sources.add("api-football")
        return len(sources)


# ─── Quick Test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Multi-Source Collector...")

    # Test Understat
    understat = UnderstatCollector()
    psg_xg = understat.get_team_xg("Paris Saint-Germain", "Ligue 1")
    print(f"\nPSG xG Profile:")
    print(f"  xG/match: {psg_xg['xg_per_match']}")
    print(f"  xGA/match: {psg_xg['xga_per_match']}")
    print(f"  Home xG: {psg_xg['home_xg_avg']}, Away xG: {psg_xg['away_xg_avg']}")
    print(f"  Recent 5 xG: {psg_xg['recent_xg_avg']}")
    print(f"  PPDA: {psg_xg['ppda']}")
    print(f"  xG overperformance: {psg_xg['xg_overperformance']}")

    tou_xg = understat.get_team_xg("Toulouse", "Ligue 1")
    print(f"\nToulouse xG Profile:")
    print(f"  xG/match: {tou_xg['xg_per_match']}")
    print(f"  xGA/match: {tou_xg['xga_per_match']}")
    print(f"  PPDA: {tou_xg['ppda']}")

    # Test ESPN
    espn = ESPNCollector()
    psg_pos = espn.get_team_position("PSG", "Ligue 1")
    print(f"\nPSG Position: {psg_pos.get('position')} ({psg_pos.get('context')})")

    # Test Football-Data
    fd = FootballDataCollector()
    fd_matches = fd.get_historical_matches("Ligue 1")
    if fd_matches:
        print(f"\nFootball-Data: {len(fd_matches)} historical matches loaded")
        # Show first match
        m = fd_matches[0]
        print(f"  First: {m['date']} {m['home']} {m['home_goals']}-{m['away_goals']} {m['away']}")
        print(f"  Corners: {m['home_corners']}-{m['away_corners']}, Cards: {m['home_yellows']+m['away_yellows']}Y")
        print(f"  Referee: {m['referee']}")

        ref_stats = fd.get_referee_stats("Ligue 1")
        if ref_stats:
            print(f"\n  Referee stats ({len(ref_stats)} refs):")
            for ref, stats in sorted(ref_stats.items(), key=lambda x: x[1]["avg_total_cards"], reverse=True)[:5]:
                print(f"    {ref}: {stats['avg_total_cards']:.1f} cards/match ({stats['matches']} matches)")
    else:
        print("\nFootball-Data: no data available (season may not have started)")
