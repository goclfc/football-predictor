"""
Football Predictor - Live Intelligence Agents
These agents fetch REAL data from API-Sports and The Odds API.
They require network access and API keys to function.
"""
import os
import requests
from datetime import datetime, timedelta

API_SPORTS_KEY = os.environ.get("STATS_API_KEY", "480b0d1da4cd81135649f1a77eb6465c")
API_SPORTS_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY}


class LineupAgent:
    """
    Fetches real lineup data from API-Sports:
    1. Confirmed lineups (available ~1hr before kickoff)
    2. Last-match lineups (for pre-match prediction)
    3. Squad roster + injuries to identify replacements
    """

    name = "lineup_analyst"
    specialty = "Squad composition and lineup intelligence"
    weight = 0.85
    reliability_score = 0.80

    # Position mapping from API-Sports short codes to full names
    POS_MAP = {"G": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Attacker"}

    def _fetch_squad(self, team_id):
        """Fetch full squad roster for a team."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/players/squads",
                headers=HEADERS,
                params={"team": team_id},
                timeout=8,
            )
            data = resp.json()
            squads = data.get("response", [])
            if squads:
                return squads[0].get("players", [])
        except Exception as e:
            print(f"[LineupAgent] Squad fetch error for team {team_id}: {e}")
        return []

    def _fetch_injuries(self, fixture_id):
        """Fetch injury/suspension report for a fixture."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/injuries",
                headers=HEADERS,
                params={"fixture": fixture_id},
                timeout=8,
            )
            data = resp.json()
            return data.get("response", [])
        except Exception as e:
            print(f"[LineupAgent] Injuries fetch error: {e}")
        return []

    def _fetch_lineup(self, fixture_id):
        """Fetch lineups for a fixture (confirmed or empty if not available yet)."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/fixtures/lineups",
                headers=HEADERS,
                params={"fixture": fixture_id},
                timeout=8,
            )
            data = resp.json()
            return data.get("response", [])
        except Exception as e:
            print(f"[LineupAgent] Lineup fetch error: {e}")
        return []

    def _fetch_last_match_lineup(self, team_id):
        """Fetch the lineup from a team's most recent match.
        This is the best predictor for the next match lineup."""
        try:
            # Get last match fixture ID
            resp = requests.get(
                f"{API_SPORTS_BASE}/fixtures",
                headers=HEADERS,
                params={"team": team_id, "last": 1},
                timeout=8,
            )
            data = resp.json()
            fixtures = data.get("response", [])
            if not fixtures:
                return None, None

            last_fix = fixtures[0]
            last_fix_id = last_fix["fixture"]["id"]
            opponent = last_fix["teams"]["away"]["name"] if last_fix["teams"]["home"]["id"] == team_id else last_fix["teams"]["home"]["name"]
            match_date = last_fix["fixture"]["date"][:10]

            # Fetch lineup from that match
            lineup_data = self._fetch_lineup(last_fix_id)
            for team_data in lineup_data:
                if team_data.get("team", {}).get("id") == team_id:
                    formation = team_data.get("formation", "4-3-3")
                    start_xi = []
                    for p in team_data.get("startXI", []):
                        pl = p.get("player", {})
                        pos_code = pl.get("pos", "?")
                        start_xi.append({
                            "name": pl.get("name", "?"),
                            "number": pl.get("number"),
                            "position": self.POS_MAP.get(pos_code, pos_code),
                            "grid": pl.get("grid"),  # pitch position e.g. "1:1", "2:3"
                        })
                    subs = []
                    for p in team_data.get("substitutes", []):
                        pl = p.get("player", {})
                        pos_code = pl.get("pos", "?")
                        subs.append({
                            "name": pl.get("name", "?"),
                            "number": pl.get("number"),
                            "position": self.POS_MAP.get(pos_code, pos_code),
                        })
                    info = {
                        "formation": formation,
                        "start_xi": start_xi,
                        "substitutes": subs,
                        "from_match": f"vs {opponent} ({match_date})",
                        "fixture_id": last_fix_id,
                    }
                    print(f"[LineupAgent] Got last-match lineup for team {team_id}: {formation} (vs {opponent} {match_date})")
                    return info, formation
        except Exception as e:
            print(f"[LineupAgent] Last match lineup error for team {team_id}: {e}")
        return None, None

    @staticmethod
    def _is_injured(player_name, injured_list):
        """Match player name against injury list using multiple strategies."""
        pname = player_name.lower().strip()
        for inj in injured_list:
            iname = inj["player"].lower().strip()
            if pname == iname:
                return True
            if pname in iname or iname in pname:
                return True
            p_parts = pname.replace(".", "").split()
            i_parts = iname.replace(".", "").split()
            if p_parts and i_parts:
                if len(p_parts[-1]) > 2 and p_parts[-1] == i_parts[-1]:
                    return True
                if len(i_parts) == 2 and len(i_parts[0]) <= 2 and len(p_parts) >= 2:
                    if p_parts[-1] == i_parts[-1] and p_parts[0][0] == i_parts[0][0]:
                        return True
                if len(p_parts) == 2 and len(p_parts[0]) <= 2 and len(i_parts) >= 2:
                    if i_parts[-1] == p_parts[-1] and i_parts[0][0] == p_parts[0][0]:
                        return True
        return False

    def _build_predicted_xi(self, last_lineup, injuries, squad):
        """Build predicted XI: start from last-match lineup, swap out injured players
        with replacements from the squad at the same position."""
        if not last_lineup:
            return [], "4-3-3", "no_data"

        formation = last_lineup["formation"]
        predicted_xi = []
        swaps = []

        # Build set of available squad players by position for replacements
        squad_by_pos = {}
        for p in squad:
            pos = p.get("position", "Unknown")
            squad_by_pos.setdefault(pos, []).append(p)

        # Pre-populate used_names with all non-injured starters (avoid picking them as replacements)
        used_names = set()
        for s in last_lineup["start_xi"]:
            if not self._is_injured(s["name"], injuries):
                used_names.add(s["name"].lower())

        for starter in last_lineup["start_xi"]:
            name = starter["name"]
            pos = starter["position"]

            if self._is_injured(name, injuries):
                # Find replacement: first try last-match subs, then full squad
                replacement = None

                # Try substitutes from last match first (coach's preferred backups)
                for sub in last_lineup.get("substitutes", []):
                    if sub["position"] == pos and sub["name"].lower() not in used_names:
                        if not self._is_injured(sub["name"], injuries):
                            replacement = {
                                "name": sub["name"],
                                "number": sub.get("number"),
                                "position": pos,
                                "replacing": name,
                            }
                            break

                # Then try full squad
                if not replacement:
                    for sp in squad_by_pos.get(pos, []):
                        sp_name = sp.get("name", "")
                        if sp_name.lower() not in used_names and not self._is_injured(sp_name, injuries):
                            replacement = {
                                "name": sp_name,
                                "number": sp.get("number"),
                                "position": pos,
                                "replacing": name,
                            }
                            break

                if replacement:
                    swaps.append(f"{replacement['name']} replaces {name} ({pos})")
                    predicted_xi.append(replacement)
                    used_names.add(replacement["name"].lower())
                else:
                    # No replacement found — keep them but flag as doubtful
                    predicted_xi.append({
                        "name": name,
                        "number": starter.get("number"),
                        "position": pos,
                        "status": "doubtful",
                    })
                    used_names.add(name.lower())
            else:
                predicted_xi.append({
                    "name": name,
                    "number": starter.get("number"),
                    "position": pos,
                })

        source = "last_match"
        if swaps:
            source = "last_match_adjusted"
        return predicted_xi, formation, source

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        home_team_id = match_data.get("home_team_id")
        away_team_id = match_data.get("away_team_id")
        fixture_id = match_data.get("fixture_id")

        insights = []
        home_squad = []
        away_squad = []
        home_injuries = []
        away_injuries = []
        lineup_source = "predicted"  # "confirmed" or "predicted"
        home_formation = "4-3-3"
        away_formation = "4-3-3"
        home_predicted_xi = []
        away_predicted_xi = []

        # 1) Fetch squads
        if home_team_id:
            home_squad = self._fetch_squad(home_team_id)
            insights.append(f"{home_team} squad: {len(home_squad)} registered players")
        if away_team_id:
            away_squad = self._fetch_squad(away_team_id)
            insights.append(f"{away_team} squad: {len(away_squad)} registered players")

        # 2) Fetch injuries for this fixture
        if fixture_id:
            all_injuries = self._fetch_injuries(fixture_id)
            seen = set()
            for inj in all_injuries:
                team_name = inj.get("team", {}).get("name", "")
                player_name = inj.get("player", {}).get("name", "")
                reason = inj.get("player", {}).get("reason", "Unknown")
                status = inj.get("player", {}).get("type", "Unknown")
                key = f"{team_name}_{player_name}"
                if key in seen:
                    continue
                seen.add(key)
                entry = {"player": player_name, "reason": reason, "status": status}
                if home_team in team_name or team_name in home_team:
                    home_injuries.append(entry)
                else:
                    away_injuries.append(entry)

            if home_injuries:
                missing = [f"{i['player']} ({i['reason']})" for i in home_injuries]
                insights.append(f"⚠️ {home_team} missing: {', '.join(missing)}")
            if away_injuries:
                missing = [f"{i['player']} ({i['reason']})" for i in away_injuries]
                insights.append(f"⚠️ {away_team} missing: {', '.join(missing)}")

        # 3) Try CONFIRMED lineups first (available ~1hr before kickoff)
        confirmed = False
        if fixture_id:
            confirmed_data = self._fetch_lineup(fixture_id)
            if confirmed_data:
                confirmed = True
                lineup_source = "confirmed"
                insights.append("✅ CONFIRMED lineups available!")
                for team_data in confirmed_data:
                    tid = team_data.get("team", {}).get("id")
                    formation = team_data.get("formation", "4-3-3")
                    xi = []
                    for p in team_data.get("startXI", []):
                        pl = p.get("player", {})
                        xi.append({
                            "name": pl.get("name", "?"),
                            "number": pl.get("number"),
                            "position": self.POS_MAP.get(pl.get("pos", "?"), pl.get("pos", "?")),
                        })
                    if tid == home_team_id:
                        home_predicted_xi = xi
                        home_formation = formation
                    elif tid == away_team_id:
                        away_predicted_xi = xi
                        away_formation = formation

        # 4) If no confirmed lineups, use LAST-MATCH lineups as prediction
        if not confirmed:
            lineup_source = "predicted"

            # Fetch last-match lineups
            home_last, h_form = self._fetch_last_match_lineup(home_team_id) if home_team_id else (None, None)
            away_last, a_form = self._fetch_last_match_lineup(away_team_id) if away_team_id else (None, None)

            if home_last:
                home_predicted_xi, home_formation, src = self._build_predicted_xi(
                    home_last, home_injuries, home_squad
                )
                insights.append(f"{home_team}: {home_formation} (based on {home_last['from_match']})")
            if away_last:
                away_predicted_xi, away_formation, src = self._build_predicted_xi(
                    away_last, away_injuries, away_squad
                )
                insights.append(f"{away_team}: {away_formation} (based on {away_last['from_match']})")

        # Build available/missing lists
        home_missing = []
        home_available = []
        away_missing = []
        away_available = []
        for p in home_squad:
            name = p.get("name", "")
            if self._is_injured(name, home_injuries):
                home_missing.append({"name": name, "position": p.get("position", "Unknown")})
            else:
                home_available.append({"name": name, "position": p.get("position", "Unknown"), "number": p.get("number")})
        for p in away_squad:
            name = p.get("name", "")
            if self._is_injured(name, away_injuries):
                away_missing.append({"name": name, "position": p.get("position", "Unknown")})
            else:
                away_available.append({"name": name, "position": p.get("position", "Unknown"), "number": p.get("number")})

        # Log predicted XI
        if home_predicted_xi:
            xi_names = [p["name"] for p in home_predicted_xi]
            insights.append(f"⭐ {home_team} XI: {', '.join(xi_names)}")
        if away_predicted_xi:
            xi_names = [p["name"] for p in away_predicted_xi]
            insights.append(f"⭐ {away_team} XI: {', '.join(xi_names)}")

        # Injury severity
        home_injury_impact = len([i for i in home_injuries if i["status"] == "Missing Fixture"]) * 0.03
        away_injury_impact = len([i for i in away_injuries if i["status"] == "Missing Fixture"]) * 0.03

        return {
            "agent": self.name,
            "predictions": {
                "home_squad_size": len(home_squad),
                "away_squad_size": len(away_squad),
                "home_injuries_count": len(home_injuries),
                "away_injuries_count": len(away_injuries),
                "home_available_count": len(home_available),
                "away_available_count": len(away_available),
                "home_injury_impact": round(home_injury_impact, 3),
                "away_injury_impact": round(away_injury_impact, 3),
                "lineup_confirmed": confirmed,
                "lineup_source": lineup_source,
                "home_formation": home_formation,
                "away_formation": away_formation,
                "home_squad": home_available[:25],
                "away_squad": away_available[:25],
                "home_predicted_xi": home_predicted_xi,
                "away_predicted_xi": away_predicted_xi,
                "home_injuries": home_injuries,
                "away_injuries": away_injuries,
                "home_missing": home_missing,
                "away_missing": away_missing,
            },
            "confidence": 0.95 if confirmed else (0.80 if home_predicted_xi else 0.40),
            "insights": insights,
            "adjustments": {
                "home_win_adj": away_injury_impact - home_injury_impact,
                "away_win_adj": home_injury_impact - away_injury_impact,
                "goals_adj": 0.0,
            },
        }


class PlayerNewsAgent:
    """
    Gathers the latest news, form, and context about key players
    from each team. Uses squad data + web search for breaking news.
    """

    name = "player_news_analyst"
    specialty = "Individual player news, form, and transfer rumors"
    weight = 0.65
    reliability_score = 0.60

    # No hardcoded player lists — top performers are identified from live API stats

    @staticmethod
    def _name_matches_squad(player_name, squad_names):
        """Check if a player name from stats data matches any name in the current squad.
        Handles different name formats: 'A. Griezmann' vs 'Antoine Griezmann', etc."""
        pname = player_name.lower().strip()
        for sq_name in squad_names:
            sq = sq_name.lower().strip()
            # Exact match
            if pname == sq:
                return True
            # Substring: "griezmann" in "a. griezmann"
            if pname in sq or sq in pname:
                return True
            # Surname match (last word)
            p_parts = pname.replace(".", "").split()
            s_parts = sq.replace(".", "").split()
            if p_parts and s_parts:
                # Match surname
                if len(p_parts[-1]) > 2 and p_parts[-1] == s_parts[-1]:
                    return True
                # Match "A. Griezmann" → "Antoine Griezmann" (initial + surname)
                if len(p_parts) >= 2 and len(s_parts) >= 2:
                    if p_parts[-1] == s_parts[-1] and p_parts[0][0] == s_parts[0][0]:
                        return True
        return False

    def _fetch_current_squad_names(self, team_id):
        """Fetch the current squad roster and return set of names."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/players/squads",
                headers=HEADERS,
                params={"team": team_id},
                timeout=8,
            )
            data = resp.json()
            squads = data.get("response", [])
            if squads:
                return [p["name"] for p in squads[0].get("players", [])]
        except Exception as e:
            print(f"[PlayerNewsAgent] Squad fetch error: {e}")
        return []

    def _process_team_stats(self, stats_raw, team_name, insights, current_squad_names=None):
        """Process raw API stats for a team. Returns (player_reports, top_scorers).
        Filters against current squad to exclude players who have left the club."""
        player_reports = []
        top_scorers = []

        for player_entry in stats_raw[:50]:
            player_info = player_entry.get("player", {})
            pname = player_info.get("name", "")

            # Skip players not in current squad
            if current_squad_names and not self._name_matches_squad(pname, current_squad_names):
                continue

            stats = self._get_player_season_stats(player_entry)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            appearances = stats.get("appearances", 0)

            if goals > 0 or assists > 0:
                top_scorers.append({
                    "name": pname,
                    "goals": goals,
                    "assists": assists,
                    "appearances": appearances,
                    "rating": stats.get("rating"),
                })

            # Include all predicted XI players who have any appearances
            # (previously filtered to stars only, now we show all XI players with stats)
            if appearances >= 1:
                report = {
                    "name": pname,
                    "team": team_name,
                    "stats": stats,
                    "status": "fit",
                    "news": [],
                }
                if stats.get("rating"):
                    try:
                        r = float(stats["rating"])
                        if r >= 7.5:
                            report["form"] = "excellent"
                            insights.append(f"⭐ {pname} in superb form (rating: {stats['rating']})")
                        elif r >= 7.0:
                            report["form"] = "good"
                        elif r >= 6.5:
                            report["form"] = "average"
                        else:
                            report["form"] = "poor"
                            insights.append(f"⚠️ {pname} struggling (rating: {stats['rating']})")
                    except (ValueError, TypeError):
                        report["form"] = "unknown"
                player_reports.append(report)

        top_scorers.sort(key=lambda x: x["goals"] + x["assists"], reverse=True)
        return player_reports[:10], top_scorers[:5]

    _player_cache = {}  # Class-level cache: (team_id, season) -> players

    def _fetch_player_stats_single_season(self, team_id, season):
        """Fetch player stats for one season with pagination."""
        try:
            all_players = []
            page = 1
            max_pages = 5
            while page <= max_pages:
                resp = requests.get(
                    f"{API_SPORTS_BASE}/players",
                    headers=HEADERS,
                    params={"team": team_id, "season": season, "page": page},
                    timeout=10,
                )
                data = resp.json()
                results = data.get("response", [])
                paging = data.get("paging", {})
                errors = data.get("errors", {})
                if errors:
                    print(f"[PlayerNewsAgent] API error for team {team_id} season {season}: {errors}")
                    break
                all_players.extend(results)
                total_pages = paging.get("total", 1)
                if page >= total_pages:
                    break
                page += 1
            return all_players
        except Exception as e:
            print(f"[PlayerNewsAgent] Stats fetch error (season {season}): {e}")
            return []

    def _fetch_player_stats(self, team_id, season=2024):
        """Fetch player statistics from seasons 2024 + 2025 for completeness.
        Season 2024 has the most complete data; 2025 covers recent transfers.
        Caches results to avoid redundant calls within the same session."""
        cache_key = (team_id, "merged")
        if cache_key in PlayerNewsAgent._player_cache:
            cached = PlayerNewsAgent._player_cache[cache_key]
            return cached if cached else []

        # Fetch both seasons
        players_2024 = self._fetch_player_stats_single_season(team_id, 2024)
        players_2025 = self._fetch_player_stats_single_season(team_id, 2025)

        # Merge: use 2024 as base (more complete), add any 2025-only players
        seen_ids = set()
        merged = []
        for p in players_2024:
            pid = p.get("player", {}).get("id")
            if pid:
                seen_ids.add(pid)
            if p.get("statistics") and p["statistics"][0].get("games", {}).get("appearences"):
                merged.append(p)

        # Add players from 2025 that weren't in 2024 (transfers)
        added_2025 = 0
        for p in players_2025:
            pid = p.get("player", {}).get("id")
            if pid and pid not in seen_ids:
                if p.get("statistics") and p["statistics"][0].get("games", {}).get("appearences"):
                    merged.append(p)
                    added_2025 += 1

        PlayerNewsAgent._player_cache[cache_key] = merged
        print(f"[PlayerNewsAgent] Got {len(players_2024)} (2024) + {len(players_2025)} (2025), merged {len(merged)} active for team {team_id} (+{added_2025} from 2025)")
        return merged

    def _get_player_season_stats(self, player_data):
        """Extract meaningful stats from API response."""
        stats_list = player_data.get("statistics", [])
        if not stats_list:
            return {}
        stats = stats_list[0]  # First league stats
        games = stats.get("games", {})
        goals_data = stats.get("goals", {})
        passes = stats.get("passes", {})
        cards = stats.get("cards", {})

        return {
            "appearances": games.get("appearences", 0) or 0,
            "minutes": games.get("minutes", 0) or 0,
            "rating": games.get("rating"),
            "goals": goals_data.get("total", 0) or 0,
            "assists": goals_data.get("assists", 0) or 0,
            "key_passes": passes.get("key", 0) or 0,
            "yellows": cards.get("yellow", 0) or 0,
            "reds": cards.get("red", 0) or 0,
        }

    def _extract_predicted_xi_names(self, agent_reports, team_key):
        """Extract predicted XI player names from LineupAgent's report."""
        for report in agent_reports:
            agent_name = getattr(report, 'name', '') or getattr(report, 'agent_name', '')
            # Handle both AgentReport objects and dict-style reports
            if 'lineup' in str(agent_name).lower():
                preds = getattr(report, 'predictions', [])
                for pred in preds:
                    market = getattr(pred, 'market', '') if hasattr(pred, 'market') else pred.get('market', '')
                    if market == team_key:
                        outcome = getattr(pred, 'outcome', '') if hasattr(pred, 'outcome') else pred.get('outcome', '')
                        if isinstance(outcome, str) and outcome.startswith('['):
                            try:
                                xi = eval(outcome)
                                return [p.get('name', '') for p in xi if isinstance(p, dict)]
                            except:
                                pass
                        elif isinstance(outcome, list):
                            return [p.get('name', '') for p in outcome if isinstance(p, dict)]
        return []

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        home_team_id = match_data.get("home_team_id")
        away_team_id = match_data.get("away_team_id")

        insights = []
        home_player_reports = []
        away_player_reports = []

        # Get predicted XI names from LineupAgent (runs before us)
        prev_reports = kwargs.get("agent_reports", [])
        home_xi_names = self._extract_predicted_xi_names(prev_reports, "home_predicted_xi")
        away_xi_names = self._extract_predicted_xi_names(prev_reports, "away_predicted_xi")

        # Fall back to full squad if no predicted XI available
        if not home_xi_names:
            home_xi_names = self._fetch_current_squad_names(home_team_id) if home_team_id else []
        if not away_xi_names:
            away_xi_names = self._fetch_current_squad_names(away_team_id) if away_team_id else []
        print(f"[PlayerNewsAgent] Filtering to: {home_team}={len(home_xi_names)} players, {away_team}={len(away_xi_names)} players")

        # Fetch season stats (2024 — most complete data)
        home_stats_raw = []
        away_stats_raw = []
        if home_team_id:
            home_stats_raw = self._fetch_player_stats(home_team_id)
        if away_team_id:
            away_stats_raw = self._fetch_player_stats(away_team_id)

        # Process stats — filtered to predicted XI only
        home_top_scorers = []
        away_top_scorers = []

        home_player_reports, home_top_scorers = self._process_team_stats(
            home_stats_raw, home_team, insights, home_xi_names
        )
        away_player_reports, away_top_scorers = self._process_team_stats(
            away_stats_raw, away_team, insights, away_xi_names
        )

        # Sort top scorers
        home_top_scorers.sort(key=lambda x: x["goals"] + x["assists"], reverse=True)
        away_top_scorers.sort(key=lambda x: x["goals"] + x["assists"], reverse=True)

        # Generate insights from top scorers
        if home_top_scorers:
            top = home_top_scorers[0]
            insights.append(f"{home_team} top scorer: {top['name']} ({top['goals']}G, {top['assists']}A in {top['appearances']} apps)")
        if away_top_scorers:
            top = away_top_scorers[0]
            insights.append(f"{away_team} top scorer: {top['name']} ({top['goals']}G, {top['assists']}A in {top['appearances']} apps)")

        # Goal threat comparison
        home_total_goals = sum(p["goals"] for p in home_top_scorers[:5])
        away_total_goals = sum(p["goals"] for p in away_top_scorers[:5])
        if home_total_goals > 0 or away_total_goals > 0:
            insights.append(f"Top-5 scorers combined: {home_team} {home_total_goals}G vs {away_team} {away_total_goals}G")

        # Card-prone players (filtered to current squad)
        for player_entry in home_stats_raw[:50]:
            pinfo = player_entry.get("player", {})
            pname = pinfo.get("name", "")
            if home_xi_names and not self._name_matches_squad(pname, home_xi_names):
                continue
            stats = self._get_player_season_stats(player_entry)
            if stats.get("yellows", 0) >= 5:
                insights.append(f"🟨 {pname} ({home_team}) card-prone: {stats['yellows']} yellows this season")

        for player_entry in away_stats_raw[:50]:
            pinfo = player_entry.get("player", {})
            pname = pinfo.get("name", "")
            if away_xi_names and not self._name_matches_squad(pname, away_xi_names):
                continue
            stats = self._get_player_season_stats(player_entry)
            if stats.get("yellows", 0) >= 5:
                insights.append(f"🟨 {pname} ({away_team}) card-prone: {stats['yellows']} yellows this season")

        # Compute adjustments based on firepower
        goal_diff = home_total_goals - away_total_goals
        home_adj = max(-0.05, min(0.05, goal_diff * 0.005))

        return {
            "agent": self.name,
            "predictions": {
                "home_player_reports": home_player_reports[:10],
                "away_player_reports": away_player_reports[:10],
                "home_top_scorers": home_top_scorers[:5],
                "away_top_scorers": away_top_scorers[:5],
                "home_total_goals_top5": home_total_goals,
                "away_total_goals_top5": away_total_goals,
                "home_players_fetched": len(home_stats_raw),
                "away_players_fetched": len(away_stats_raw),
            },
            "confidence": 0.75 if home_stats_raw and away_stats_raw else 0.35,
            "insights": insights,
            "adjustments": {
                "home_win_adj": round(home_adj, 4),
                "away_win_adj": round(-home_adj, 4),
                "goals_adj": 0.0,
            },
        }


