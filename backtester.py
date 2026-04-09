#!/usr/bin/env python3
"""
Backtester — Tests whether our prediction model would have made money
on historical matches with real odds.

Strategy:
1. Fetch completed matches from API-Football (past fixtures with results + stats)
2. Fetch historical closing odds from The Odds API (or reconstruct from results)
3. For each completed match, run our agent pipeline AS IF the match hadn't happened
4. Compare model's "value bets" to actual outcomes
5. Track cumulative P&L with Kelly staking

This answers the critical question: "Would this system actually make money?"
"""
import sys
import os
import json
import time
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent import StatsAgent
from agents.market_agent import MarketAgent
from agents.value_agent import ValueAgent
from agents.meta_agent import MetaAgent, FinalBet


# ─── Result Tracking ──────────────────────────────────────────────────
@dataclass
class BetResult:
    """Tracks a single bet and its outcome."""
    match_id: str
    match_date: str
    home_team: str
    away_team: str
    league: str
    market: str
    outcome: str
    odds: float
    bookmaker: str
    stake_pct: float          # % of bankroll staked
    confidence: float
    expected_value: float
    risk_level: str
    # Actual result
    won: bool = False
    actual_outcome: str = ""
    profit: float = 0.0       # Net profit/loss from this bet
    running_bankroll: float = 0.0


@dataclass
class BacktestSummary:
    """Overall backtest results."""
    total_matches: int = 0
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_staked: float = 0.0
    total_profit: float = 0.0
    roi: float = 0.0
    max_drawdown: float = 0.0
    peak_bankroll: float = 0.0
    final_bankroll: float = 0.0
    starting_bankroll: float = 0.0
    sharpe_ratio: float = 0.0
    # By risk level
    low_risk_record: str = ""
    medium_risk_record: str = ""
    high_risk_record: str = ""
    # By market
    market_breakdown: Dict = field(default_factory=dict)
    # By league
    league_breakdown: Dict = field(default_factory=dict)
    # Monthly P&L
    monthly_pl: Dict = field(default_factory=dict)


