"""
Comprehensive Agent Backtest Framework
Evaluates all 27 swarm intelligence agents across 2-3 seasons of real matches.
"""

import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import traceback
from collections import defaultdict
import os

# Configuration
API_KEY = "480b0d1da4cd81135649f1a77eb6465c"
BASE_URL = "https://v3.football.api-sports.io"
CACHE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_cache.json"
RESULTS_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/agent_backtest_results.json"
INTERMEDIATE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_intermediate.json"

# Target leagues
LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}

SEASONS = [2023, 2024]
MATCHES_PER_LEAGUE_SEASON = 20  # Reduced to stay within API limits

# Import agents
import sys
sys.path.insert(0, "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor")

from agents.base_agent import BaseAgent, AgentReport, AgentPrediction
from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent_v3 import StatsAgentV3
from agents.market_agent import MarketAgent
from agents.value_agent_v2 import ValueAgentV2
from agents.context_agent import ContextAgent

from agents.player_intel_agents import (
    InjuryAgent, FatigueAgent, KeyPlayerAgent, GoalkeeperAgent
)
from agents.tactical_agents import (
    TacticalAgent, SetPieceAgent, DefensiveProfileAgent, AttackingProfileAgent
)
from agents.situational_agents import (
    StakesAgent, RivalryIntensityAgent, RefereeAgent, VenueAgent, WeatherAgent,
    MomentumAgent, ManagerAgent, MediaPressureAgent, RestDaysAgent
)
from agents.live_intel_agents import (
    LineupAgent, PlayerNewsAgent, ScheduleContextAgent, HistoricalOddsAgent
)


@dataclass
class MatchRecord:
    """Actual match result"""
    match_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    league: str
    season: int
    date: str
    home_id: Optional[int] = None
    away_id: Optional[int] = None


@dataclass
class AgentPredictionRecord:
    """One agent's prediction on a market"""
    agent_name: str
    match_id: int
    market: str
    predicted_outcome: str
    probability: float
    confidence: float
    correct: Optional[bool] = None
    notes: str = ""


class APICache:
    """Simple file-based cache for API responses"""
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.cache = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}

    def save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def get(self, key: str):
        return self.cache.get(key)

    def set(self, key: str, value):
        self.cache[key] = value
        self.save()