# ============================================================================
# Odds API configuration
# ============================================================================
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "804de796839c681ca327aa0983abbb7b")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Map API-Sports league IDs to Odds API sport keys (including cups)
LEAGUE_TO_ODDS_SPORT = {
    39: "soccer_epl",
    140: "soccer_spain_la_liga",
    135: "soccer_italy_serie_a",
    78: "soccer_germany_bundesliga",
    61: "soccer_france_ligue_one",
    2: "soccer_uefa_champs_league",
    3: "soccer_uefa_europa_league",
    848: "soccer_uefa_europa_conference_league",
}


class ScheduleContextAgent:
    """
    Analyzes upcoming schedule context for both teams.
    Fetches upcoming fixtures from API-Sports to determine:
    - What's the next match after this one (CL? Cup? Relegation battle?)
    - Will the manager rotate? (big CL match in 3 days)
    - Are the teams meeting again soon? (e.g., CL QF rematch)
    - Fixture congestion and rest days
    - Competition priority (what matters more — league or CL?)
    """

    name = "schedule_context_agent"
    specialty = "Upcoming schedule, rotation risk, and multi-competition context"
    weight = 0.70
    reliability_score = 0.75

    # Competition priority tiers (higher = more prestigious)
    COMP_PRIORITY = {
        "UEFA Champions League": 10,
        "UEFA Europa League": 8,
        "UEFA Europa Conference League": 7,
        "Copa del Rey": 6,
        "FA Cup": 6,
        "DFB Pokal": 6,
        "Coppa Italia": 6,
        "Coupe de France": 6,
        "La Liga": 5,
        "Premier League": 5,
        "Serie A": 5,
        "Bundesliga": 5,
        "Ligue 1": 5,
    }

    KNOCKOUT_ROUNDS = {"Quarter-finals", "Semi-finals", "Final", "Round of 16", "Play-offs"}

    def _fetch_upcoming(self, team_id, count=7):
        """Fetch next N fixtures for a team across ALL competitions."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/fixtures",
                headers=HEADERS,
                params={"team": team_id, "next": count},
                timeout=10,
            )
            return resp.json().get("response", [])
        except Exception as e:
            print(f"[ScheduleContext] Upcoming fetch error for team {team_id}: {e}")
            return []

    def _fetch_last_results(self, team_id, count=5):
        """Fetch last N results for a team across ALL competitions."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/fixtures",
                headers=HEADERS,
                params={"team": team_id, "last": count},
                timeout=10,
            )
            return resp.json().get("response", [])
        except Exception as e:
            print(f"[ScheduleContext] Last results error for team {team_id}: {e}")
            return []

    def _fetch_h2h(self, team1_id, team2_id, last=10):
        """Fetch head-to-head across ALL competitions."""
        try:
            resp = requests.get(
                f"{API_SPORTS_BASE}/fixtures/headtohead",
                headers=HEADERS,
                params={"h2h": f"{team1_id}-{team2_id}", "last": last},
                timeout=10,
            )
            return resp.json().get("response", [])
        except Exception as e:
            print(f"[ScheduleContext] H2H fetch error: {e}")
            return []

    def _parse_fixture(self, f, team_id):
        """Parse a fixture response into a clean dict."""
        fix = f.get("fixture", {})
        league = f.get("league", {})
        teams = f.get("teams", {})
        goals = f.get("goals", {})

        home_team = teams.get("home", {})
        away_team = teams.get("away", {})
        is_home = home_team.get("id") == team_id

        opponent = away_team if is_home else home_team
        date_str = fix.get("date", "")

        try:
            match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            match_date = None

        # Determine result if played
        result = None
        if goals.get("home") is not None and goals.get("away") is not None:
            my_goals = goals["home"] if is_home else goals["away"]
            opp_goals = goals["away"] if is_home else goals["home"]
            if my_goals > opp_goals:
                result = "W"
            elif my_goals < opp_goals:
                result = "L"
            else:
                result = "D"

        return {
            "date": date_str[:10],
            "datetime": match_date,
            "competition": league.get("name", "Unknown"),
            "round": league.get("round", ""),
            "opponent": opponent.get("name", "Unknown"),
            "opponent_id": opponent.get("id"),
            "is_home": is_home,
            "score": f"{goals.get('home', '?')}-{goals.get('away', '?')}" if goals.get("home") is not None else None,
            "result": result,
            "fixture_id": fix.get("id"),
        }

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        home_id = match_data.get("home_team_id")
        away_id = match_data.get("away_team_id")

        insights = []
        predictions = {}

        # === 1. Fetch upcoming fixtures for both teams ===
        home_upcoming = []
        away_upcoming = []
        home_recent = []
        away_recent = []

        if home_id:
            raw_upcoming = self._fetch_upcoming(home_id, 7)
            home_upcoming = [self._parse_fixture(f, home_id) for f in raw_upcoming]
            raw_recent = self._fetch_last_results(home_id, 5)
            home_recent = [self._parse_fixture(f, home_id) for f in raw_recent]

        if away_id:
            raw_upcoming = self._fetch_upcoming(away_id, 7)
            away_upcoming = [self._parse_fixture(f, away_id) for f in raw_upcoming]
            raw_recent = self._fetch_last_results(away_id, 5)
            away_recent = [self._parse_fixture(f, away_id) for f in raw_recent]

        # === 2. Recent form across all competitions ===
        home_form_str = "".join([m["result"] for m in home_recent if m["result"]]) or "?????"
        away_form_str = "".join([m["result"] for m in away_recent if m["result"]]) or "?????"
        predictions["home_recent_form_all_comps"] = home_form_str
        predictions["away_recent_form_all_comps"] = away_form_str

        # Recent results detail
        home_recent_detail = [
            f"{m['result']} {m['score']} vs {m['opponent']} ({m['competition']})"
            for m in home_recent if m["result"]
        ]
        away_recent_detail = [
            f"{m['result']} {m['score']} vs {m['opponent']} ({m['competition']})"
            for m in away_recent if m["result"]
        ]
        predictions["home_recent_results"] = home_recent_detail
        predictions["away_recent_results"] = away_recent_detail

        insights.append(f"{home_team} recent form (all comps): {home_form_str}")
        insights.append(f"{away_team} recent form (all comps): {away_form_str}")

        # === 3. Upcoming schedule analysis ===
        # Skip the current match (first upcoming) and look at what's NEXT
        home_next = [m for m in home_upcoming[1:] if m["datetime"]]
        away_next = [m for m in away_upcoming[1:] if m["datetime"]]

        home_next_match = home_next[0] if home_next else None
        away_next_match = away_next[0] if away_next else None

        if home_next_match:
            predictions["home_next_match"] = f"{home_next_match['competition']}: vs {home_next_match['opponent']} ({home_next_match['date']})"
            predictions["home_next_competition"] = home_next_match["competition"]
            predictions["home_next_is_home"] = home_next_match["is_home"]

            # Days until next match
            now = datetime.now(home_next_match["datetime"].tzinfo) if home_next_match["datetime"].tzinfo else datetime.now()
            days_to_next = (home_next_match["datetime"] - now).days
            predictions["home_days_to_next"] = max(0, days_to_next)

            insights.append(f"{home_team} next: {home_next_match['competition']} vs {home_next_match['opponent']} in {days_to_next} days")

        if away_next_match:
            predictions["away_next_match"] = f"{away_next_match['competition']}: vs {away_next_match['opponent']} ({away_next_match['date']})"
            predictions["away_next_competition"] = away_next_match["competition"]
            predictions["away_next_is_home"] = away_next_match["is_home"]

            now = datetime.now(away_next_match["datetime"].tzinfo) if away_next_match["datetime"].tzinfo else datetime.now()
            days_to_next = (away_next_match["datetime"] - now).days
            predictions["away_days_to_next"] = max(0, days_to_next)

            insights.append(f"{away_team} next: {away_next_match['competition']} vs {away_next_match['opponent']} in {days_to_next} days")

        # === 4. Rotation risk ===
        home_rotation_risk = 0.0
        away_rotation_risk = 0.0

        for side, next_match, team_name, risk_key in [
            ("home", home_next_match, home_team, "home_rotation_risk"),
            ("away", away_next_match, away_team, "away_rotation_risk")
        ]:
            if next_match:
                comp = next_match["competition"]
                comp_priority = self.COMP_PRIORITY.get(comp, 5)
                current_comp_priority = self.COMP_PRIORITY.get(match_data.get("league", ""), 5)
                days = predictions.get(f"{side}_days_to_next", 7)
                rnd = next_match.get("round", "")

                risk = 0.0

                # Higher priority next match = higher rotation risk NOW
                if comp_priority > current_comp_priority:
                    risk += 0.25
                    insights.append(f"⚠️ {team_name} has {comp} ({rnd}) next — may rotate")

                # CL knockout round coming = VERY high rotation
                if any(kr in rnd for kr in self.KNOCKOUT_ROUNDS) and "Champions" in comp:
                    risk += 0.30
                    insights.append(f"🏆 {team_name}: CL knockout {rnd} coming — high rotation risk")

                # Tight schedule (< 4 days)
                if days <= 3:
                    risk += 0.20
                    insights.append(f"⏰ {team_name}: only {days} days until next match")

                # Cup final coming
                if "Final" in rnd:
                    risk += 0.35
                    insights.append(f"🏆 {team_name} has a cup FINAL coming — likely to protect key players")

                predictions[risk_key] = round(min(0.9, risk), 2)

        # === 5. Rematch detection ===
        # Are these teams meeting again soon in another competition?
        rematch = None
        for m in home_upcoming[1:]:
            if m.get("opponent_id") in (home_id, away_id) and m.get("opponent") in (home_team, away_team):
                rematch = m
                break

        if rematch:
            predictions["rematch_detected"] = True
            predictions["rematch_competition"] = rematch["competition"]
            predictions["rematch_date"] = rematch["date"]
            predictions["rematch_round"] = rematch.get("round", "")
            insights.append(f"🔄 REMATCH: {home_team} vs {away_team} again in {rematch['competition']} ({rematch.get('round','')}) on {rematch['date']}")

            # If CL rematch, both teams might be tactical about this league game
            if "Champions" in rematch["competition"]:
                insights.append(f"♟️ Tactical implications: CL {rematch.get('round','')} rematch may affect team selection today")

        # === 6. Full H2H across all competitions ===
        h2h_all = []
        if home_id and away_id:
            raw_h2h = self._fetch_h2h(home_id, away_id, 10)
            for f in raw_h2h:
                parsed = self._parse_fixture(f, home_id)
                h2h_all.append(parsed)

        if h2h_all:
            h2h_detail = [
                f"{m['date']} | {m['competition']} | {m['score']} ({'H' if m['is_home'] else 'A'}) = {m['result']}"
                for m in h2h_all
            ]
            predictions["h2h_all_competitions"] = h2h_detail
            predictions["h2h_total_matches"] = len(h2h_all)

            # H2H record
            home_wins = sum(1 for m in h2h_all if m["result"] == "W")
            draws = sum(1 for m in h2h_all if m["result"] == "D")
            away_wins = sum(1 for m in h2h_all if m["result"] == "L")
            predictions["h2h_record"] = f"{home_team} {home_wins}W {draws}D {away_wins}L"

            insights.append(f"H2H all comps (last {len(h2h_all)}): {home_team} {home_wins}W-{draws}D-{away_wins}L")

            # Goals pattern
            total_goals = 0
            for m in h2h_all:
                if m["score"] and "-" in m["score"]:
                    try:
                        parts = m["score"].split("-")
                        total_goals += int(parts[0]) + int(parts[1])
                    except:
                        pass
            avg_goals = total_goals / len(h2h_all) if h2h_all else 0
            predictions["h2h_avg_goals"] = round(avg_goals, 1)
            insights.append(f"H2H avg goals: {avg_goals:.1f} per match")

        # === 7. Upcoming schedule list (for frontend display) ===
        predictions["home_schedule"] = [
            f"{m['date']} | {m['competition']} | vs {m['opponent']} ({'H' if m['is_home'] else 'A'})"
            for m in home_upcoming[:7]
        ]
        predictions["away_schedule"] = [
            f"{m['date']} | {m['competition']} | vs {m['opponent']} ({'H' if m['is_home'] else 'A'})"
            for m in away_upcoming[:7]
        ]

        # === 8. Compute adjustments ===
        home_rot = predictions.get("home_rotation_risk", 0)
        away_rot = predictions.get("away_rotation_risk", 0)

        # Rotation risk weakens the team that rotates
        home_adj = -home_rot * 0.08
        away_adj = -away_rot * 0.08

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": 0.75,
            "insights": insights,
            "adjustments": {
                "home_win_adj": round(home_adj, 4),
                "away_win_adj": round(away_adj, 4),
                "goals_adj": 0.0,
            },
        }