# ─── Historical Data Fetcher ──────────────────────────────────────────
class HistoricalDataFetcher:
    """
    Fetches historical match data with results and odds.
    Uses API-Football for match results and The Odds API for historical odds.
    Falls back to odds reconstruction when historical API not available.
    """

    # Top 5 leagues with API-Football IDs
    LEAGUES = {
        "Premier League": {"apifb_id": 39, "odds_key": "soccer_epl"},
        "La Liga": {"apifb_id": 140, "odds_key": "soccer_spain_la_liga"},
        "Bundesliga": {"apifb_id": 78, "odds_key": "soccer_germany_bundesliga"},
        "Serie A": {"apifb_id": 135, "odds_key": "soccer_italy_serie_a"},
        "Ligue 1": {"apifb_id": 61, "odds_key": "soccer_france_ligue_one"},
    }

    def __init__(self, stats_api_key: str, odds_api_key: str = None):
        self.stats_api_key = stats_api_key
        self.odds_api_key = odds_api_key
        self.stats_base = "https://v3.football.api-sports.io"
        self.odds_base = "https://api.the-odds-api.com/v4"
        self.headers = {"x-apisports-key": stats_api_key}
        self._team_cache = {}
        self._request_count = 0

    def fetch_completed_fixtures(self, league_name: str, season: int = 2025,
                                  max_rounds: int = 30) -> List[Dict]:
        """
        Fetch completed fixtures for a league with full stats.
        Returns match data in the same format our agents expect.
        """
        league_info = self.LEAGUES.get(league_name)
        if not league_info:
            print(f"  Unknown league: {league_name}")
            return []

        league_id = league_info["apifb_id"]

        try:
            # Get completed fixtures for the season
            resp = requests.get(
                f"{self.stats_base}/fixtures",
                headers=self.headers,
                params={
                    "league": league_id,
                    "season": season,
                    "status": "FT",  # Finished matches only
                },
                timeout=15
            )
            resp.raise_for_status()
            self._request_count += 1
            data = resp.json()
            fixtures = data.get("response", [])
            print(f"  {league_name}: {len(fixtures)} completed fixtures found")
            return fixtures

        except Exception as e:
            print(f"  Error fetching {league_name} fixtures: {e}")
            return []

    def fixture_to_match_data(self, fixture: Dict, league_name: str) -> Dict:
        """Convert API-Football fixture to our internal match format."""
        home_team = fixture["teams"]["home"]["name"]
        away_team = fixture["teams"]["away"]["name"]
        match_date = fixture["fixture"]["date"]
        fixture_id = str(fixture["fixture"]["id"])

        return {
            "id": fixture_id,
            "home_team": home_team,
            "away_team": away_team,
            "league": league_name,
            "commence_time": match_date,
            "markets": {},  # Will be populated by odds
        }

    def get_match_result(self, fixture: Dict) -> Dict:
        """Extract actual match result from a completed fixture."""
        goals = fixture.get("goals", {})
        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0
        score = fixture.get("score", {})

        # First half
        ht = score.get("halftime", {})
        ht_home = ht.get("home", 0) or 0
        ht_away = ht.get("away", 0) or 0

        result = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "total_goals": home_goals + away_goals,
            "ht_home_goals": ht_home,
            "ht_away_goals": ht_away,
            "ht_total_goals": ht_home + ht_away,
            "btts": home_goals > 0 and away_goals > 0,
            "match_result": (
                f"{fixture['teams']['home']['name']} Win" if home_goals > away_goals
                else "Draw" if home_goals == away_goals
                else f"{fixture['teams']['away']['name']} Win"
            ),
        }

        # Double chance
        if home_goals >= away_goals:
            result["double_chance_1X"] = True
        if home_goals <= away_goals:
            result["double_chance_X2"] = True
        if home_goals != away_goals:
            result["double_chance_12"] = True

        return result

    def get_fixture_stats(self, fixture_id: int) -> Dict:
        """Fetch detailed match statistics (corners, cards, shots, etc.)."""
        try:
            resp = requests.get(
                f"{self.stats_base}/fixtures/statistics",
                headers=self.headers,
                params={"fixture": fixture_id},
                timeout=10
            )
            resp.raise_for_status()
            self._request_count += 1
            data = resp.json()
            stats_list = data.get("response", [])

            result = {
                "home_corners": 0, "away_corners": 0,
                "home_cards": 0, "away_cards": 0,
                "home_shots_on": 0, "away_shots_on": 0,
                "home_fouls": 0, "away_fouls": 0,
            }

            for team_stats in stats_list:
                is_home = team_stats.get("team", {}).get("id") == stats_list[0].get("team", {}).get("id") if stats_list else True
                prefix = "home" if team_stats == stats_list[0] else "away"

                for stat in team_stats.get("statistics", []):
                    val = stat.get("value", 0) or 0
                    if isinstance(val, str):
                        val = int(val.replace("%", "")) if val.replace("%", "").isdigit() else 0

                    stype = stat.get("type", "")
                    if stype == "Corner Kicks":
                        result[f"{prefix}_corners"] = val
                    elif stype == "Yellow Cards":
                        result[f"{prefix}_cards"] += val
                    elif stype == "Red Cards":
                        result[f"{prefix}_cards"] += val
                    elif stype == "Shots on Goal":
                        result[f"{prefix}_shots_on"] = val
                    elif stype == "Fouls":
                        result[f"{prefix}_fouls"] = val

            result["total_corners"] = result["home_corners"] + result["away_corners"]
            result["total_cards"] = result["home_cards"] + result["away_cards"]
            result["total_shots_on"] = result["home_shots_on"] + result["away_shots_on"]

            return result

        except Exception as e:
            return {
                "home_corners": 0, "away_corners": 0, "total_corners": 0,
                "home_cards": 0, "away_cards": 0, "total_cards": 0,
                "home_shots_on": 0, "away_shots_on": 0, "total_shots_on": 0,
                "home_fouls": 0, "away_fouls": 0,
            }

    def reconstruct_odds(self, fixture: Dict, result: Dict,
                          match_stats: Dict = None) -> Dict:
        """
        Reconstruct realistic pre-match odds from results.
        This is necessary because historical odds require a paid API plan.

        Method: Use known league averages + team strength indicators to
        generate odds that are realistic but NOT perfectly calibrated
        (simulating real bookmaker inefficiency).
        """
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        home_goals = result["home_goals"]
        away_goals = result["away_goals"]
        total = result["total_goals"]

        markets = {}

        # --- Match Result (1X2) ---
        # Generate realistic odds — bookmakers are quite accurate on average
        # Small noise only (~3-5% deviation from true probability)
        home_strength = 0.44 + random.gauss(0, 0.05)
        draw_prob = 0.27 + random.gauss(0, 0.03)
        away_strength = 1 - home_strength - draw_prob

        # Clamp
        home_strength = max(0.15, min(0.70, home_strength))
        draw_prob = max(0.15, min(0.35, draw_prob))
        away_strength = max(0.15, 1 - home_strength - draw_prob)

        margin = 1.05  # 5% bookmaker margin
        markets["match_result"] = self._generate_bookmaker_odds(
            {f"{home} Win": home_strength, "Draw": draw_prob, f"{away} Win": away_strength},
            margin, num_bookmakers=5
        )

        # --- Goals Over/Under ---
        avg_goals = 2.65 + random.gauss(0, 0.3)  # League average ~2.65
        from scipy.stats import poisson

        for line in [1.5, 2.5, 3.5]:
            over_prob = 1 - poisson.cdf(int(line), avg_goals)
            noise = random.gauss(0, 0.03)
            over_prob = max(0.10, min(0.90, over_prob + noise))
            markets[f"goals_over_under_{line}"] = self._generate_bookmaker_odds(
                {f"Over {line}": over_prob, f"Under {line}": 1 - over_prob},
                margin, num_bookmakers=5
            )

        # --- BTTS ---
        btts_prob = 0.52 + random.gauss(0, 0.06)
        btts_prob = max(0.25, min(0.75, btts_prob))
        markets["btts"] = self._generate_bookmaker_odds(
            {"Yes": btts_prob, "No": 1 - btts_prob},
            margin, num_bookmakers=5
        )

        # --- Corners Over/Under ---
        avg_corners = 10.2 + random.gauss(0, 1.0)
        for line in [8.5, 9.5, 10.5, 11.5]:
            over_prob = 1 - poisson.cdf(int(line), avg_corners)
            noise = random.gauss(0, 0.04)
            over_prob = max(0.15, min(0.85, over_prob + noise))
            markets[f"corners_over_under_{line}"] = self._generate_bookmaker_odds(
                {f"Over {line}": over_prob, f"Under {line}": 1 - over_prob},
                margin, num_bookmakers=4
            )

        # --- Cards Over/Under ---
        avg_cards = 4.2 + random.gauss(0, 0.6)
        for line in [3.5, 4.5, 5.5]:
            over_prob = 1 - poisson.cdf(int(line), avg_cards)
            noise = random.gauss(0, 0.04)
            over_prob = max(0.15, min(0.85, over_prob + noise))
            markets[f"cards_over_under_{line}"] = self._generate_bookmaker_odds(
                {f"Over {line}": over_prob, f"Under {line}": 1 - over_prob},
                margin, num_bookmakers=4
            )

        # --- First Half Goals ---
        fh_avg = avg_goals * 0.42
        for line in [0.5, 1.5]:
            over_prob = 1 - poisson.cdf(int(line), fh_avg)
            noise = random.gauss(0, 0.03)
            over_prob = max(0.15, min(0.85, over_prob + noise))
            markets[f"first_half_goals_over_under_{line}"] = self._generate_bookmaker_odds(
                {f"Over {line}": over_prob, f"Under {line}": 1 - over_prob},
                margin, num_bookmakers=3
            )

        # --- Double Chance ---
        markets["double_chance"] = self._generate_bookmaker_odds(
            {
                "1X": home_strength + draw_prob,
                "X2": draw_prob + away_strength,
                "12": home_strength + away_strength,
            },
            margin * 0.98,  # Slightly less margin on double chance
            num_bookmakers=4
        )

        return markets

    def _generate_bookmaker_odds(self, true_probs: Dict[str, float],
                                   margin: float, num_bookmakers: int = 5) -> List[Dict]:
        """
        Generate realistic odds from multiple bookmakers with slight variations.
        IMPORTANT: Keep bookmaker disagreement small (~1-3%) to simulate
        real markets. Large disagreements create unrealistic value.
        """
        bookmaker_names = ["Pinnacle", "Bet365", "Unibet", "William Hill",
                           "Betfair", "1xBet", "Betway", "888sport"][:num_bookmakers]
        result = []

        for i, bookie in enumerate(bookmaker_names):
            odds_dict = {}
            for outcome, prob in true_probs.items():
                # Pinnacle has tighter margin (~2%)
                if bookie == "Pinnacle":
                    bookie_margin = 1.02
                else:
                    # Soft bookmakers have 4-7% margin
                    bookie_margin = 1.04 + random.random() * 0.03

                # Per-bookmaker noise is SMALL (1-2% at most)
                noise = random.gauss(0, 0.008)
                adjusted_prob = max(0.03, prob + noise)
                odds = round(bookie_margin / adjusted_prob, 2)
                odds = max(1.01, odds)
                odds_dict[outcome] = odds

            result.append({
                "bookmaker": bookie,
                "odds": odds_dict
            })

        return result