class BacktestFramework:
    """Main backtest coordinator"""

    def __init__(self):
        self.cache = APICache(CACHE_FILE)
        self.matches: List[MatchRecord] = []
        self.predictions: List[AgentPredictionRecord] = []
        self.agents = self._initialize_agents()
        self.headers = {"x-apisports-key": API_KEY}
        self.rate_limit_delay = 0.65  # ~92 req/min
        self.form_cache = {}  # Cache computed form to avoid recalculation
        self.stats_cache = {}  # Cache team stats

    def _initialize_agents(self) -> Dict[str, Any]:
        """Instantiate all 27 agents"""
        agents = {}

        # Original 6 (BaseAgent style)
        agents["FormAgent"] = FormAgent()
        agents["HistoricalAgent"] = HistoricalAgent()
        agents["StatsAgentV3"] = StatsAgentV3()
        agents["MarketAgent"] = MarketAgent()
        agents["ValueAgentV2"] = ValueAgentV2()
        agents["ContextAgent"] = ContextAgent()

        # Player Intel (4)
        agents["InjuryAgent"] = InjuryAgent()
        agents["FatigueAgent"] = FatigueAgent()
        agents["KeyPlayerAgent"] = KeyPlayerAgent()
        agents["GoalkeeperAgent"] = GoalkeeperAgent()

        # Tactical (4)
        agents["TacticalAgent"] = TacticalAgent()
        agents["SetPieceAgent"] = SetPieceAgent()
        agents["DefensiveProfileAgent"] = DefensiveProfileAgent()
        agents["AttackingProfileAgent"] = AttackingProfileAgent()

        # Situational (9)
        agents["StakesAgent"] = StakesAgent()
        agents["RivalryIntensityAgent"] = RivalryIntensityAgent()
        agents["RefereeAgent"] = RefereeAgent()
        agents["VenueAgent"] = VenueAgent()
        agents["WeatherAgent"] = WeatherAgent()
        agents["MomentumAgent"] = MomentumAgent()
        agents["ManagerAgent"] = ManagerAgent()
        agents["MediaPressureAgent"] = MediaPressureAgent()
        agents["RestDaysAgent"] = RestDaysAgent()

        # Live Intel (4)
        agents["LineupAgent"] = LineupAgent()
        agents["PlayerNewsAgent"] = PlayerNewsAgent()
        agents["ScheduleContextAgent"] = ScheduleContextAgent()
        agents["HistoricalOddsAgent"] = HistoricalOddsAgent()

        print(f"Initialized {len(agents)} agents")
        return agents

    def api_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with caching and rate limiting"""
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"

        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        time.sleep(self.rate_limit_delay)
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self.cache.set(cache_key, data)
            return data
        except Exception as e:
            print(f"API Error on {endpoint}: {e}")
            return {"response": []}

    def fetch_matches(self) -> List[MatchRecord]:
        """Fetch finished matches from all leagues for target seasons"""
        print("\n=== FETCHING MATCHES ===")
        matches = []

        for league_name, league_id in LEAGUES.items():
            for season in SEASONS:
                print(f"Fetching {league_name} {season}...")

                # Strategy: fetch matches in date ranges to get representative sample
                season_start = f"{season}-08-01"
                season_end = f"{season}-12-31"

                data = self.api_request("/fixtures", {
                    "league": league_id,
                    "season": season,
                    "status": "FT",
                    "from": season_start,
                    "to": season_end,
                })

                fixtures = data.get("response", [])[:MATCHES_PER_LEAGUE_SEASON]

                for fixture in fixtures:
                    try:
                        # Extract team IDs directly from fixture data
                        home_id = fixture["teams"]["home"]["id"]
                        away_id = fixture["teams"]["away"]["id"]

                        match = MatchRecord(
                            match_id=fixture["fixture"]["id"],
                            home_team=fixture["teams"]["home"]["name"],
                            away_team=fixture["teams"]["away"]["name"],
                            home_score=fixture["goals"]["home"],
                            away_score=fixture["goals"]["away"],
                            league=league_name,
                            season=season,
                            date=fixture["fixture"]["date"]
                        )
                        # Store team IDs for later use
                        match.home_id = home_id
                        match.away_id = away_id
                        matches.append(match)
                    except Exception as e:
                        print(f"Error parsing fixture: {e}")

        print(f"Fetched {len(matches)} matches total")
        return matches

    def fetch_team_stats(self, team_id: int, season: int, league_id: int) -> Dict:
        """Fetch team statistics for a season"""
        cache_key = f"stats:{team_id}:{season}:{league_id}"
        if cache_key in self.stats_cache:
            return self.stats_cache[cache_key]

        data = self.api_request("/teams/statistics", {
            "league": league_id,
            "season": season,
            "team": team_id,
        })
        result = data.get("response", {})
        self.stats_cache[cache_key] = result
        return result

    def fetch_h2h(self, home_id: int, away_id: int) -> List[Dict]:
        """Fetch head-to-head history"""
        data = self.api_request("/fixtures/headtohead", {
            "h2h": f"{home_id}-{away_id}",
            "last": 10,
        })
        return data.get("response", [])

    def fetch_team_id(self, team_name: str, season: int, league_id: int) -> Optional[int]:
        """Resolve team name to team ID"""
        data = self.api_request("/teams", {
            "league": league_id,
            "season": season,
            "search": team_name,
        })
        teams = data.get("response", [])
        if teams:
            return teams[0]["team"]["id"]
        return None

    def compute_form(self, team_id: int, season: int, league_id: int, before_date: str) -> Dict:
        """Compute recent form stats for a team"""
        cache_key = f"{team_id}:{season}:{league_id}"
        if cache_key in self.form_cache:
            return self.form_cache[cache_key]

        # Fetch last 10 matches
        data = self.api_request("/fixtures", {
            "team": team_id,
            "season": season,
            "status": "FT",
            "last": 10,
        })

        fixtures = data.get("response", [])
        if not fixtures:
            result = self._default_form()
            self.form_cache[cache_key] = result
            return result

        goals_scored = 0
        goals_conceded = 0
        wins = 0
        draws = 0
        losses = 0
        form_string = ""

        for fixture in fixtures:
            if fixture["fixture"]["date"] >= before_date:
                continue  # Skip matches after the target match

            home_goals = fixture["goals"]["home"]
            away_goals = fixture["goals"]["away"]

            if fixture["teams"]["home"]["id"] == team_id:
                goals_scored += home_goals
                goals_conceded += away_goals
                if home_goals > away_goals:
                    wins += 1
                    form_string = "W" + form_string
                elif home_goals == away_goals:
                    draws += 1
                    form_string = "D" + form_string
                else:
                    losses += 1
                    form_string = "L" + form_string
            else:
                goals_scored += away_goals
                goals_conceded += home_goals
                if away_goals > home_goals:
                    wins += 1
                    form_string = "W" + form_string
                elif away_goals == home_goals:
                    draws += 1
                    form_string = "D" + form_string
                else:
                    losses += 1
                    form_string = "L" + form_string

        num_matches = len(fixtures)
        result = {
            "goals_scored_avg": goals_scored / max(num_matches, 1),
            "goals_conceded_avg": goals_conceded / max(num_matches, 1),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "form_string": form_string[:5],  # Last 5 results
            "matches_played": num_matches,
            "corners_avg": 4.5,  # Default fallback
            "total_matches": num_matches,
        }
        self.form_cache[cache_key] = result
        return result

    def _default_form(self) -> Dict:
        """Default form when no data available"""
        return {
            "goals_scored_avg": 1.3,
            "goals_conceded_avg": 1.2,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "form_string": "DDDDD",
            "matches_played": 0,
        }

    def prepare_match_data(self, match: MatchRecord) -> Tuple[Dict, Dict, Dict, Dict, Dict, Dict]:
        """Prepare all data needed for agent analysis"""
        match_data = {
            "match_id": match.match_id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "league": match.league,
            "season": match.season,
            "date": match.date,
        }

        # Use team IDs from fixture or fallback to resolution
        home_id = match.home_id
        away_id = match.away_id

        if not home_id or not away_id:
            print(f"Could not get team IDs for {match.home_team} vs {match.away_team}")
            return match_data, self._default_form(), self._default_form(), {}, {}, {}

        # Fetch data
        home_form = self.compute_form(home_id, match.season, LEAGUES[match.league], match.date)
        away_form = self.compute_form(away_id, match.season, LEAGUES[match.league], match.date)
        h2h = self.fetch_h2h(home_id, away_id)
        home_stats = self.fetch_team_stats(home_id, match.season, LEAGUES[match.league])
        away_stats = self.fetch_team_stats(away_id, match.season, LEAGUES[match.league])

        return match_data, home_form, away_form, h2h, home_stats, away_stats

    def run_agent(self, agent_name: str, agent: Any, match_data: Dict,
                  home_form: Dict, away_form: Dict, h2h: Dict,
                  home_stats: Dict, away_stats: Dict) -> List[Dict]:
        """Run a single agent and extract predictions"""
        predictions = []

        try:
            result = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats)

            # Handle old-style AgentReport
            if isinstance(result, AgentReport):
                for pred in result.predictions:
                    predictions.append({
                        "market": pred.market,
                        "outcome": pred.outcome,
                        "probability": pred.probability,
                        "confidence": pred.confidence,
                    })

            # Handle new-style dict
            elif isinstance(result, dict) and "predictions" in result:
                pred_dict = result["predictions"]

                # Extract predictions from dict
                if isinstance(pred_dict, dict):
                    confidence = result.get("confidence", 0.5)

                    # For numeric predictions that look like probabilities/factors
                    for key, value in pred_dict.items():
                        if isinstance(value, (int, float)) and 0 <= value <= 1:
                            # Binary predictions (0-1 range)
                            predictions.append({
                                "market": key,
                                "outcome": "positive" if value > 0.5 else "negative",
                                "probability": value,
                                "confidence": confidence,
                            })
                        elif isinstance(value, (int, float)):
                            # Normalize to 0-1 range if needed
                            prob = min(1.0, max(0.0, value / 10.0 if value > 1 else value))
                            predictions.append({
                                "market": key,
                                "outcome": "positive" if prob > 0.5 else "negative",
                                "probability": prob,
                                "confidence": confidence,
                            })

                elif isinstance(pred_dict, list):
                    # If it's a list of dicts, use them directly
                    for pred in pred_dict:
                        if isinstance(pred, dict) and "probability" in pred:
                            predictions.append(pred)

        except Exception as e:
            pass
            # Silently catch errors - agents may not have complete data

        return predictions

    def determine_1x2_winner(self, match: MatchRecord) -> str:
        """Determine actual 1X2 result"""
        if match.home_score > match.away_score:
            return "Home"
        elif match.home_score < match.away_score:
            return "Away"
        else:
            return "Draw"

    def determine_goals_ou25(self, match: MatchRecord) -> str:
        """Determine actual Over/Under 2.5"""
        total = match.home_score + match.away_score
        return "Over" if total > 2.5 else "Under"

    def determine_btts(self, match: MatchRecord) -> str:
        """Determine actual BTTS"""
        return "Yes" if match.home_score > 0 and match.away_score > 0 else "No"

    def evaluate_prediction(self, agent_name: str, match: MatchRecord,
                           prediction: Dict) -> Optional[bool]:
        """Check if a prediction was correct"""
        market = prediction["market"].lower()
        outcome = prediction["outcome"].lower()

        # 1X2
        if "1x2" in market or "match_winner" in market or "draw" in market:
            actual = self.determine_1x2_winner(match).lower()
            # Handle various outcome formats
            if "home" in outcome or "1" in outcome or match.home_team.lower() in outcome:
                return actual == "home"
            elif "away" in outcome or "2" in outcome or match.away_team.lower() in outcome:
                return actual == "away"
            elif "draw" in outcome or "x" in outcome or "d" in outcome:
                return actual == "draw"

        # Over/Under 2.5
        elif "over_under" in market or "goals" in market:
            actual = self.determine_goals_ou25(match)
            if "over" in outcome:
                return actual == "Over"
            elif "under" in outcome:
                return actual == "Under"

        # BTTS
        elif "btts" in market:
            actual = self.determine_btts(match)
            if "yes" in outcome:
                return actual == "Yes"
            elif "no" in outcome:
                return actual == "No"

        return None

    def run_backtest(self):
        """Execute full backtest"""
        print("\n" + "="*80)
        print("FOOTBALL AGENT BACKTEST FRAMEWORK")
        print("="*80)

        # Fetch matches
        self.matches = self.fetch_matches()
        if not self.matches:
            print("ERROR: No matches fetched!")
            return

        # Process each match
        print(f"\n=== PROCESSING {len(self.matches)} MATCHES ===")
        for i, match in enumerate(self.matches):
            print(f"\n[{i+1}/{len(self.matches)}] {match.home_team} vs {match.away_team} ({match.date})")

            # Prepare data
            match_data, home_form, away_form, h2h, home_stats, away_stats = \
                self.prepare_match_data(match)

            # Run each agent
            for agent_name, agent in self.agents.items():
                predictions = self.run_agent(
                    agent_name, agent, match_data, home_form, away_form, h2h, home_stats, away_stats
                )

                # Record predictions
                for pred in predictions:
                    is_correct = self.evaluate_prediction(agent_name, match, pred)

                    record = AgentPredictionRecord(
                        agent_name=agent_name,
                        match_id=match.match_id,
                        market=pred["market"],
                        predicted_outcome=pred["outcome"],
                        probability=pred["probability"],
                        confidence=pred["confidence"],
                        correct=is_correct,
                    )
                    self.predictions.append(record)

            # Save intermediate results
            if (i + 1) % 10 == 0:
                self.save_intermediate_results()

        # Evaluate results
        self.evaluate_results()

    def save_intermediate_results(self):
        """Save intermediate results for recovery"""
        data = {
            "matches": [asdict(m) for m in self.matches],
            "predictions": [asdict(p) for p in self.predictions],
            "timestamp": datetime.now().isoformat(),
        }
        with open(INTERMEDIATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.predictions)} predictions to intermediate file")

    def evaluate_results(self):
        """Compute per-agent statistics"""
        print("\n" + "="*80)
        print("EVALUATING RESULTS")
        print("="*80)

        # Organize by agent
        agent_preds = defaultdict(list)
        for pred in self.predictions:
            agent_preds[pred.agent_name].append(pred)

        results = {}

        for agent_name in sorted(self.agents.keys()):
            preds = agent_preds[agent_name]
            if not preds:
                continue

            # Filter predictions with evaluation
            evaluated = [p for p in preds if p.correct is not None]

            if not evaluated:
                results[agent_name] = {
                    "status": "No evaluated predictions",
                    "total_predictions": len(preds),
                }
                continue

            correct = sum(1 for p in evaluated if p.correct)
            accuracy = correct / len(evaluated) if evaluated else 0

            # Calibration: group by probability decile
            calibration = self._compute_calibration(evaluated)

            # Confidence-weighted accuracy
            conf_weighted = sum(p.confidence for p in evaluated if p.correct) / \
                           sum(p.confidence for p in evaluated) if evaluated else 0

            # By market
            by_market = defaultdict(lambda: {"total": 0, "correct": 0})
            for p in evaluated:
                by_market[p.market]["total"] += 1
                if p.correct:
                    by_market[p.market]["correct"] += 1

            market_acc = {
                market: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                for market, stats in by_market.items()
            }

            # By league
            by_league = defaultdict(lambda: {"total": 0, "correct": 0})
            for p in evaluated:
                # Find match
                match = next((m for m in self.matches if m.match_id == p.match_id), None)
                if match:
                    by_league[match.league]["total"] += 1
                    if p.correct:
                        by_league[match.league]["correct"] += 1

            league_acc = {
                league: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                for league, stats in by_league.items()
            }

            # Simulated ROI (assuming fair odds = 1/probability)
            roi = self._compute_roi(evaluated)

            results[agent_name] = {
                "total_predictions": len(preds),
                "evaluated_predictions": len(evaluated),
                "accuracy": round(accuracy, 4),
                "confidence_weighted_accuracy": round(conf_weighted, 4),
                "calibration": calibration,
                "by_market": {k: round(v, 4) for k, v in market_acc.items()},
                "by_league": {k: round(v, 4) for k, v in league_acc.items()},
                "roi": round(roi, 4),
                "avg_confidence": round(sum(p.confidence for p in evaluated) / len(evaluated), 4),
                "avg_probability": round(sum(p.probability for p in evaluated) / len(evaluated), 4),
            }

        # Save results
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_matches": len(self.matches),
            "total_predictions": len(self.predictions),
            "agents": results,
        }

        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to {RESULTS_FILE}")
        self.print_summary(results)

    def _compute_calibration(self, predictions: List[AgentPredictionRecord]) -> Dict:
        """Compute calibration across probability deciles"""
        deciles = defaultdict(lambda: {"total": 0, "correct": 0})

        for pred in predictions:
            decile = int(pred.probability * 10) * 0.1  # Round to decile
            deciles[decile]["total"] += 1
            if pred.correct:
                deciles[decile]["correct"] += 1

        return {
            f"{decile:.1f}": {
                "predicted": decile,
                "actual": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "count": stats["total"],
            }
            for decile, stats in sorted(deciles.items())
        }

    def _compute_roi(self, predictions: List[AgentPredictionRecord],
                     stake_per_pred: float = 1.0) -> float:
        """Compute ROI assuming we bet at fair odds (1/probability)"""
        total_stake = len(predictions) * stake_per_pred
        total_return = 0

        for pred in predictions:
            if pred.probability > 0:
                odds = 1 / pred.probability
                if pred.correct:
                    total_return += odds * stake_per_pred

        roi = (total_return - total_stake) / total_stake if total_stake > 0 else 0
        return roi

    def print_summary(self, results: Dict):
        """Print summary statistics"""
        print("\n" + "="*80)
        print("AGENT PERFORMANCE SUMMARY")
        print("="*80)

        # Sort by accuracy
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].get("accuracy", -1),
            reverse=True
        )

        print(f"\n{'Agent':<30} {'Accuracy':<12} {'Predictions':<15} {'ROI':<10} {'Avg Conf':<10}")
        print("-" * 80)

        for agent_name, stats in sorted_results:
            if "status" in stats:
                print(f"{agent_name:<30} {stats['status']}")
            else:
                acc = stats.get("accuracy", 0)
                preds = stats.get("evaluated_predictions", 0)
                roi = stats.get("roi", 0)
                conf = stats.get("avg_confidence", 0)
                print(f"{agent_name:<30} {acc:>11.2%} {preds:>14} {roi:>9.2%} {conf:>9.2%}")


if __name__ == "__main__":
    backtest = BacktestFramework()
    backtest.run_backtest()