class HistoricalOddsAgent:
    """
    Analyzes historical odds data from The Odds API to find patterns:
    - How bookmakers priced past H2H matchups
    - Odds movement patterns for similar fixtures
    - Value detection by comparing current odds to historical H2H odds
    - Cross-competition odds (CL, league, cup) for the same matchup
    """

    name = "historical_odds_agent"
    specialty = "Historical odds patterns, H2H odds history, and value detection"
    weight = 0.70
    reliability_score = 0.75

    # Cache to avoid re-fetching
    _odds_cache = {}

    def _fetch_historical_odds(self, sport_key, date_iso, markets="h2h"):
        """Fetch historical odds for a specific date and sport."""
        cache_key = (sport_key, date_iso)
        if cache_key in HistoricalOddsAgent._odds_cache:
            return HistoricalOddsAgent._odds_cache[cache_key]

        try:
            resp = requests.get(
                f"{ODDS_API_BASE}/historical/sports/{sport_key}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "date": date_iso,
                    "regions": "eu",
                    "markets": markets,
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )
            data = resp.json()
            events = data.get("data", [])
            HistoricalOddsAgent._odds_cache[cache_key] = events
            return events
        except Exception as e:
            print(f"[HistoricalOdds] Fetch error for {sport_key} {date_iso}: {e}")
            return []

    def _fetch_current_odds(self, sport_key, markets="h2h"):
        """Fetch current live odds for a sport."""
        try:
            resp = requests.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "eu",
                    "markets": markets,
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[HistoricalOdds] Current odds error: {e}")
            return []

    def _extract_odds_from_event(self, event):
        """Extract average h2h odds from an event's bookmakers."""
        home_odds = []
        away_odds = []
        draw_odds = []
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")

        for bm in event.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for outcome in mkt.get("outcomes", []):
                        name = outcome.get("name", "")
                        price = outcome.get("price", 0)
                        if name == home_team:
                            home_odds.append(price)
                        elif name == away_team:
                            away_odds.append(price)
                        elif name == "Draw":
                            draw_odds.append(price)

        avg_h = sum(home_odds) / len(home_odds) if home_odds else None
        avg_a = sum(away_odds) / len(away_odds) if away_odds else None
        avg_d = sum(draw_odds) / len(draw_odds) if draw_odds else None

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_odds": round(avg_h, 2) if avg_h else None,
            "away_odds": round(avg_a, 2) if avg_a else None,
            "draw_odds": round(avg_d, 2) if avg_d else None,
            "bookmaker_count": len(event.get("bookmakers", [])),
        }

    def _fuzzy_team_match(self, name1, name2):
        """Check if two team names refer to the same team."""
        n1 = name1.lower().replace("fc ", "").replace(" fc", "").strip()
        n2 = name2.lower().replace("fc ", "").replace(" fc", "").strip()
        if n1 == n2:
            return True
        # Substring match
        if len(n1) > 4 and len(n2) > 4:
            if n1 in n2 or n2 in n1:
                return True
        # Common mappings
        mappings = {
            "atlético madrid": "atletico madrid",
            "atlético": "atletico madrid",
            "paris saint germain": "paris saint-germain",
            "psg": "paris saint-germain",
            "inter milan": "inter",
            "internazionale": "inter",
        }
        m1 = mappings.get(n1, n1)
        m2 = mappings.get(n2, n2)
        if m1 == m2:
            return True
        if m1 in m2 or m2 in m1:
            return True
        return False

    def analyze(self, match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs):
        home_team = match_data.get("home_team", "")
        away_team = match_data.get("away_team", "")
        league = match_data.get("league", "")

        insights = []
        predictions = {}

        # === 1. Get current odds for this match ===
        current_odds = match_data.get("odds", {})
        current_h = current_odds.get("home")
        current_d = current_odds.get("draw")
        current_a = current_odds.get("away")

        if current_h:
            predictions["current_odds_home"] = current_h
            predictions["current_odds_draw"] = current_d
            predictions["current_odds_away"] = current_a
            # Implied probabilities
            total = (1/current_h + 1/current_d + 1/current_a) if current_h and current_d and current_a else 1
            predictions["implied_prob_home"] = round((1/current_h) / total, 3) if current_h else None
            predictions["implied_prob_draw"] = round((1/current_d) / total, 3) if current_d else None
            predictions["implied_prob_away"] = round((1/current_a) / total, 3) if current_a else None

        # === 2. Get H2H historical results with dates for odds lookup ===
        # Use previous agent reports to get H2H dates
        prev_reports = kwargs.get("agent_reports", [])
        h2h_dates = []
        for rpt in prev_reports:
            agent_name = getattr(rpt, "agent_name", "") or getattr(rpt, "name", "")
            if "schedule" in str(agent_name).lower():
                preds = getattr(rpt, "predictions", [])
                if isinstance(preds, list):
                    for pred in preds:
                        market = getattr(pred, "market", "") if hasattr(pred, "market") else pred.get("market", "")
                        if market == "h2h_all_competitions":
                            outcome = getattr(pred, "outcome", "") if hasattr(pred, "outcome") else pred.get("outcome", "")
                            # Parse the h2h dates
                            if isinstance(outcome, str) and outcome.startswith("["):
                                try:
                                    items = eval(outcome)
                                    for item in items:
                                        if isinstance(item, str) and "|" in item:
                                            date_part = item.split("|")[0].strip()
                                            comp_part = item.split("|")[1].strip() if len(item.split("|")) > 1 else ""
                                            h2h_dates.append({"date": date_part, "competition": comp_part})
                                except:
                                    pass

        # === 3. Fetch historical odds for past H2H matches ===
        h2h_odds_history = []
        # Look up past matches by fetching historical odds around known H2H dates
        # Use the league sport key + CL sport key
        sport_keys = set()
        # Determine sport keys to search
        for lid, skey in LEAGUE_TO_ODDS_SPORT.items():
            if league and any(ln in league for ln in ["Liga", "Premier", "Serie", "Bundes", "Ligue"]):
                # Find the right one
                pass
            sport_keys.add(skey)

        # Simpler approach: search league + CL for the team matchup
        league_sport_key = None
        for lid, skey in LEAGUE_TO_ODDS_SPORT.items():
            if lid == match_data.get("league_id"):
                league_sport_key = skey
                break
        # Fallback: guess from league name
        if not league_sport_key:
            name_map = {
                "La Liga": "soccer_spain_la_liga",
                "Premier League": "soccer_epl",
                "Serie A": "soccer_italy_serie_a",
                "Bundesliga": "soccer_germany_bundesliga",
                "Ligue 1": "soccer_france_ligue_one",
            }
            for ln, sk in name_map.items():
                if ln.lower() in league.lower():
                    league_sport_key = sk
                    break

        search_sport_keys = []
        if league_sport_key:
            search_sport_keys.append(league_sport_key)
        search_sport_keys.append("soccer_uefa_champs_league")

        # Fetch historical odds for known H2H dates
        if h2h_dates:
            for h2h_entry in h2h_dates[:5]:  # Max 5 lookups to conserve API calls
                date_str = h2h_entry["date"]
                comp = h2h_entry.get("competition", "")
                try:
                    match_date = datetime.strptime(date_str, "%Y-%m-%d")
                    date_iso = match_date.strftime("%Y-%m-%dT12:00:00Z")
                except:
                    continue

                # Choose sport key based on competition
                if "Champions" in comp:
                    sk = "soccer_uefa_champs_league"
                elif "Europa" in comp:
                    sk = "soccer_uefa_europa_league"
                elif league_sport_key:
                    sk = league_sport_key
                else:
                    continue

                events = self._fetch_historical_odds(sk, date_iso)
                for ev in events:
                    if (self._fuzzy_team_match(ev.get("home_team", ""), home_team) and
                        self._fuzzy_team_match(ev.get("away_team", ""), away_team)) or \
                       (self._fuzzy_team_match(ev.get("home_team", ""), away_team) and
                        self._fuzzy_team_match(ev.get("away_team", ""), home_team)):

                        odds_data = self._extract_odds_from_event(ev)
                        odds_data["date"] = date_str
                        odds_data["competition"] = comp
                        h2h_odds_history.append(odds_data)
                        break

        predictions["h2h_odds_history"] = h2h_odds_history

        if h2h_odds_history:
            insights.append(f"Found historical odds for {len(h2h_odds_history)} past H2H matches")

            # Show odds comparison
            for hist in h2h_odds_history[:3]:
                ho = hist.get("home_odds", "?")
                do = hist.get("draw_odds", "?")
                ao = hist.get("away_odds", "?")
                insights.append(
                    f"  {hist['date']} ({hist.get('competition','')}) — "
                    f"{hist['home_team']}: {ho} | Draw: {do} | {hist['away_team']}: {ao}"
                )

        # === 4. Get CL/EL odds if applicable ===
        # Check if there's an upcoming CL match between these teams
        cl_odds = None
        cl_events = self._fetch_current_odds("soccer_uefa_champs_league")
        for ev in cl_events:
            if (self._fuzzy_team_match(ev.get("home_team", ""), home_team) or
                self._fuzzy_team_match(ev.get("home_team", ""), away_team)) and \
               (self._fuzzy_team_match(ev.get("away_team", ""), home_team) or
                self._fuzzy_team_match(ev.get("away_team", ""), away_team)):

                cl_odds = self._extract_odds_from_event(ev)
                cl_odds["commence_time"] = ev.get("commence_time", "")
                break

        if cl_odds:
            predictions["cl_match_odds"] = cl_odds
            insights.append(
                f"🏆 CL match odds: {cl_odds['home_team']} {cl_odds.get('home_odds','?')} | "
                f"Draw {cl_odds.get('draw_odds','?')} | {cl_odds['away_team']} {cl_odds.get('away_odds','?')}"
            )

        # === 5. Value analysis: compare current odds to historical pattern ===
        if h2h_odds_history and current_h:
            # What were the average historical odds for the home team?
            hist_home_odds = []
            hist_away_odds = []
            for hist in h2h_odds_history:
                if self._fuzzy_team_match(hist.get("home_team", ""), home_team):
                    if hist.get("home_odds"):
                        hist_home_odds.append(hist["home_odds"])
                elif self._fuzzy_team_match(hist.get("away_team", ""), home_team):
                    if hist.get("away_odds"):
                        hist_home_odds.append(hist["away_odds"])

                if self._fuzzy_team_match(hist.get("home_team", ""), away_team):
                    if hist.get("home_odds"):
                        hist_away_odds.append(hist["home_odds"])
                elif self._fuzzy_team_match(hist.get("away_team", ""), away_team):
                    if hist.get("away_odds"):
                        hist_away_odds.append(hist["away_odds"])

            if hist_home_odds:
                avg_hist_home = sum(hist_home_odds) / len(hist_home_odds)
                predictions["historical_avg_odds_home"] = round(avg_hist_home, 2)
                odds_shift = current_h - avg_hist_home
                predictions["odds_shift_home"] = round(odds_shift, 2)
                if abs(odds_shift) > 0.3:
                    direction = "drifted (less favored)" if odds_shift > 0 else "shortened (more favored)"
                    insights.append(f"📊 {home_team} odds {direction}: now {current_h} vs historical avg {avg_hist_home:.2f}")

            if hist_away_odds:
                avg_hist_away = sum(hist_away_odds) / len(hist_away_odds)
                predictions["historical_avg_odds_away"] = round(avg_hist_away, 2)
                odds_shift = current_a - avg_hist_away if current_a else 0
                predictions["odds_shift_away"] = round(odds_shift, 2)
                if abs(odds_shift) > 0.3:
                    direction = "drifted (less favored)" if odds_shift > 0 else "shortened (more favored)"
                    insights.append(f"📊 {away_team} odds {direction}: now {current_a} vs historical avg {avg_hist_away:.2f}")

        # === 6. Goals market pattern from H2H history ===
        if h2h_odds_history:
            # Average implied totals from historical matches
            home_probs = []
            for hist in h2h_odds_history:
                ho = hist.get("home_odds")
                ao = hist.get("away_odds")
                do = hist.get("draw_odds")
                if ho and ao and do:
                    home_probs.append(1/ho)
            if home_probs:
                predictions["h2h_avg_home_implied_prob"] = round(sum(home_probs)/len(home_probs), 3)

        # Adjustments
        home_adj = 0.0
        away_adj = 0.0
        if "odds_shift_home" in predictions:
            # If home team odds shortened (negative shift), slight boost
            shift = predictions["odds_shift_home"]
            home_adj = max(-0.03, min(0.03, -shift * 0.01))
        if "odds_shift_away" in predictions:
            shift = predictions["odds_shift_away"]
            away_adj = max(-0.03, min(0.03, -shift * 0.01))

        return {
            "agent": self.name,
            "predictions": predictions,
            "confidence": 0.70 if h2h_odds_history else 0.50,
            "insights": insights,
            "adjustments": {
                "home_win_adj": round(home_adj, 4),
                "away_win_adj": round(away_adj, 4),
                "goals_adj": 0.0,
            },
        }