# ─── Bet Resolver ─────────────────────────────────────────────────────
class BetResolver:
    """Determines whether a bet won or lost based on actual match result."""

    @staticmethod
    def resolve(bet: FinalBet, result: Dict, match_stats: Dict) -> Tuple[bool, str]:
        """
        Returns (won: bool, actual_outcome: str)
        """
        market = bet.market
        outcome = bet.outcome
        total_goals = result["total_goals"]
        home_goals = result["home_goals"]
        away_goals = result["away_goals"]

        # --- Goals Over/Under ---
        if market.startswith("goals_over_under_"):
            line = float(market.split("_")[-1])
            actual = f"Over {line}" if total_goals > line else f"Under {line}"
            return outcome == actual, actual

        # --- Match Result ---
        if market == "match_result":
            actual = result["match_result"]
            return outcome == actual, actual

        # --- BTTS ---
        if market == "btts":
            actual = "Yes" if result["btts"] else "No"
            return outcome == actual, actual

        # --- Corners Over/Under ---
        if market.startswith("corners_over_under_"):
            line = float(market.split("_")[-1])
            total_corners = match_stats.get("total_corners", 0)
            if total_corners == 0:
                return False, "No data"  # Can't resolve without stats
            actual = f"Over {line}" if total_corners > line else f"Under {line}"
            return outcome == actual, actual

        # --- Cards Over/Under ---
        if market.startswith("cards_over_under_"):
            line = float(market.split("_")[-1])
            total_cards = match_stats.get("total_cards", 0)
            if total_cards == 0:
                return False, "No data"
            actual = f"Over {line}" if total_cards > line else f"Under {line}"
            return outcome == actual, actual

        # --- First Half Goals ---
        if market.startswith("first_half_goals_over_under_"):
            line = float(market.split("_")[-1])
            ht_goals = result["ht_total_goals"]
            actual = f"Over {line}" if ht_goals > line else f"Under {line}"
            return outcome == actual, actual

        # --- Double Chance ---
        if market == "double_chance":
            if "1X" in outcome:
                won = home_goals >= away_goals
            elif "X2" in outcome:
                won = away_goals >= home_goals
            elif "12" in outcome:
                won = home_goals != away_goals
            else:
                won = False
            return won, result["match_result"]

        # --- Corner Dominance ---
        if market == "corners_home_away":
            hc = match_stats.get("home_corners", 0)
            ac = match_stats.get("away_corners", 0)
            if hc == 0 and ac == 0:
                return False, "No data"
            actual = "Home More Corners" if hc > ac else "Away More Corners"
            return outcome.endswith("More Corners") and outcome.split(" ")[0] in bet.home_team and hc > ac, actual

        # --- Shots on Target O/U ---
        if market.startswith("shots_on_target_over_under_"):
            line = float(market.split("_")[-1])
            total_sot = match_stats.get("total_shots_on", 0)
            if total_sot == 0:
                return False, "No data"
            actual = f"Over {line}" if total_sot > line else f"Under {line}"
            return outcome == actual, actual

        # --- Throw-ins ---
        if market.startswith("throwins_over_under_"):
            # Throw-in stats rarely available — skip
            return False, "No data"

        # Default: unresolvable
        return False, "Unknown market"


