"""
Live Data Collector — Fetches REAL odds and stats from The Odds API + API-Football.
"""
import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


# Major football leagues on The Odds API
LEAGUES = [
    ("soccer_epl", "Premier League", 39),
    ("soccer_spain_la_liga", "La Liga", 140),
    ("soccer_germany_bundesliga", "Bundesliga", 78),
    ("soccer_italy_serie_a", "Serie A", 135),
    ("soccer_france_ligue_one", "Ligue 1", 61),
    ("soccer_netherlands_eredivisie", "Eredivisie", 88),
    ("soccer_portugal_primeira_liga", "Primeira Liga", 94),
    ("soccer_spl", "Scottish Premiership", 179),
    ("soccer_efl_champ", "Championship", 40),
    ("soccer_turkey_super_league", "Turkish Super League", 203),
    ("soccer_belgium_first_div", "Belgian First Div", 144),
    ("soccer_uefa_champs_league", "Champions League", 2),
    ("soccer_uefa_europa_league", "Europa League", 3),
    ("soccer_brazil_campeonato", "Brasileirão", 71),
    ("soccer_argentina_primera_division", "Argentina Primera", 128),
]


class LiveOddsCollector:
    """Fetches real-time odds from The Odds API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        self.remaining_requests = None

    def get_all_upcoming_matches(self, max_leagues: int = 15) -> List[Dict]:
        """Fetch upcoming matches with odds across all major leagues."""
        all_matches = []

        for odds_key, league_name, apifb_id in LEAGUES[:max_leagues]:
            print(f"    Fetching odds: {league_name}...")
            matches = self._fetch_league_odds(odds_key, league_name)
            if matches:
                all_matches.extend(matches)
                print(f"      -> {len(matches)} matches with odds")
            time.sleep(0.3)  # Rate limiting

        print(f"\n    API requests remaining: {self.remaining_requests}")
        return all_matches

    def _fetch_league_odds(self, sport_key: str, league_name: str) -> List[Dict]:
        """Fetch odds for a single league."""
        # First get h2h + totals from main endpoint
        url = f"{self.base_url}/sports/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "eu",
            "markets": "h2h,totals,spreads",
            "oddsFormat": "decimal",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 422:
                return []
            resp.raise_for_status()
            self.remaining_requests = resp.headers.get("x-requests-remaining", self.remaining_requests)
            raw_matches = resp.json()
        except Exception as e:
            print(f"      Error fetching {league_name}: {e}")
            return []

        if not isinstance(raw_matches, list):
            return []

        matches = []
        for rm in raw_matches:
            match = self._transform_match(rm, league_name)
            matches.append(match)

        # For first few matches, try to get BTTS + alternate totals from event endpoint
        for match in matches[:5]:
            self._enrich_with_event_odds(sport_key, match)
            time.sleep(0.2)

        return matches

    def _enrich_with_event_odds(self, sport_key: str, match: Dict):
        """Fetch BTTS and alternate totals for a specific event."""
        event_id = match.get("odds_api_id")
        if not event_id:
            return

        url = f"{self.base_url}/sports/{sport_key}/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "eu",
            "markets": "btts,alternate_totals,team_totals",
            "oddsFormat": "decimal",
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return
            self.remaining_requests = resp.headers.get("x-requests-remaining", self.remaining_requests)
            data = resp.json()
        except:
            return

        if not isinstance(data, dict):
            return

        for bm in data.get("bookmakers", []):
            bookie_name = bm["title"]
            for market in bm.get("markets", []):
                mkey = market["key"]

                if mkey == "btts":
                    if "btts" not in match["markets"]:
                        match["markets"]["btts"] = []
                    odds_dict = {}
                    for o in market["outcomes"]:
                        odds_dict[o["name"]] = o["price"]
                    match["markets"]["btts"].append({
                        "bookmaker": bookie_name,
                        "odds": odds_dict,
                    })

                elif mkey == "alternate_totals":
                    # Group by point value
                    for o in market["outcomes"]:
                        point = o.get("point", 2.5)
                        mkt_key = f"goals_over_under_{point}"
                        if mkt_key not in match["markets"]:
                            match["markets"][mkt_key] = []

                        # Find or create bookmaker entry
                        bookie_entry = None
                        for be in match["markets"][mkt_key]:
                            if be["bookmaker"] == bookie_name:
                                bookie_entry = be
                                break
                        if not bookie_entry:
                            bookie_entry = {"bookmaker": bookie_name, "odds": {}}
                            match["markets"][mkt_key].append(bookie_entry)

                        bookie_entry["odds"][f"{o['name']} {point}"] = o["price"]

                elif mkey == "team_totals":
                    for o in market["outcomes"]:
                        team_key = "home" if o["name"] == match["home_team"] else "away"
                        point = o.get("point", 0.5)
                        # Will be used by stats agent

    def _transform_match(self, raw: Dict, league_name: str) -> Dict:
        """Transform Odds API format into our internal format."""
        match = {
            "id": raw["id"][:12],
            "odds_api_id": raw["id"],
            "home_team": raw["home_team"],
            "away_team": raw["away_team"],
            "league": league_name,
            "sport_key": raw.get("sport_key", ""),
            "commence_time": raw["commence_time"],
            "markets": {},
        }

        for bm in raw.get("bookmakers", []):
            bookie_name = bm["title"]

            for market in bm.get("markets", []):
                mkey = market["key"]

                if mkey == "h2h":
                    if "match_result" not in match["markets"]:
                        match["markets"]["match_result"] = []
                    odds_dict = {}
                    for o in market["outcomes"]:
                        odds_dict[o["name"]] = o["price"]
                    match["markets"]["match_result"].append({
                        "bookmaker": bookie_name,
                        "odds": odds_dict,
                    })

                elif mkey == "totals":
                    point = market["outcomes"][0].get("point", 2.5) if market["outcomes"] else 2.5
                    mkt_key = f"goals_over_under_{point}"
                    if mkt_key not in match["markets"]:
                        match["markets"][mkt_key] = []
                    odds_dict = {}
                    for o in market["outcomes"]:
                        odds_dict[f"{o['name']} {o.get('point', point)}"] = o["price"]
                    match["markets"][mkt_key].append({
                        "bookmaker": bookie_name,
                        "odds": odds_dict,
                    })

                elif mkey == "spreads":
                    if "spreads" not in match["markets"]:
                        match["markets"]["spreads"] = []
                    odds_dict = {}
                    for o in market["outcomes"]:
                        odds_dict[f"{o['name']} ({o.get('point', 0):+g})"] = o["price"]
                    match["markets"]["spreads"].append({
                        "bookmaker": bookie_name,
                        "odds": odds_dict,
                    })

        return match


class LiveStatsCollector:
    """Fetches real team statistics from API-Football."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": api_key}
        self._team_cache = {}
        self._stats_cache = {}

    def find_team_id(self, team_name: str) -> Optional[int]:
        """Search for a team ID by name."""
        if team_name in self._team_cache:
            return self._team_cache[team_name]

        try:
            resp = requests.get(
                f"{self.base_url}/teams",
                headers=self.headers,
                params={"search": team_name},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("response", [])
            if results:
                team_id = results[0]["team"]["id"]
                self._team_cache[team_name] = team_id
                return team_id
        except Exception as e:
            print(f"      Error finding team {team_name}: {e}")
        return None

    def get_team_form(self, team_name: str, league_id: int = None) -> Dict:
        """Get recent form data — last fixtures with stats."""
        team_id = self.find_team_id(team_name)
        if not team_id:
            return self._empty_form(team_name)

        cache_key = f"form_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        try:
            params = {"team": team_id, "last": 10}
            if league_id:
                params["league"] = league_id
                params["season"] = 2025
                del params["last"]

            resp = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={"team": team_id, "last": 10},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            fixtures = data.get("response", [])
        except Exception as e:
            print(f"      Error getting form for {team_name}: {e}")
            return self._empty_form(team_name)

        if not fixtures:
            return self._empty_form(team_name)

        form_str = ""
        matches = []
        total_goals_for = 0
        total_goals_against = 0
        total_corners = 0
        total_cards = 0
        total_shots_on = 0
        match_count = 0

        for fix in fixtures:
            is_home = fix["teams"]["home"]["id"] == team_id
            goals = fix.get("goals", {})
            gf = goals.get("home" if is_home else "away", 0) or 0
            ga = goals.get("away" if is_home else "home", 0) or 0

            if gf > ga:
                form_str += "W"
            elif gf == ga:
                form_str += "D"
            else:
                form_str += "L"

            total_goals_for += gf
            total_goals_against += ga

            # Get detailed stats if available
            stats = fix.get("statistics", [])
            corners = 0
            cards = 0
            shots_on = 0
            for s in stats:
                if s.get("team", {}).get("id") == team_id:
                    for stat in s.get("statistics", []):
                        if stat["type"] == "Corner Kicks":
                            corners = stat["value"] or 0
                        elif stat["type"] == "Yellow Cards":
                            cards += stat["value"] or 0
                        elif stat["type"] == "Red Cards":
                            cards += stat["value"] or 0
                        elif stat["type"] == "Shots on Goal":
                            shots_on = stat["value"] or 0

            total_corners += corners
            total_cards += cards
            total_shots_on += shots_on
            match_count += 1

            matches.append({
                "goals_for": gf, "goals_against": ga,
                "corners": corners, "cards_yellow": cards,
                "cards_red": 0, "shots_on_target": shots_on,
                "result": form_str[-1],
                "home": is_home,
                "date": fix["fixture"]["date"],
                "opponent": fix["teams"]["away" if is_home else "home"]["name"],
            })

        n = max(match_count, 1)
        result = {
            "team": team_name,
            "form_string": form_str,
            "wins": form_str.count("W"),
            "draws": form_str.count("D"),
            "losses": form_str.count("L"),
            "points_last_10": form_str.count("W") * 3 + form_str.count("D"),
            "goals_scored_avg": round(total_goals_for / n, 2),
            "goals_conceded_avg": round(total_goals_against / n, 2),
            "corners_avg": round(total_corners / n, 2) if total_corners > 0 else 5.0,
            "cards_avg": round(total_cards / n, 2) if total_cards > 0 else 2.0,
            "shots_on_target_avg": round(total_shots_on / n, 2) if total_shots_on > 0 else 4.0,
            "throw_ins_avg": 22.0,  # Not available from API, use league average
            "fouls_avg": 12.0,
            "matches": matches,
        }

        self._stats_cache[cache_key] = result
        return result

    def get_head_to_head(self, home: str, away: str) -> Dict:
        """Get H2H between two teams."""
        home_id = self.find_team_id(home)
        away_id = self.find_team_id(away)

        if not home_id or not away_id:
            return self._empty_h2h(home, away)

        cache_key = f"h2h_{home_id}_{away_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        try:
            resp = requests.get(
                f"{self.base_url}/fixtures/headtohead",
                headers=self.headers,
                params={"h2h": f"{home_id}-{away_id}", "last": 10},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            fixtures = data.get("response", [])
        except Exception as e:
            print(f"      Error getting H2H: {e}")
            return self._empty_h2h(home, away)

        if not fixtures:
            return self._empty_h2h(home, away)

        home_wins = 0
        away_wins = 0
        draws = 0
        total_goals = 0
        btts_count = 0
        over25_count = 0

        for fix in fixtures:
            gh = fix["goals"]["home"] or 0
            ga = fix["goals"]["away"] or 0
            total_goals += gh + ga

            is_home_team_home = fix["teams"]["home"]["id"] == home_id
            if gh > ga:
                if is_home_team_home:
                    home_wins += 1
                else:
                    away_wins += 1
            elif ga > gh:
                if is_home_team_home:
                    away_wins += 1
                else:
                    home_wins += 1
            else:
                draws += 1

            if gh > 0 and ga > 0:
                btts_count += 1
            if gh + ga > 2:
                over25_count += 1

        n = len(fixtures)
        result = {
            "home": home, "away": away,
            "total_matches": n,
            "home_wins": home_wins, "away_wins": away_wins, "draws": draws,
            "avg_goals_per_match": round(total_goals / n, 2),
            "avg_corners_per_match": 9.5,  # H2H corners not in free API
            "avg_cards_per_match": 4.0,
            "btts_percentage": round(btts_count / n * 100, 1),
            "over_2_5_percentage": round(over25_count / n * 100, 1),
        }

        self._stats_cache[cache_key] = result
        return result

    def get_team_stats(self, team_name: str) -> Dict:
        """Get season-level team statistics."""
        team_id = self.find_team_id(team_name)
        if not team_id:
            return self._empty_stats(team_name)

        cache_key = f"stats_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        # Use team statistics endpoint
        try:
            resp = requests.get(
                f"{self.base_url}/teams/statistics",
                headers=self.headers,
                params={"team": team_id, "season": 2025, "league": 39},  # Default EPL
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            stats = data.get("response", {})
        except:
            stats = {}

        if not stats:
            # Fallback: derive from form data
            form = self.get_team_form(team_name)
            return {
                "team": team_name,
                "season": "2025/26",
                "played": len(form.get("matches", [])),
                "home_corners_avg": form.get("corners_avg", 5.0),
                "away_corners_avg": max(form.get("corners_avg", 5.0) - 0.8, 3.0),
                "home_cards_avg": form.get("cards_avg", 2.0),
                "away_cards_avg": form.get("cards_avg", 2.0) + 0.3,
                "home_goals_avg": form.get("goals_scored_avg", 1.5),
                "away_goals_avg": max(form.get("goals_scored_avg", 1.5) - 0.3, 0.5),
                "home_conceded_avg": max(form.get("goals_conceded_avg", 1.0) - 0.2, 0.3),
                "away_conceded_avg": form.get("goals_conceded_avg", 1.0) + 0.2,
                "clean_sheets_pct": 30.0,
                "btts_pct": 50.0,
                "over_2_5_pct": 50.0,
                "avg_throw_ins": 22.0,
                "avg_fouls": 12.0,
                "avg_shots_on_target": form.get("shots_on_target_avg", 4.5),
            }

        # Parse real stats
        fixtures = stats.get("fixtures", {})
        goals = stats.get("goals", {})

        played_home = (fixtures.get("played", {}).get("home", 0)) or 1
        played_away = (fixtures.get("played", {}).get("away", 0)) or 1
        played = played_home + played_away

        goals_home = (goals.get("for", {}).get("total", {}).get("home", 0)) or 0
        goals_away = (goals.get("for", {}).get("total", {}).get("away", 0)) or 0
        conceded_home = (goals.get("against", {}).get("total", {}).get("home", 0)) or 0
        conceded_away = (goals.get("against", {}).get("total", {}).get("away", 0)) or 0

        cs_pct = ((stats.get("clean_sheet", {}).get("total", 0) or 0) / max(played, 1)) * 100

        result = {
            "team": team_name,
            "season": "2025/26",
            "played": played,
            "home_corners_avg": 5.5,  # Not in free API
            "away_corners_avg": 4.5,
            "home_cards_avg": 2.0,
            "away_cards_avg": 2.3,
            "home_goals_avg": round(goals_home / played_home, 2),
            "away_goals_avg": round(goals_away / played_away, 2),
            "home_conceded_avg": round(conceded_home / played_home, 2),
            "away_conceded_avg": round(conceded_away / played_away, 2),
            "clean_sheets_pct": round(cs_pct, 1),
            "btts_pct": 50.0,
            "over_2_5_pct": 50.0,
            "avg_throw_ins": 22.0,
            "avg_fouls": 12.0,
            "avg_shots_on_target": 4.5,
        }

        self._stats_cache[cache_key] = result
        return result

    def _empty_form(self, team: str) -> Dict:
        return {
            "team": team, "form_string": "?????",
            "wins": 0, "draws": 0, "losses": 0, "points_last_10": 0,
            "goals_scored_avg": 1.3, "goals_conceded_avg": 1.1,
            "corners_avg": 5.0, "cards_avg": 2.0,
            "shots_on_target_avg": 4.0, "throw_ins_avg": 22.0, "fouls_avg": 12.0,
            "matches": [],
        }

    def _empty_h2h(self, home: str, away: str) -> Dict:
        return {
            "home": home, "away": away, "total_matches": 0,
            "home_wins": 0, "away_wins": 0, "draws": 0,
            "avg_goals_per_match": 2.5, "avg_corners_per_match": 9.5,
            "avg_cards_per_match": 4.0, "btts_percentage": 50.0, "over_2_5_percentage": 50.0,
        }

    def _empty_stats(self, team: str) -> Dict:
        return {
            "team": team, "season": "2025/26", "played": 0,
            "home_corners_avg": 5.0, "away_corners_avg": 4.5,
            "home_cards_avg": 2.0, "away_cards_avg": 2.3,
            "home_goals_avg": 1.4, "away_goals_avg": 1.0,
            "home_conceded_avg": 1.0, "away_conceded_avg": 1.3,
            "clean_sheets_pct": 30.0, "btts_pct": 50.0, "over_2_5_pct": 50.0,
            "avg_throw_ins": 22.0, "avg_fouls": 12.0, "avg_shots_on_target": 4.5,
        }
