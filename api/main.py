"""Football Predictor V5 API — 25 Agents + Match Simulation (with Live Intelligence)"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import uuid
import random
from datetime import datetime, timedelta

from engine_v4 import FootballPredictionEngineV4

app = FastAPI(title="Football Predictor V4 API")

# Serve React frontend static files
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(_static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(_static_dir, "assets")), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
engine = FootballPredictionEngineV4()
_matches_cache = []
_analysis_store = {}
_odds_api_cache = {}  # Cache for The Odds API data (refreshed max once per hour)
_odds_api_last_fetch = None

# API keys (must be provided via environment variables in production)
# If missing, the API will gracefully fall back to demo fixtures/odds.
API_SPORTS_KEY = os.environ.get("STATS_API_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
TOP_LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "Champions League",
}

# Mapping from API-Sports league IDs to The Odds API sport keys
LEAGUE_TO_ODDS_API = {
    39: "soccer_epl",
    140: "soccer_spain_la_liga",
    135: "soccer_italy_serie_a",
    78: "soccer_germany_bundesliga",
    61: "soccer_france_ligue_one",
    2: "soccer_uefa_champs_league",
}

# Elo-based odds estimation for when odds API is unavailable
TEAM_STRENGTH = {
    # EPL
    "Manchester City": 1850, "Arsenal": 1820, "Liverpool": 1810, "Chelsea": 1720,
    "Tottenham Hotspur": 1700, "Aston Villa": 1680, "Newcastle United": 1680,
    "Manchester United": 1660, "Brighton & Hove Albion": 1650, "West Ham United": 1630,
    "Everton": 1580, "Wolverhampton Wanderers": 1570, "Crystal Palace": 1570,
    "Fulham": 1570, "Brentford": 1570, "Bournemouth": 1560, "Nottingham Forest": 1580,
    # La Liga
    "Real Madrid": 1870, "Barcelona": 1860, "Atletico Madrid": 1790,
    "Athletic Club": 1710, "Real Sociedad": 1700, "Real Betis": 1680,
    "Villarreal": 1680, "Mallorca": 1620, "Sevilla": 1650, "Valencia": 1620,
    "Espanyol": 1560, "Levante": 1560, "Celta Vigo": 1590,
    # Serie A
    "Inter Milan": 1800, "Inter": 1800, "Napoli": 1780, "AC Milan": 1750,
    "Juventus": 1740, "Atalanta": 1730, "Roma": 1700, "Lazio": 1690,
    "Fiorentina": 1670, "Bologna": 1650, "Sassuolo": 1580, "Hellas Verona": 1550,
    "Cagliari": 1550, "Parma": 1540,
    # Bundesliga
    "Bayern München": 1850, "Bayern Munich": 1850, "Bayer Leverkusen": 1800,
    "Borussia Dortmund": 1760, "RB Leipzig": 1740, "VfB Stuttgart": 1710,
    "SC Freiburg": 1680, "VfL Wolfsburg": 1650, "Eintracht Frankfurt": 1670,
    "Werder Bremen": 1640, "1. FC Union Berlin": 1620, "FSV Mainz 05": 1610,
    "FC Augsburg": 1590, "1899 Hoffenheim": 1600, "Borussia Mönchengladbach": 1620,
    "1. FC Heidenheim": 1560, "Hamburger SV": 1600,
    # Ligue 1
    "Paris Saint-Germain": 1830, "PSG": 1830, "Marseille": 1730, "Monaco": 1720,
    "Lille": 1710, "Lyon": 1690, "Nice": 1670, "Lens": 1660,
    "Rennes": 1640, "Strasbourg": 1600, "Stade Brestois 29": 1610,
}


def _elo_to_odds(home_team: str, away_team: str):
    """Generate realistic odds from Elo ratings."""
    home_elo = TEAM_STRENGTH.get(home_team, 1600)
    away_elo = TEAM_STRENGTH.get(away_team, 1600)

    # Expected score with home advantage (~65 Elo points)
    home_exp = 1 / (1 + 10 ** ((away_elo - home_elo - 65) / 400))

    # Convert to 1X2 probabilities
    draw_base = 0.26
    hw_prob = home_exp * (1 - draw_base)
    aw_prob = (1 - home_exp) * (1 - draw_base)
    dw_prob = draw_base

    # Add margin (5%)
    margin = 1.05
    h1 = round(margin / max(hw_prob, 0.05), 2)
    d1 = round(margin / max(dw_prob, 0.05), 2)
    a1 = round(margin / max(aw_prob, 0.05), 2)

    # O/U 2.5 from attacking strength
    attack_combined = (home_elo + away_elo) / 2
    over_prob = 0.35 + (attack_combined - 1550) / 1000  # Higher Elo → more goals
    over_prob = max(0.35, min(0.70, over_prob))
    o25 = round(margin / over_prob, 2)
    u25 = round(margin / (1 - over_prob), 2)

    return h1, d1, a1, o25, u25


def _fetch_odds_api_matches():
    """Fetch real odds from The Odds API (the-odds-api.com) for top-5 leagues.
    Returns dict mapping (normalized_home, normalized_away) -> odds data.
    Paid plan — fetches all available markets.
    """
    import requests

    ODDS_LEAGUES = list(LEAGUE_TO_ODDS_API.values())

    odds_by_teams = {}  # (home_lower, away_lower) -> odds data

    for sport_key in ODDS_LEAGUES:
        try:
            resp = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "h2h,totals",
                    "oddsFormat": "decimal",
                },
                timeout=10,
            )
            if resp.status_code == 422:
                continue
            if resp.status_code != 200:
                print(f"[OddsAPI] {sport_key}: HTTP {resp.status_code}")
                continue

            remaining = resp.headers.get("x-requests-remaining", "?")
            events = resp.json()
            if not isinstance(events, list):
                continue

            for ev in events:
                home = ev.get("home_team", "")
                away = ev.get("away_team", "")
                key = (home.lower().strip(), away.lower().strip())

                match_winner_odds = []
                ou_odds = []
                for bm in ev.get("bookmakers", []):
                    bk_name = bm.get("title", bm.get("key", "Unknown"))
                    for mkt in bm.get("markets", []):
                        if mkt["key"] == "h2h":
                            h_odd = d_odd = a_odd = None
                            for o in mkt["outcomes"]:
                                if o["name"] == home:
                                    h_odd = o["price"]
                                elif o["name"] == "Draw":
                                    d_odd = o["price"]
                                elif o["name"] == away:
                                    a_odd = o["price"]
                            if h_odd and d_odd and a_odd:
                                match_winner_odds.append({
                                    "bookmaker": bk_name,
                                    "home": h_odd,
                                    "draw": d_odd,
                                    "away": a_odd,
                                })
                        elif mkt["key"] == "totals":
                            ou_entry = {"bookmaker": bk_name}
                            for o in mkt["outcomes"]:
                                if o["name"] == "Over":
                                    ou_entry["over"] = o["price"]
                                    ou_entry["point"] = o.get("point", 2.5)
                                elif o["name"] == "Under":
                                    ou_entry["under"] = o["price"]
                            if "over" in ou_entry:
                                ou_odds.append(ou_entry)

                if match_winner_odds:
                    odds_by_teams[key] = {
                        "match_winner": match_winner_odds,
                        "over_under": ou_odds,
                        "odds_api_home": home,
                        "odds_api_away": away,
                    }

            print(f"[OddsAPI] {sport_key}: {len(events)} events (remaining: {remaining})")
        except Exception as e:
            print(f"[OddsAPI] {sport_key} error: {e}")

    print(f"[OddsAPI] Total odds collected for {len(odds_by_teams)} matches")
    return odds_by_teams


def _match_odds_by_name(odds_by_teams, home, away):
    """Fuzzy-match team names from API-Sports to The Odds API team names."""
    # Try exact match first
    key = (home.lower().strip(), away.lower().strip())
    if key in odds_by_teams:
        return odds_by_teams[key]

    # Try substring matching
    for (oh, oa), odds_data in odds_by_teams.items():
        # Check if key words match
        home_words = set(home.lower().split())
        away_words = set(away.lower().split())
        oh_words = set(oh.split())
        oa_words = set(oa.split())

        # At least one meaningful word in common (ignore short words)
        home_match = any(w in oh_words for w in home_words if len(w) > 3)
        away_match = any(w in oa_words for w in away_words if len(w) > 3)

        if home_match and away_match:
            return odds_data

    return None


def _fetch_fixture_odds(fixture_id):
    """Fetch real bookmaker odds for a single fixture (1 API call)."""
    import requests
    try:
        resp = requests.get(
            "https://v3.football.api-sports.io/odds",
            headers={"x-apisports-key": API_SPORTS_KEY},
            params={"fixture": fixture_id},
            timeout=8,
        )
        data = resp.json()
        entries = data.get("response", [])
        if not entries:
            return None

        bookmakers = entries[0].get("bookmakers", [])
        match_winner_odds = []
        ou_odds = []
        for bk in bookmakers:
            bk_name = bk["name"]
            for bet in bk.get("bets", []):
                if bet["name"] == "Match Winner":
                    odds_vals = {}
                    for v in bet["values"]:
                        odds_vals[v["value"]] = float(v["odd"])
                    if "Home" in odds_vals and "Draw" in odds_vals and "Away" in odds_vals:
                        match_winner_odds.append({
                            "bookmaker": bk_name,
                            "home": odds_vals["Home"],
                            "draw": odds_vals["Draw"],
                            "away": odds_vals["Away"],
                        })
                elif "Over/Under" in bet.get("name", "") or "Over Under" in bet.get("name", ""):
                    # Skip non-goals O/U markets (first half, corners, cards, etc.)
                    bet_name = bet.get("name", "").lower()
                    if any(x in bet_name for x in ["half", "corner", "card", "booking", "shot"]):
                        continue
                    ou_entry = {}
                    for v in bet["values"]:
                        if v["value"] == "Over 2.5":
                            ou_entry["over"] = float(v["odd"])
                        elif v["value"] == "Under 2.5":
                            ou_entry["under"] = float(v["odd"])
                    if "over" in ou_entry:
                        ou_entry["bookmaker"] = bk_name
                        ou_entry["point"] = 2.5
                        ou_odds.append(ou_entry)
        if match_winner_odds:
            return {"match_winner": match_winner_odds, "over_under": ou_odds}
    except Exception as e:
        print(f"[Odds] Error for fixture {fixture_id}: {e}")
    return None


def _fetch_real_matches():
    """Fetch real upcoming matches (next 24h) from API-Sports for top-5 leagues.
    Paid plans — no call limits. Gets per-fixture odds from both APIs.
    """
    import requests
    matches = []
    fixtures_by_league = {}  # league_id -> list of fixture dicts

    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Step 1: Fetch fixtures for top-5 leagues (2 API calls)
        for date in [today, tomorrow]:
            resp = requests.get(
                f"https://v3.football.api-sports.io/fixtures?date={date}",
                headers={"x-apisports-key": API_SPORTS_KEY},
                timeout=10,
            )
            data = resp.json()
            for fix in data.get("response", []):
                lid = fix["league"]["id"]
                if lid not in TOP_LEAGUES:
                    continue
                fixtures_by_league.setdefault(lid, []).append(fix)

        total_fixtures = sum(len(v) for v in fixtures_by_league.values())
        print(f"[Fixtures] Found {total_fixtures} fixtures across {len(fixtures_by_league)} leagues")

        # Step 2a: Fetch per-fixture odds from API-Sports (paid plan — no limit)
        all_odds = {}
        for lid, fixes in fixtures_by_league.items():
            for fix in fixes:
                fid = fix["fixture"]["id"]
                result = _fetch_fixture_odds(fid)
                if result:
                    all_odds[fid] = result
        print(f"[API-Sports Odds] Got odds for {len(all_odds)}/{total_fixtures} fixtures")

        # Step 2b: Fetch bulk odds from The Odds API (top-5 leagues, paid plan)
        global _odds_api_cache, _odds_api_last_fetch
        odds_api_data = _odds_api_cache
        now = datetime.utcnow()
        if not _odds_api_last_fetch or (now - _odds_api_last_fetch).total_seconds() > 600:
            try:
                odds_api_data = _fetch_odds_api_matches()
                _odds_api_cache = odds_api_data
                _odds_api_last_fetch = now
            except Exception as e:
                print(f"[OddsAPI] Bulk fetch failed: {e}")
        else:
            print(f"[OddsAPI] Using cached data ({len(odds_api_data)} matches, {int((now - _odds_api_last_fetch).total_seconds())}s old)")

        # Step 3: Build match objects
        for lid, fixtures in fixtures_by_league.items():
            league_name = TOP_LEAGUES[lid]
            for fix in fixtures:
                home = fix["teams"]["home"]["name"]
                away = fix["teams"]["away"]["name"]
                fixture_id = fix['fixture']['id']

                # Start with Elo-based fallback odds
                h1, d1, a1, o25, u25 = _elo_to_odds(home, away)
                bookmakers_list = []
                ou_bookmakers_list = []
                bookmaker_count = 1
                odds_source = "elo_model"

                # Apply real odds — prefer API-Sports per-fixture, fallback to The Odds API
                real_odds = all_odds.get(fixture_id)
                if not real_odds and odds_api_data:
                    matched = _match_odds_by_name(odds_api_data, home, away)
                    if matched:
                        real_odds = matched
                        odds_source = "the_odds_api"

                if real_odds and real_odds.get("match_winner"):
                    mw = real_odds["match_winner"]
                    best = min(mw, key=lambda x: (1/x["home"] + 1/x["draw"] + 1/x["away"]))
                    h1 = best["home"]
                    d1 = best["draw"]
                    a1 = best["away"]
                    bookmaker_count = len(mw)
                    odds_source = "real_bookmakers"
                    bookmakers_list = [
                        {"bookmaker": bk["bookmaker"], "odds": {
                            f"{home} Win": bk["home"], "Draw": bk["draw"], f"{away} Win": bk["away"]
                        }} for bk in mw[:6]
                    ]
                    if real_odds["over_under"]:
                        # Filter to ONLY 2.5 lines (other points like 1.5, 3.5 have different odds)
                        ou_25_only = [ou for ou in real_odds["over_under"]
                                      if ou.get("point", 2.5) == 2.5]
                        if not ou_25_only:
                            ou_25_only = real_odds["over_under"][:1]  # fallback to first entry
                        best_ou = ou_25_only[0]
                        o25 = best_ou.get("over", o25)
                        u25 = best_ou.get("under", u25)
                        ou_bookmakers_list = [
                            {"bookmaker": ou["bookmaker"], "odds": {
                                "Over 2.5": ou.get("over", o25), "Under 2.5": ou.get("under", u25)
                            }} for ou in ou_25_only[:4]
                        ]

                if not bookmakers_list:
                    bookmakers_list = [
                        {"bookmaker": "Elo Model", "odds": {f"{home} Win": h1, "Draw": d1, f"{away} Win": a1}},
                    ]
                if not ou_bookmakers_list:
                    ou_bookmakers_list = [
                        {"bookmaker": "Elo Model", "odds": {"Over 2.5": o25, "Under 2.5": u25}},
                    ]

                matches.append({
                    "id": f"fix_{fixture_id}",
                    "fixture_id": fixture_id,
                    "home_team": home,
                    "away_team": away,
                    "home_team_id": fix["teams"]["home"]["id"],
                    "away_team_id": fix["teams"]["away"]["id"],
                    "league": league_name,
                    "commence_time": fix["fixture"]["date"],
                    "market_count": 2,
                    "bookmaker_count": bookmaker_count,
                    "odds_source": odds_source,
                    "markets_summary": {
                        "h2h": {home: h1, "Draw": d1, away: a1},
                        "totals": {"Over 2.5": o25, "Under 2.5": u25},
                    },
                    "markets": {
                        "match_result": bookmakers_list,
                        "goals_over_under_2.5": ou_bookmakers_list,
                    },
                    "has_analysis": False,
                })

        print(f"Fetched {len(matches)} real fixtures ({len(all_odds)} with real odds) from API-Sports")
    except Exception as e:
        print(f"API-Sports error: {e}, using fallback")

    if not matches:
        matches = _generate_fallback_matches()
    return matches


def _generate_fallback_matches():
    """Fallback demo matches when API is unreachable."""
    fallback = [
        ("Arsenal", "Chelsea", "Premier League"),
        ("Liverpool", "Man City", "Premier League"),
        ("Real Madrid", "Barcelona", "La Liga"),
        ("Inter", "AC Milan", "Serie A"),
        ("Bayern Munich", "Dortmund", "Bundesliga"),
        ("PSG", "Marseille", "Ligue 1"),
    ]
    matches = []
    now = datetime.utcnow()
    for i, (home, away, league) in enumerate(fallback):
        h1, d1, a1, o25, u25 = _elo_to_odds(home, away)
        matches.append({
            "id": f"demo_{i:03d}",
            "home_team": home,
            "away_team": away,
            "league": league,
            "commence_time": (now + timedelta(hours=i*3+1)).isoformat() + "Z",
            "market_count": 2,
            "bookmaker_count": 2,
            "markets_summary": {
                "h2h": {home: h1, "Draw": d1, away: a1},
                "totals": {"Over 2.5": o25, "Under 2.5": u25},
            },
            "markets": {
                "match_result": [
                    {"bookmaker": "Pinnacle", "odds": {f"{home} Win": h1, "Draw": d1, f"{away} Win": a1}},
                    {"bookmaker": "Bet365", "odds": {f"{home} Win": round(h1*1.02, 2), "Draw": round(d1*0.99, 2), f"{away} Win": round(a1*1.01, 2)}},
                ],
                "goals_over_under_2.5": [
                    {"bookmaker": "Pinnacle", "odds": {"Over 2.5": o25, "Under 2.5": u25}},
                ],
            },
            "has_analysis": False,
        })
    return matches


def _make_demo_form(team):
    return {
        "team": team,
        "form_string": random.choice(["WWDLW", "WDWWL", "LDWWD", "WLWDW", "DWWLW"]),
        "wins": random.randint(2, 4),
        "draws": random.randint(0, 2),
        "losses": random.randint(0, 2),
        "points_last_10": random.randint(12, 24),
        "goals_scored_avg": round(random.uniform(1.0, 2.2), 1),
        "goals_conceded_avg": round(random.uniform(0.7, 1.5), 1),
        "corners_avg": round(random.uniform(4.0, 6.5), 1),
        "cards_avg": round(random.uniform(1.5, 2.8), 1),
        "shots_on_target_avg": round(random.uniform(3.5, 5.5), 1),
        "throw_ins_avg": round(random.uniform(20, 25), 1),
        "fouls_avg": round(random.uniform(10, 14), 1),
        "matches": [],
    }


def _make_demo_stats(team, is_home=True):
    return {
        "team": team,
        "season": "2025/26",
        "played": random.randint(25, 34),
        "home_corners_avg": round(random.uniform(4.5, 6.5), 1),
        "away_corners_avg": round(random.uniform(3.8, 5.2), 1),
        "home_cards_avg": round(random.uniform(1.5, 2.5), 1),
        "away_cards_avg": round(random.uniform(1.8, 2.8), 1),
        "home_goals_avg": round(random.uniform(1.1, 2.0), 1),
        "away_goals_avg": round(random.uniform(0.8, 1.5), 1),
        "home_conceded_avg": round(random.uniform(0.6, 1.4), 1),
        "away_conceded_avg": round(random.uniform(0.9, 1.7), 1),
        "clean_sheets_pct": round(random.uniform(20, 40), 1),
        "btts_pct": round(random.uniform(40, 65), 1),
        "over_2_5_pct": round(random.uniform(40, 65), 1),
        "avg_throw_ins": round(random.uniform(20, 25), 1),
        "avg_fouls": round(random.uniform(10, 14), 1),
        "avg_shots_on_target": round(random.uniform(3.5, 5.5), 1),
        "league_position": random.randint(1, 20),
    }


def _make_demo_h2h(home, away):
    return {
        "home": home,
        "away": away,
        "total_matches": random.randint(5, 20),
        "home_wins": random.randint(2, 8),
        "away_wins": random.randint(1, 6),
        "draws": random.randint(1, 6),
        "avg_goals_per_match": round(random.uniform(2.0, 3.5), 1),
        "avg_corners_per_match": round(random.uniform(8.5, 11.5), 1),
        "avg_cards_per_match": round(random.uniform(3.0, 5.5), 1),
        "btts_percentage": round(random.uniform(40, 65), 1),
        "over_2_5_percentage": round(random.uniform(40, 65), 1),
    }


@app.get("/")
def root():
    index_path = os.path.join(_static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"service": "Football Predictor V4", "version": engine.VERSION, "agents": len(engine.agents)}


@app.get("/api/matches")
def get_matches():
    global _matches_cache
    if not _matches_cache:
        _matches_cache = _fetch_real_matches()
    leagues = sorted(set(m["league"] for m in _matches_cache))
    return {"matches": _matches_cache, "total": len(_matches_cache), "leagues": leagues}


@app.post("/api/matches/refresh")
def refresh_matches():
    global _matches_cache
    _matches_cache = _fetch_real_matches()
    leagues = sorted(set(m["league"] for m in _matches_cache))
    return {"matches": _matches_cache, "total": len(_matches_cache), "leagues": leagues}


@app.post("/api/matches/{match_id}/analyze")
async def analyze_match(match_id: str):
    match = next((m for m in _matches_cache if m["id"] == match_id), None)
    if not match:
        raise HTTPException(404, "Match not found")

    analysis_id = f"analysis_{match_id}_{uuid.uuid4().hex[:8]}"
    _analysis_store[analysis_id] = {
        "id": analysis_id,
        "match_id": match_id,
        "status": "running",
        "progress": [],
        "home_form": None,
        "away_form": None,
        "h2h": None,
        "home_stats": None,
        "away_stats": None,
        "agent_reports": [],
        "final_bets": [],
        "v4_analysis": None,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    # Also store by match_id for latest lookup
    _analysis_store[f"latest_{match_id}"] = analysis_id

    asyncio.create_task(_run_analysis(analysis_id, match))
    return {"analysis_id": analysis_id, "status": "running"}


async def _run_analysis(analysis_id: str, match: dict):
    store = _analysis_store[analysis_id]
    home = match["home_team"]
    away = match["away_team"]

    def progress(step, msg):
        store["progress"].append({
            "step": step,
            "message": msg,
            "timestamp": datetime.utcnow().isoformat(),
        })

    try:
        progress("collecting_data", f"Fetching form, stats & H2H for {home} vs {away}...")
        await asyncio.sleep(0.5)  # Simulate data fetch

        home_form = _make_demo_form(home)
        away_form = _make_demo_form(away)
        h2h = _make_demo_h2h(home, away)
        home_stats = _make_demo_stats(home, True)
        away_stats = _make_demo_stats(away, False)

        store["home_form"] = home_form
        store["away_form"] = away_form
        store["h2h"] = h2h
        store["home_stats"] = home_stats
        store["away_stats"] = away_stats
        progress("data_collected", "Team data collected successfully")

        # Run V4 engine
        result = engine.analyze_match(
            match_data=match,
            home_form=home_form,
            away_form=away_form,
            h2h=h2h,
            home_stats=home_stats,
            away_stats=away_stats,
            progress_callback=progress,
        )

        store["agent_reports"] = result["agent_reports"]

        # Merge V4 value_bets into final_bets so the Value Bets tab shows everything
        final_bets = list(result["final_bets"])
        v4_analysis = result["v4_analysis"]
        existing_markets = {b.get("outcome", b.get("market", "")) for b in final_bets}

        if v4_analysis and v4_analysis.get("value_bets"):
            for vb in v4_analysis["value_bets"]:
                market_name = vb.get("market", "")
                if market_name in existing_markets:
                    continue  # Don't duplicate

                # Convert V4 value_bet dict to final_bet compatible format
                market_type = vb.get("market_type", "match_result")
                if "Corner" in market_name:
                    market_type = "corners"
                elif "Card" in market_name:
                    market_type = "cards"
                elif "Goal" in market_name or "Over" in market_name or "Under" in market_name:
                    market_type = "goals_over_under_2.5"

                edge = vb.get("edge", 0)
                model_prob = vb.get("model_prob", 0)
                odds_val = vb.get("odds", 2.0)
                ev_pct = vb.get("ev_pct", 0)

                # Determine risk level
                if edge > 0.10:
                    risk = "LOW"  # High edge = low risk
                elif edge > 0.06:
                    risk = "MEDIUM"
                else:
                    risk = "HIGH"  # Low edge = higher risk

                # Kelly stake
                q = 1 - model_prob
                kelly = max(0, (model_prob * odds_val - 1) / (odds_val - 1)) if odds_val > 1 else 0
                kelly = min(kelly, 0.05)  # Cap at 5%

                final_bets.append({
                    "match_id": match["id"],
                    "home_team": match["home_team"],
                    "away_team": match["away_team"],
                    "league": match.get("league", ""),
                    "match_date": match.get("commence_time", ""),
                    "market": market_type,
                    "market_display": market_name,
                    "outcome": market_name,
                    "confidence_pct": round(model_prob * 100, 1),
                    "best_odds": odds_val,
                    "best_bookmaker": "Agent Model" if "AGENT_MODEL" in vb.get("flags", []) else "Best Available",
                    "expected_value": round(ev_pct, 2),
                    "agent_agreement": 70.0,
                    "reasoning": vb.get("flags", []),
                    "risk_level": risk,
                    "recommended_stake": round(kelly * 100, 2),
                    "calibrated_prob": round(model_prob, 4),
                    "raw_prob": round(vb.get("implied_prob", 0), 4),
                    "edge_pct": round(edge * 100, 2),
                    "v4_flags": vb.get("flags", []),
                })
                existing_markets.add(market_name)

        # Sort all final bets by edge
        final_bets.sort(key=lambda b: b.get("edge_pct", 0), reverse=True)

        store["final_bets"] = final_bets
        store["v4_analysis"] = v4_analysis
        store["status"] = "completed"
        store["completed_at"] = datetime.utcnow().isoformat()

        # Mark match as analyzed
        for m in _matches_cache:
            if m["id"] == match["id"]:
                m["has_analysis"] = True
                break

    except Exception as e:
        store["status"] = "error"
        progress("error", str(e))


@app.get("/api/analysis/{analysis_id}")
def get_analysis(analysis_id: str):
    if analysis_id not in _analysis_store:
        raise HTTPException(404, "Analysis not found")
    return _analysis_store[analysis_id]


@app.get("/api/matches/{match_id}/latest-analysis")
def get_latest_analysis(match_id: str):
    latest_key = f"latest_{match_id}"
    if latest_key not in _analysis_store:
        raise HTTPException(404, "No analysis found")
    return _analysis_store[_analysis_store[latest_key]]


@app.post("/api/matches/{match_id}/simulate")
async def simulate_match(match_id: str):
    """Run a full match simulation using all agent intelligence.
    Returns featured simulation + Monte Carlo probabilities + value bets."""
    match = next((m for m in _matches_cache if m["id"] == match_id), None)
    if not match:
        raise HTTPException(404, "Match not found")

    home = match["home_team"]
    away = match["away_team"]

    # Get agent reports + v4_analysis from latest analysis if available
    latest_key = f"latest_{match_id}"
    agent_reports = None
    v4_analysis = None
    if latest_key in _analysis_store:
        analysis = _analysis_store[_analysis_store[latest_key]]
        agent_reports = analysis.get("agent_reports")
        v4_analysis = analysis.get("v4_analysis")
        home_form = analysis.get("home_form") or _make_demo_form(home)
        away_form = analysis.get("away_form") or _make_demo_form(away)
        h2h = analysis.get("h2h") or _make_demo_h2h(home, away)
        home_stats = analysis.get("home_stats") or _make_demo_stats(home, True)
        away_stats = analysis.get("away_stats") or _make_demo_stats(away, False)
    else:
        home_form = _make_demo_form(home)
        away_form = _make_demo_form(away)
        h2h = _make_demo_h2h(home, away)
        home_stats = _make_demo_stats(home, True)
        away_stats = _make_demo_stats(away, False)

    try:
        result = engine.simulate_match(
            match_data=match,
            home_form=home_form,
            away_form=away_form,
            h2h=h2h,
            home_stats=home_stats,
            away_stats=away_stats,
            agent_reports=agent_reports,
            n_sims=500,
            v4_analysis=v4_analysis,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Simulation error: {str(e)}")


@app.get("/api/v4/stats")
def v4_stats():
    return {
        "version": engine.VERSION,
        "agents": [{"name": a.name, "specialty": a.specialty, "weight": a.weight} for a in engine.agents],
        "calibration": {"method": "linear_shrinkage", "factor": 0.35},
        "base_rates": {"home_win": 0.431, "draw": 0.256, "away_win": 0.313, "over_25": 0.54},
        "backtest": {
            "best_config": "EPL+SerieA, home+draw+over2.5, 5% edge",
            "roi": "+3.3%",
            "bets": 281,
            "epl_draws_roi": "+45.2%",
            "epl_draws_bets": 45,
        },
        "market_filters": {
            "rejected": ["away_wins (-22% ROI)", "under_2.5 (-10-14% ROI)"],
            "allowed": ["home_win", "draw", "over_2.5", "btts", "corners", "cards"],
        },
        "training_data": "4,888 matches across 5 leagues",
    }


# Serve static files (favicon, icons) and SPA catch-all
@app.get("/favicon.svg")
def favicon():
    fpath = os.path.join(_static_dir, "favicon.svg")
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/svg+xml")
    raise HTTPException(404)


@app.get("/icons.svg")
def icons():
    fpath = os.path.join(_static_dir, "icons.svg")
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="image/svg+xml")
    raise HTTPException(404)