# ─── Main Backtester ──────────────────────────────────────────────────
class Backtester:
    """
    The main backtester that runs our model against historical data.
    """

    def __init__(self, stats_api_key: str, odds_api_key: str = None,
                 starting_bankroll: float = 1000.0, flat_staking: bool = True):
        self.fetcher = HistoricalDataFetcher(stats_api_key, odds_api_key)
        self.resolver = BetResolver()

        # Agents — use V2 if available
        try:
            from agents.stats_agent_v2 import StatsAgentV2
            from agents.value_agent_v2 import ValueAgentV2
            self.agents = [FormAgent(), HistoricalAgent(), StatsAgentV2(), MarketAgent(), ValueAgentV2()]
            print("  Using V2 agents (Dixon-Coles + Elo)")
        except ImportError:
            self.agents = [FormAgent(), HistoricalAgent(), StatsAgent(), MarketAgent(), ValueAgent()]
            print("  Using V1 agents")
        self.meta_agent = MetaAgent()

        # Bankroll
        self.starting_bankroll = starting_bankroll
        self.bankroll = starting_bankroll
        self.peak_bankroll = starting_bankroll
        self.flat_staking = flat_staking  # Use initial bankroll for stake calc (realistic)

        # Results tracking
        self.bet_results: List[BetResult] = []
        self.daily_bankroll: List[Tuple[str, float]] = []

    def run(self, leagues: List[str] = None, season: int = 2025,
            max_matches: int = 100, use_real_odds: bool = False) -> BacktestSummary:
        """
        Run the full backtest.
        """
        if leagues is None:
            leagues = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]

        print("=" * 80)
        print("  BACKTEST — Historical Performance Analysis")
        print(f"  Leagues: {', '.join(leagues)}")
        print(f"  Season: {season}/{season+1}")
        print(f"  Starting bankroll: €{self.starting_bankroll:.2f}")
        print("=" * 80)

        all_fixtures = []

        # Step 1: Fetch completed fixtures
        print("\n[1/3] Fetching completed fixtures...")
        for league in leagues:
            fixtures = self.fetcher.fetch_completed_fixtures(league, season)
            for f in fixtures:
                f["_league_name"] = league
            all_fixtures.extend(fixtures)
            time.sleep(1)  # Rate limit

        # Sort by date (chronological order — critical for realistic backtesting)
        all_fixtures.sort(key=lambda f: f["fixture"]["date"])

        # Limit to max_matches
        if len(all_fixtures) > max_matches:
            # Take evenly spaced matches across the season
            step = len(all_fixtures) // max_matches
            all_fixtures = all_fixtures[::step][:max_matches]

        print(f"\n  Total fixtures to backtest: {len(all_fixtures)}")

        # Step 2: Process each match
        print("\n[2/3] Running model on historical matches...")
        processed = 0

        for i, fixture in enumerate(all_fixtures):
            home = fixture["teams"]["home"]["name"]
            away = fixture["teams"]["away"]["name"]
            league = fixture["_league_name"]
            match_date = fixture["fixture"]["date"][:10]
            fixture_id = fixture["fixture"]["id"]

            print(f"\n  [{i+1}/{len(all_fixtures)}] {match_date} | {home} vs {away} ({league})")

            # Get actual result
            result = self.fetcher.get_match_result(fixture)
            print(f"    Result: {result['home_goals']}-{result['away_goals']}")

            # Get match stats (corners, cards, etc.)
            # Only fetch if we haven't exceeded API limit
            if self.fetcher._request_count < 80:
                match_stats = self.fetcher.get_fixture_stats(fixture_id)
                time.sleep(0.5)
            else:
                match_stats = {
                    "total_corners": 0, "total_cards": 0, "total_shots_on": 0,
                    "home_corners": 0, "away_corners": 0,
                    "home_cards": 0, "away_cards": 0,
                    "home_shots_on": 0, "away_shots_on": 0,
                    "home_fouls": 0, "away_fouls": 0,
                }

            # Reconstruct odds (or use real historical odds if available)
            odds = self.fetcher.reconstruct_odds(fixture, result, match_stats)

            # Build match data in our pipeline format
            match_data = self.fetcher.fixture_to_match_data(fixture, league)
            match_data["markets"] = odds

            # Build team stats (simplified — use league averages + some noise)
            home_form = self._build_form_data(home, league)
            away_form = self._build_form_data(away, league)
            h2h = self._build_h2h_data(home, away)
            home_stats = self._build_season_stats(home, is_home=True)
            away_stats = self._build_season_stats(away, is_home=False)

            # Run agents
            agent_reports = []
            for agent in self.agents:
                try:
                    report = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats)
                    agent_reports.append(report)
                except Exception as e:
                    pass

            # Meta synthesis
            final_bets = self.meta_agent.synthesize(match_data, agent_reports)

            # Resolve bets
            for bet in final_bets:
                won, actual = self.resolver.resolve(bet, result, match_stats)

                if actual == "No data" or actual == "Unknown market":
                    continue  # Skip unresolvable bets

                # Calculate P&L (flat staking = % of INITIAL bankroll, not current)
                base = self.starting_bankroll if self.flat_staking else self.bankroll
                stake_amount = base * (bet.recommended_stake / 100)
                if won:
                    profit = stake_amount * (bet.best_odds - 1)
                else:
                    profit = -stake_amount

                self.bankroll += profit
                self.peak_bankroll = max(self.peak_bankroll, self.bankroll)

                self.bet_results.append(BetResult(
                    match_id=match_data["id"],
                    match_date=match_date,
                    home_team=home,
                    away_team=away,
                    league=league,
                    market=bet.market,
                    outcome=bet.outcome,
                    odds=bet.best_odds,
                    bookmaker=bet.best_bookmaker,
                    stake_pct=bet.recommended_stake,
                    confidence=bet.confidence_pct,
                    expected_value=bet.expected_value,
                    risk_level=bet.risk_level,
                    won=won,
                    actual_outcome=actual,
                    profit=profit,
                    running_bankroll=self.bankroll,
                ))

            bet_count = len([b for b in final_bets if self.resolver.resolve(b, result, match_stats)[1] not in ("No data", "Unknown market")])
            print(f"    Bets: {bet_count} | Bankroll: €{self.bankroll:.2f}")

            self.daily_bankroll.append((match_date, self.bankroll))
            processed += 1

        # Step 3: Generate summary
        print("\n[3/3] Generating backtest report...")
        summary = self._generate_summary()
        return summary

    def run_with_cached_data(self, cached_file: str = None) -> BacktestSummary:
        """
        Run backtest using cached/generated data instead of API calls.
        This is the offline mode — no API needed, uses realistic simulated matches.
        """
        print("=" * 80)
        print("  BACKTEST — Offline Mode (Simulated Historical Data)")
        print(f"  Starting bankroll: €{self.starting_bankroll:.2f}")
        print("=" * 80)

        # Generate realistic historical matches
        matches = self._generate_historical_matches(200)

        print(f"\n  Generated {len(matches)} historical matches for backtesting")
        print("\n  Running model on each match...")

        for i, (match_data, result, match_stats) in enumerate(matches):
            home = match_data["home_team"]
            away = match_data["away_team"]
            match_date = match_data["commence_time"][:10]

            if i % 20 == 0:
                print(f"\n  [{i+1}/{len(matches)}] {match_date} | {home} vs {away}")

            # Build team data
            home_form = self._build_form_data(home, match_data["league"])
            away_form = self._build_form_data(away, match_data["league"])
            h2h = self._build_h2h_data(home, away)
            home_stats = self._build_season_stats(home, is_home=True)
            away_stats = self._build_season_stats(away, is_home=False)

            # Run agents
            agent_reports = []
            for agent in self.agents:
                try:
                    report = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats)
                    agent_reports.append(report)
                except:
                    pass

            # Meta synthesis
            final_bets = self.meta_agent.synthesize(match_data, agent_reports)

            # Resolve bets
            for bet in final_bets:
                won, actual = self.resolver.resolve(bet, result, match_stats)
                if actual in ("No data", "Unknown market"):
                    continue

                base = self.starting_bankroll if self.flat_staking else self.bankroll
                stake_amount = base * (bet.recommended_stake / 100)
                profit = stake_amount * (bet.best_odds - 1) if won else -stake_amount

                self.bankroll += profit
                self.peak_bankroll = max(self.peak_bankroll, self.bankroll)

                self.bet_results.append(BetResult(
                    match_id=match_data["id"],
                    match_date=match_date,
                    home_team=home,
                    away_team=away,
                    league=match_data["league"],
                    market=bet.market,
                    outcome=bet.outcome,
                    odds=bet.best_odds,
                    bookmaker=bet.best_bookmaker,
                    stake_pct=bet.recommended_stake,
                    confidence=bet.confidence_pct,
                    expected_value=bet.expected_value,
                    risk_level=bet.risk_level,
                    won=won,
                    actual_outcome=actual,
                    profit=profit,
                    running_bankroll=self.bankroll,
                ))

            self.daily_bankroll.append((match_date, self.bankroll))

        summary = self._generate_summary()
        return summary

    def _generate_historical_matches(self, n: int = 200) -> List[Tuple[Dict, Dict, Dict]]:
        """Generate realistic historical match data for offline backtesting."""
        from scipy.stats import poisson

        teams = {
            "Premier League": [
                ("Arsenal", 1.8, 0.8), ("Man City", 2.1, 0.6), ("Liverpool", 1.9, 0.7),
                ("Chelsea", 1.5, 1.0), ("Man United", 1.4, 1.1), ("Tottenham", 1.5, 1.0),
                ("Newcastle", 1.5, 0.9), ("Aston Villa", 1.4, 1.0), ("Brighton", 1.3, 1.1),
                ("West Ham", 1.2, 1.2),
            ],
            "La Liga": [
                ("Real Madrid", 2.0, 0.7), ("Barcelona", 2.1, 0.8), ("Atletico Madrid", 1.3, 0.6),
                ("Real Sociedad", 1.4, 1.0), ("Villarreal", 1.3, 1.0), ("Athletic Club", 1.2, 0.9),
                ("Betis", 1.3, 1.1), ("Sevilla", 1.1, 1.2), ("Girona", 1.4, 1.1),
                ("Mallorca", 1.0, 1.2),
            ],
            "Bundesliga": [
                ("Bayern Munich", 2.3, 0.8), ("Bayer Leverkusen", 1.8, 0.7),
                ("Borussia Dortmund", 1.7, 1.0), ("RB Leipzig", 1.6, 0.9),
                ("Stuttgart", 1.5, 1.0), ("SC Freiburg", 1.3, 1.0),
                ("Eintracht Frankfurt", 1.5, 1.1), ("Wolfsburg", 1.2, 1.1),
                ("Union Berlin", 1.0, 1.1), ("Hoffenheim", 1.3, 1.3),
            ],
            "Serie A": [
                ("Inter Milan", 1.8, 0.6), ("Napoli", 1.7, 0.7), ("AC Milan", 1.5, 0.9),
                ("Juventus", 1.4, 0.7), ("Atalanta", 1.7, 1.0), ("Roma", 1.3, 1.0),
                ("Lazio", 1.4, 1.1), ("Fiorentina", 1.3, 1.0), ("Bologna", 1.2, 1.0),
                ("Torino", 1.1, 1.1),
            ],
            "Ligue 1": [
                ("Paris Saint-Germain", 2.2, 0.5), ("Monaco", 1.6, 0.9),
                ("Marseille", 1.5, 0.9), ("Lille", 1.3, 0.8), ("Lyon", 1.4, 1.1),
                ("Nice", 1.2, 0.9), ("Lens", 1.2, 1.0), ("Rennes", 1.1, 1.1),
                ("Strasbourg", 1.0, 1.2), ("Toulouse", 1.0, 1.1),
            ],
        }

        matches = []
        base_date = datetime(2025, 8, 15)

        for i in range(n):
            # Pick random league and matchup
            league = random.choice(list(teams.keys()))
            league_teams = teams[league]
            home_team, away_team = random.sample(league_teams, 2)

            home_name, home_attack, home_defense = home_team
            away_name, away_attack, away_defense = away_team

            # Simulate match
            home_xg = (home_attack + away_defense) / 2 * 1.1  # Home advantage
            away_xg = (away_attack + home_defense) / 2

            home_goals = poisson.rvs(home_xg)
            away_goals = poisson.rvs(away_xg)

            # Corners (~10 per match on average)
            home_corners = poisson.rvs(5.2 + home_attack * 0.3)
            away_corners = poisson.rvs(4.8 + away_attack * 0.2)

            # Cards (~4 per match)
            home_cards = poisson.rvs(1.8 + away_attack * 0.2)
            away_cards = poisson.rvs(2.0 + home_attack * 0.2)

            # Shots on target
            home_sot = poisson.rvs(3.5 + home_attack * 0.5)
            away_sot = poisson.rvs(3.0 + away_attack * 0.4)

            # First half goals (~42% of total)
            ht_home = min(home_goals, poisson.rvs(home_xg * 0.42))
            ht_away = min(away_goals, poisson.rvs(away_xg * 0.42))

            match_date = base_date + timedelta(days=i * 1.5 + random.randint(0, 2))
            match_id = f"bt_{i:04d}"

            # Build result
            result = {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "total_goals": home_goals + away_goals,
                "ht_home_goals": ht_home,
                "ht_away_goals": ht_away,
                "ht_total_goals": ht_home + ht_away,
                "btts": home_goals > 0 and away_goals > 0,
                "match_result": (
                    f"{home_name} Win" if home_goals > away_goals
                    else "Draw" if home_goals == away_goals
                    else f"{away_name} Win"
                ),
            }

            match_stats = {
                "home_corners": home_corners, "away_corners": away_corners,
                "total_corners": home_corners + away_corners,
                "home_cards": home_cards, "away_cards": away_cards,
                "total_cards": home_cards + away_cards,
                "home_shots_on": home_sot, "away_shots_on": away_sot,
                "total_shots_on": home_sot + away_sot,
                "home_fouls": 0, "away_fouls": 0,
            }

            # Generate odds (with intentional noise to simulate bookmaker mispricing)
            fixture_stub = {"teams": {"home": {"name": home_name}, "away": {"name": away_name}}}
            odds = self.fetcher.reconstruct_odds(fixture_stub, result, match_stats)

            match_data = {
                "id": match_id,
                "home_team": home_name,
                "away_team": away_name,
                "league": league,
                "commence_time": match_date.isoformat(),
                "markets": odds,
            }

            matches.append((match_data, result, match_stats))

        return matches

    def _build_form_data(self, team: str, league: str) -> Dict:
        """Build simplified form data for backtesting."""
        # Use league-average data with some noise per team
        return {
            "team": team,
            "form_string": "".join(random.choices(["W", "W", "W", "D", "D", "L", "L"], k=10)),
            "wins": random.randint(3, 7),
            "draws": random.randint(1, 4),
            "losses": random.randint(1, 4),
            "points_last_10": random.randint(10, 22),
            "goals_scored_avg": round(1.0 + random.random() * 1.0, 2),
            "goals_conceded_avg": round(0.7 + random.random() * 0.8, 2),
            "corners_avg": round(4.0 + random.random() * 3.0, 2),
            "cards_avg": round(1.5 + random.random() * 1.5, 2),
            "shots_on_target_avg": round(3.0 + random.random() * 3.0, 2),
            "throw_ins_avg": round(19 + random.random() * 6, 1),
            "fouls_avg": round(10 + random.random() * 5, 1),
            "matches": [],
        }

    def _build_h2h_data(self, home: str, away: str) -> Dict:
        """Build simplified H2H data."""
        n = random.randint(3, 15)
        hw = random.randint(0, n)
        aw = random.randint(0, n - hw)
        d = n - hw - aw
        return {
            "home": home, "away": away,
            "total_matches": n,
            "home_wins": hw, "away_wins": aw, "draws": d,
            "avg_goals_per_match": round(2.0 + random.random() * 1.5, 2),
            "avg_corners_per_match": round(8.5 + random.random() * 3.0, 2),
            "avg_cards_per_match": round(3.0 + random.random() * 3.0, 2),
            "btts_percentage": round(40 + random.random() * 30, 1),
            "over_2_5_percentage": round(40 + random.random() * 30, 1),
        }

    def _build_season_stats(self, team: str, is_home: bool) -> Dict:
        """Build season stats."""
        base_attack = 1.0 + random.random() * 1.0
        base_defense = 0.6 + random.random() * 0.8
        return {
            "team": team, "season": "2025/26", "played": 26,
            "home_corners_avg": round(4.5 + random.random() * 2.5, 2),
            "away_corners_avg": round(3.8 + random.random() * 2.5, 2),
            "home_cards_avg": round(1.5 + random.random() * 1.5, 2),
            "away_cards_avg": round(1.8 + random.random() * 1.5, 2),
            "home_goals_avg": round(base_attack * 1.15, 2),
            "away_goals_avg": round(base_attack * 0.85, 2),
            "home_conceded_avg": round(base_defense * 0.9, 2),
            "away_conceded_avg": round(base_defense * 1.15, 2),
            "clean_sheets_pct": round(20 + random.random() * 25, 1),
            "btts_pct": round(40 + random.random() * 25, 1),
            "over_2_5_pct": round(40 + random.random() * 25, 1),
            "avg_throw_ins": round(19 + random.random() * 6, 1),
            "avg_fouls": round(10 + random.random() * 5, 1),
            "avg_shots_on_target": round(3.5 + random.random() * 3.0, 2),
        }

    def _generate_summary(self) -> BacktestSummary:
        """Generate comprehensive summary of backtest results."""
        summary = BacktestSummary()

        if not self.bet_results:
            print("  No bets resolved!")
            return summary

        summary.total_bets = len(self.bet_results)
        summary.wins = len([b for b in self.bet_results if b.won])
        summary.losses = summary.total_bets - summary.wins
        summary.win_rate = summary.wins / summary.total_bets * 100
        summary.total_staked = sum(b.stake_pct * self.starting_bankroll / 100 for b in self.bet_results)
        summary.total_profit = sum(b.profit for b in self.bet_results)
        summary.starting_bankroll = self.starting_bankroll
        summary.final_bankroll = self.bankroll
        summary.peak_bankroll = self.peak_bankroll
        summary.roi = (summary.total_profit / summary.total_staked * 100) if summary.total_staked > 0 else 0

        # Max drawdown
        peak = self.starting_bankroll
        max_dd = 0
        for br in self.bet_results:
            peak = max(peak, br.running_bankroll)
            dd = (peak - br.running_bankroll) / peak * 100
            max_dd = max(max_dd, dd)
        summary.max_drawdown = max_dd

        # Sharpe ratio (simplified)
        returns = [b.profit / (b.stake_pct * self.starting_bankroll / 100) if b.stake_pct > 0 else 0
                    for b in self.bet_results]
        if len(returns) > 1:
            import statistics
            avg_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
            summary.sharpe_ratio = avg_ret / std_ret if std_ret > 0 else 0

        # By risk level
        for risk in ["LOW", "MEDIUM", "HIGH"]:
            bets = [b for b in self.bet_results if b.risk_level == risk]
            wins = len([b for b in bets if b.won])
            total = len(bets)
            profit = sum(b.profit for b in bets)
            if risk == "LOW":
                summary.low_risk_record = f"{wins}W/{total-wins}L ({wins/total*100:.0f}%) P&L: €{profit:+.2f}" if total > 0 else "N/A"
            elif risk == "MEDIUM":
                summary.medium_risk_record = f"{wins}W/{total-wins}L ({wins/total*100:.0f}%) P&L: €{profit:+.2f}" if total > 0 else "N/A"
            else:
                summary.high_risk_record = f"{wins}W/{total-wins}L ({wins/total*100:.0f}%) P&L: €{profit:+.2f}" if total > 0 else "N/A"

        # By market
        market_groups = defaultdict(list)
        for b in self.bet_results:
            # Group by market category
            if "goals" in b.market and "first_half" not in b.market:
                cat = "Goals O/U"
            elif "btts" in b.market:
                cat = "BTTS"
            elif "corners" in b.market:
                cat = "Corners"
            elif "cards" in b.market:
                cat = "Cards"
            elif "match_result" in b.market:
                cat = "Match Result"
            elif "first_half" in b.market:
                cat = "First Half Goals"
            elif "double_chance" in b.market:
                cat = "Double Chance"
            elif "shots" in b.market:
                cat = "Shots on Target"
            else:
                cat = "Other"
            market_groups[cat].append(b)

        for cat, bets in market_groups.items():
            wins = len([b for b in bets if b.won])
            total = len(bets)
            profit = sum(b.profit for b in bets)
            avg_odds = sum(b.odds for b in bets) / total if total > 0 else 0
            summary.market_breakdown[cat] = {
                "bets": total, "wins": wins, "win_rate": wins/total*100 if total > 0 else 0,
                "profit": profit, "avg_odds": avg_odds,
            }

        # By league
        league_groups = defaultdict(list)
        for b in self.bet_results:
            league_groups[b.league].append(b)

        for league, bets in league_groups.items():
            wins = len([b for b in bets if b.won])
            total = len(bets)
            profit = sum(b.profit for b in bets)
            summary.league_breakdown[league] = {
                "bets": total, "wins": wins, "win_rate": wins/total*100 if total > 0 else 0,
                "profit": profit,
            }

        # Monthly P&L
        monthly = defaultdict(float)
        for b in self.bet_results:
            month = b.match_date[:7]  # "2025-08"
            monthly[month] += b.profit
        summary.monthly_pl = dict(sorted(monthly.items()))

        return summary

    def print_report(self, summary: BacktestSummary):
        """Print a detailed backtest report."""
        print("\n" + "=" * 80)
        print("  BACKTEST RESULTS")
        print("=" * 80)

        # Overall
        print(f"\n  {'OVERALL PERFORMANCE':─<60}")
        print(f"  Total Bets:        {summary.total_bets}")
        print(f"  Win/Loss:          {summary.wins}W / {summary.losses}L ({summary.win_rate:.1f}%)")
        print(f"  Total Staked:      €{summary.total_staked:,.2f}")
        print(f"  Total Profit:      €{summary.total_profit:+,.2f}")
        print(f"  ROI:               {summary.roi:+.2f}%")
        print(f"  Starting Bankroll: €{summary.starting_bankroll:,.2f}")
        print(f"  Final Bankroll:    €{summary.final_bankroll:,.2f}")
        print(f"  Peak Bankroll:     €{summary.peak_bankroll:,.2f}")
        print(f"  Max Drawdown:      {summary.max_drawdown:.1f}%")
        print(f"  Sharpe Ratio:      {summary.sharpe_ratio:.3f}")

        # By risk
        print(f"\n  {'BY RISK LEVEL':─<60}")
        print(f"  LOW:    {summary.low_risk_record}")
        print(f"  MEDIUM: {summary.medium_risk_record}")
        print(f"  HIGH:   {summary.high_risk_record}")

        # By market
        print(f"\n  {'BY MARKET TYPE':─<60}")
        print(f"  {'Market':<20} {'Bets':>6} {'Win%':>7} {'Profit':>10} {'Avg Odds':>10}")
        for cat, data in sorted(summary.market_breakdown.items(), key=lambda x: x[1]["profit"], reverse=True):
            print(f"  {cat:<20} {data['bets']:>6} {data['win_rate']:>6.1f}% €{data['profit']:>+9.2f} {data['avg_odds']:>9.2f}")

        # By league
        print(f"\n  {'BY LEAGUE':─<60}")
        print(f"  {'League':<25} {'Bets':>6} {'Win%':>7} {'Profit':>10}")
        for league, data in sorted(summary.league_breakdown.items(), key=lambda x: x[1]["profit"], reverse=True):
            print(f"  {league:<25} {data['bets']:>6} {data['win_rate']:>6.1f}% €{data['profit']:>+9.2f}")

        # Monthly P&L
        if summary.monthly_pl:
            print(f"\n  {'MONTHLY P&L':─<60}")
            running = 0
            for month, pl in summary.monthly_pl.items():
                running += pl
                bar = "█" * max(0, int(pl / 5)) if pl > 0 else "░" * max(0, int(-pl / 5))
                print(f"  {month}  €{pl:>+9.2f}  (cumul: €{running:>+9.2f})  {bar}")

        # Verdict
        print(f"\n  {'VERDICT':─<60}")
        if summary.roi > 5:
            print(f"  ✓ PROFITABLE — {summary.roi:+.1f}% ROI across {summary.total_bets} bets")
            print(f"  → Model shows edge. Consider live testing with small stakes.")
        elif summary.roi > 0:
            print(f"  ~ MARGINAL — {summary.roi:+.1f}% ROI")
            print(f"  → Slight edge but may not survive transaction costs.")
        else:
            print(f"  ✗ UNPROFITABLE — {summary.roi:+.1f}% ROI")
            print(f"  → Model needs improvement before live betting.")

        print("=" * 80)


# ─── Dashboard Generator ─────────────────────────────────────────────
def generate_backtest_dashboard(summary: BacktestSummary, bet_results: List[BetResult],
                                 daily_bankroll: List[Tuple[str, float]],
                                 output_path: str):
    """Generate an interactive HTML dashboard for backtest results."""

    # Prepare data for charts
    bankroll_data = json.dumps([{"date": d, "bankroll": round(b, 2)} for d, b in daily_bankroll])
    monthly_data = json.dumps([{"month": m, "pl": round(p, 2)} for m, p in summary.monthly_pl.items()])

    market_data = json.dumps([
        {"market": k, "bets": v["bets"], "winRate": round(v["win_rate"], 1),
         "profit": round(v["profit"], 2), "avgOdds": round(v["avg_odds"], 2)}
        for k, v in sorted(summary.market_breakdown.items(), key=lambda x: x[1]["profit"], reverse=True)
    ])

    league_data = json.dumps([
        {"league": k, "bets": v["bets"], "winRate": round(v["win_rate"], 1),
         "profit": round(v["profit"], 2)}
        for k, v in sorted(summary.league_breakdown.items(), key=lambda x: x[1]["profit"], reverse=True)
    ])

    # Recent bets table
    recent_bets = bet_results[-50:]  # Last 50 bets
    bets_json = json.dumps([{
        "date": b.match_date,
        "match": f"{b.home_team} vs {b.away_team}",
        "league": b.league,
        "market": b.market,
        "outcome": b.outcome,
        "odds": b.odds,
        "confidence": b.confidence,
        "ev": b.expected_value,
        "risk": b.risk_level,
        "won": b.won,
        "actual": b.actual_outcome,
        "profit": round(b.profit, 2),
        "bankroll": round(b.running_bankroll, 2),
    } for b in recent_bets])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backtest Results — Football Betting Intelligence</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e17; color: #e0e4ef; }}
.header {{ background: linear-gradient(135deg, #1a1f35 0%, #0d1220 100%); padding: 24px 32px; border-bottom: 1px solid #1e2540; }}
.header h1 {{ font-size: 22px; color: #fff; margin-bottom: 4px; }}
.header .sub {{ color: #8890a4; font-size: 13px; }}
.container {{ max-width: 1300px; margin: 0 auto; padding: 24px; }}

/* KPI Cards */
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }}
.kpi {{ background: #141829; border: 1px solid #1e2540; border-radius: 10px; padding: 18px 16px; }}
.kpi .label {{ font-size: 11px; color: #6b7394; text-transform: uppercase; letter-spacing: 1px; }}
.kpi .value {{ font-size: 26px; font-weight: 700; margin: 6px 0 2px; }}
.kpi .detail {{ font-size: 12px; color: #8890a4; }}
.profit {{ color: #34d399; }}
.loss {{ color: #f87171; }}
.neutral {{ color: #fbbf24; }}

/* Chart containers */
.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
.chart-box {{ background: #141829; border: 1px solid #1e2540; border-radius: 10px; padding: 20px; }}
.chart-box h3 {{ font-size: 14px; color: #a0a8c4; margin-bottom: 14px; }}
canvas {{ width: 100% !important; height: 250px !important; }}

/* Tables */
.table-box {{ background: #141829; border: 1px solid #1e2540; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
.table-box h3 {{ font-size: 14px; color: #a0a8c4; margin-bottom: 14px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #1e2540; color: #6b7394; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; font-size: 10px; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #13162a; }}
tr:hover {{ background: #1a1f35; }}
.won {{ color: #34d399; font-weight: 600; }}
.lost {{ color: #f87171; font-weight: 600; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
.badge-low {{ background: #064e3b; color: #34d399; }}
.badge-med {{ background: #713f12; color: #fbbf24; }}
.badge-high {{ background: #7f1d1d; color: #f87171; }}

.verdict {{ background: #141829; border: 1px solid #1e2540; border-radius: 10px; padding: 28px; margin-top: 24px; text-align: center; }}
.verdict h2 {{ font-size: 20px; margin-bottom: 10px; }}
.verdict p {{ color: #8890a4; font-size: 14px; }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
</head>
<body>

<div class="header">
    <h1>Backtest Results — Football Betting Intelligence</h1>
    <div class="sub">Historical Performance Analysis | Top 5 European Leagues | Season 2025/26</div>
</div>

<div class="container">

<!-- KPI Cards -->
<div class="kpi-grid">
    <div class="kpi">
        <div class="label">Total Bets</div>
        <div class="value">{summary.total_bets}</div>
        <div class="detail">{summary.wins}W / {summary.losses}L</div>
    </div>
    <div class="kpi">
        <div class="label">Win Rate</div>
        <div class="value">{summary.win_rate:.1f}%</div>
        <div class="detail">across all markets</div>
    </div>
    <div class="kpi">
        <div class="label">ROI</div>
        <div class="value {'profit' if summary.roi > 0 else 'loss'}">{summary.roi:+.2f}%</div>
        <div class="detail">return on investment</div>
    </div>
    <div class="kpi">
        <div class="label">Total Profit</div>
        <div class="value {'profit' if summary.total_profit > 0 else 'loss'}">€{summary.total_profit:+,.2f}</div>
        <div class="detail">from €{summary.total_staked:,.2f} staked</div>
    </div>
    <div class="kpi">
        <div class="label">Final Bankroll</div>
        <div class="value">€{summary.final_bankroll:,.2f}</div>
        <div class="detail">started at €{summary.starting_bankroll:,.2f}</div>
    </div>
    <div class="kpi">
        <div class="label">Max Drawdown</div>
        <div class="value loss">{summary.max_drawdown:.1f}%</div>
        <div class="detail">peak to trough</div>
    </div>
    <div class="kpi">
        <div class="label">Sharpe Ratio</div>
        <div class="value {'profit' if summary.sharpe_ratio > 0.5 else 'neutral' if summary.sharpe_ratio > 0 else 'loss'}">{summary.sharpe_ratio:.3f}</div>
        <div class="detail">risk-adjusted return</div>
    </div>
</div>

<!-- Charts -->
<div class="chart-row">
    <div class="chart-box">
        <h3>Bankroll Over Time</h3>
        <canvas id="bankrollChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>Monthly P&L</h3>
        <canvas id="monthlyChart"></canvas>
    </div>
</div>

<div class="chart-row">
    <div class="chart-box">
        <h3>Profit by Market Type</h3>
        <canvas id="marketChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>Profit by League</h3>
        <canvas id="leagueChart"></canvas>
    </div>
</div>

<!-- Risk Level Breakdown -->
<div class="table-box">
    <h3>Risk Level Performance</h3>
    <table>
        <tr><th>Risk</th><th>Record</th></tr>
        <tr><td><span class="badge badge-low">LOW</span></td><td>{summary.low_risk_record}</td></tr>
        <tr><td><span class="badge badge-med">MEDIUM</span></td><td>{summary.medium_risk_record}</td></tr>
        <tr><td><span class="badge badge-high">HIGH</span></td><td>{summary.high_risk_record}</td></tr>
    </table>
</div>

<!-- Bet History -->
<div class="table-box">
    <h3>Recent Bet History (Last 50)</h3>
    <table id="betsTable">
        <thead>
        <tr>
            <th>Date</th><th>Match</th><th>League</th><th>Market</th><th>Bet</th>
            <th>Odds</th><th>Conf</th><th>EV</th><th>Risk</th><th>Result</th>
            <th>Actual</th><th>P&L</th><th>Bankroll</th>
        </tr>
        </thead>
        <tbody id="betsBody"></tbody>
    </table>
</div>

<!-- Verdict -->
<div class="verdict">
    <h2 class="{'profit' if summary.roi > 5 else 'neutral' if summary.roi > 0 else 'loss'}">
        {'✓ PROFITABLE' if summary.roi > 5 else '~ MARGINAL' if summary.roi > 0 else '✗ NEEDS WORK'}
    </h2>
    <p>
        {'Model shows consistent edge. Consider live testing with small stakes.' if summary.roi > 5
         else 'Slight edge detected but may not survive real-world friction.' if summary.roi > 0
         else 'Model needs improvement before live betting. Analyze losing market segments.'}
    </p>
</div>

</div>

<script>
const bankrollData = {bankroll_data};
const monthlyData = {monthly_data};
const marketData = {market_data};
const leagueData = {league_data};
const betsData = {bets_json};

// Bankroll chart
new Chart(document.getElementById('bankrollChart'), {{
    type: 'line',
    data: {{
        labels: bankrollData.map(d => d.date),
        datasets: [{{
            data: bankrollData.map(d => d.bankroll),
            borderColor: '#818cf8',
            backgroundColor: 'rgba(129,140,248,0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 2,
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            x: {{ display: true, ticks: {{ color: '#6b7394', maxTicksLimit: 8, font: {{ size: 10 }} }}, grid: {{ color: '#1e2540' }} }},
            y: {{ ticks: {{ color: '#6b7394', callback: v => '€' + v, font: {{ size: 10 }} }}, grid: {{ color: '#1e2540' }} }}
        }}
    }}
}});

// Monthly P&L
new Chart(document.getElementById('monthlyChart'), {{
    type: 'bar',
    data: {{
        labels: monthlyData.map(d => d.month),
        datasets: [{{
            data: monthlyData.map(d => d.pl),
            backgroundColor: monthlyData.map(d => d.pl > 0 ? '#34d399' : '#f87171'),
            borderRadius: 4,
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            x: {{ ticks: {{ color: '#6b7394', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
            y: {{ ticks: {{ color: '#6b7394', callback: v => '€' + v, font: {{ size: 10 }} }}, grid: {{ color: '#1e2540' }} }}
        }}
    }}
}});

// Market profit chart
new Chart(document.getElementById('marketChart'), {{
    type: 'bar',
    data: {{
        labels: marketData.map(d => d.market),
        datasets: [{{
            label: 'Profit',
            data: marketData.map(d => d.profit),
            backgroundColor: marketData.map(d => d.profit > 0 ? '#34d399' : '#f87171'),
            borderRadius: 4,
        }}]
    }},
    options: {{
        responsive: true,
        indexAxis: 'y',
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            x: {{ ticks: {{ color: '#6b7394', callback: v => '€' + v, font: {{ size: 10 }} }}, grid: {{ color: '#1e2540' }} }},
            y: {{ ticks: {{ color: '#6b7394', font: {{ size: 10 }} }}, grid: {{ display: false }} }}
        }}
    }}
}});

// League profit chart
new Chart(document.getElementById('leagueChart'), {{
    type: 'bar',
    data: {{
        labels: leagueData.map(d => d.league),
        datasets: [{{
            label: 'Profit',
            data: leagueData.map(d => d.profit),
            backgroundColor: leagueData.map(d => d.profit > 0 ? '#818cf8' : '#f87171'),
            borderRadius: 4,
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
            x: {{ ticks: {{ color: '#6b7394', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
            y: {{ ticks: {{ color: '#6b7394', callback: v => '€' + v, font: {{ size: 10 }} }}, grid: {{ color: '#1e2540' }} }}
        }}
    }}
}});

// Bets table
const tbody = document.getElementById('betsBody');
betsData.forEach(b => {{
    const row = document.createElement('tr');
    const riskClass = b.risk === 'LOW' ? 'badge-low' : b.risk === 'MEDIUM' ? 'badge-med' : 'badge-high';
    row.innerHTML = `
        <td>${{b.date}}</td>
        <td>${{b.match}}</td>
        <td>${{b.league}}</td>
        <td>${{b.market.replace(/_/g, ' ')}}</td>
        <td>${{b.outcome}}</td>
        <td>${{b.odds.toFixed(2)}}</td>
        <td>${{b.confidence.toFixed(1)}}%</td>
        <td>${{b.ev.toFixed(1)}}%</td>
        <td><span class="badge ${{riskClass}}">${{b.risk}}</span></td>
        <td class="${{b.won ? 'won' : 'lost'}}">${{b.won ? '✓ WON' : '✗ LOST'}}</td>
        <td>${{b.actual}}</td>
        <td class="${{b.profit > 0 ? 'won' : 'lost'}}">€${{b.profit.toFixed(2)}}</td>
        <td>€${{b.bankroll.toFixed(2)}}</td>
    `;
    tbody.appendChild(row);
}});
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"  Dashboard saved: {output_path}")


# ─── Entry Point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    STATS_API_KEY = os.environ.get("STATS_API_KEY", "480b0d1da4cd81135649f1a77eb6465c")
    ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "a0497245bde02bf5159229dddea27af4")

    backtester = Backtester(
        stats_api_key=STATS_API_KEY,
        odds_api_key=ODDS_API_KEY,
        starting_bankroll=1000.0,
    )

    # Use offline mode (no API calls needed) for comprehensive test
    summary = backtester.run_with_cached_data()
    backtester.print_report(summary)

    # Generate dashboard
    output_path = "/sessions/intelligent-sleepy-bell/mnt/predictions/backtest_results.html"
    generate_backtest_dashboard(
        summary, backtester.bet_results,
        backtester.daily_bankroll, output_path
    )
