"""
Focused backtest on real 1X2 predictions from older agents that provide them
"""

import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import sys

sys.path.insert(0, "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor")

API_KEY = "480b0d1da4cd81135649f1a77eb6465c"
BASE_URL = "https://v3.football.api-sports.io"

# Use cache from previous run
CACHE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_cache.json"
INTERMEDIATE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_intermediate.json"
RESULTS_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/agent_backtest_final.json"


class FocusedBacktest:
    """Focused evaluation on direct 1X2 predictions"""

    def __init__(self):
        self.matches = []
        self.predictions = []
        self.load_intermediate()

    def load_intermediate(self):
        """Load previous backtest data"""
        try:
            with open(INTERMEDIATE_FILE, 'r') as f:
                data = json.load(f)
                self.matches = data.get('matches', [])
                self.predictions = data.get('predictions', [])
                print(f"Loaded {len(self.matches)} matches, {len(self.predictions)} predictions")
        except Exception as e:
            print(f"Error loading: {e}")

    def determine_actual_1x2(self, match: Dict) -> str:
        """Get actual 1X2 result"""
        if match["home_score"] > match["away_score"]:
            return "home"
        elif match["away_score"] > match["home_score"]:
            return "away"
        else:
            return "draw"

    def determine_actual_goals_ou25(self, match: Dict) -> str:
        """Get actual Over/Under 2.5"""
        total = match["home_score"] + match["away_score"]
        return "over" if total > 2.5 else "under"

    def determine_actual_btts(self, match: Dict) -> str:
        """Get actual BTTS"""
        return "yes" if match["home_score"] > 0 and match["away_score"] > 0 else "no"

    def normalize_prediction(self, outcome: str) -> Optional[str]:
        """Normalize outcome to standard format"""
        outcome_lower = str(outcome).lower().strip()

        # 1X2
        if any(x in outcome_lower for x in ["home", "1 -", "manchester city", "manchester united",
                                              "arsenal", "liverpool", "tottenham"]):
            return "home"
        if any(x in outcome_lower for x in ["away", "2 -", "draw", "x", " d"]):
            if "draw" in outcome_lower or " x" in outcome_lower or " d" in outcome_lower:
                return "draw"
            return "away"

        # Over/Under
        if "over" in outcome_lower:
            return "over"
        if "under" in outcome_lower:
            return "under"

        # BTTS
        if "yes" in outcome_lower:
            return "yes"
        if "no" in outcome_lower:
            return "no"

        return None

    def evaluate_direct_predictions(self):
        """Evaluate all predictions that map to actual markets"""
        print("\n" + "="*80)
        print("FOCUSED EVALUATION: DIRECT MARKET PREDICTIONS")
        print("="*80)

        match_map = {m["match_id"]: m for m in self.matches}

        agent_preds = defaultdict(list)
        for pred in self.predictions:
            agent_preds[pred["agent_name"]].append(pred)

        results = {}

        for agent_name in sorted(agent_preds.keys()):
            preds = agent_preds[agent_name]

            evaluated = []
            for pred in preds:
                match = match_map.get(pred["match_id"])
                if not match:
                    continue

                market = pred["market"].lower()
                outcome = pred["predicted_outcome"]

                is_correct = None

                # 1X2 prediction
                if "1x2" in market or "match_winner" in market:
                    prediction = self.normalize_prediction(outcome)
                    if prediction in ["home", "away", "draw"]:
                        actual = self.determine_actual_1x2(match)
                        is_correct = actual == prediction

                # Over/Under 2.5
                elif "over_under" in market and "2.5" in market:
                    if "over" in outcome.lower():
                        actual = self.determine_actual_goals_ou25(match)
                        is_correct = actual == "over"
                    elif "under" in outcome.lower():
                        actual = self.determine_actual_goals_ou25(match)
                        is_correct = actual == "under"

                # BTTS
                elif "btts" in market:
                    if "yes" in outcome.lower():
                        actual = self.determine_actual_btts(match)
                        is_correct = actual == "yes"
                    elif "no" in outcome.lower():
                        actual = self.determine_actual_btts(match)
                        is_correct = actual == "no"

                if is_correct is not None:
                    evaluated.append({
                        "market": market,
                        "prediction": outcome,
                        "correct": is_correct,
                        "confidence": pred["confidence"],
                        "probability": pred["probability"],
                        "league": match["league"],
                    })

            if not evaluated:
                results[agent_name] = {
                    "status": "No direct market predictions",
                    "total_predictions": len(preds),
                }
                continue

            correct = sum(1 for e in evaluated if e["correct"])
            accuracy = correct / len(evaluated)

            # By market
            by_market = defaultdict(lambda: {"total": 0, "correct": 0})
            for e in evaluated:
                by_market[e["market"]]["total"] += 1
                if e["correct"]:
                    by_market[e["market"]]["correct"] += 1

            # By league
            by_league = defaultdict(lambda: {"total": 0, "correct": 0})
            for e in evaluated:
                by_league[e["league"]]["total"] += 1
                if e["correct"]:
                    by_league[e["league"]]["correct"] += 1

            # ROI
            roi = self._compute_roi(evaluated)

            results[agent_name] = {
                "total_predictions": len(preds),
                "evaluable_predictions": len(evaluated),
                "accuracy": round(accuracy, 4),
                "by_market": {
                    market: round(stats["correct"] / stats["total"] if stats["total"] > 0 else 0, 4)
                    for market, stats in by_market.items()
                },
                "by_league": {
                    league: round(stats["correct"] / stats["total"] if stats["total"] > 0 else 0, 4)
                    for league, stats in by_league.items()
                },
                "roi": round(roi, 4),
                "avg_confidence": round(sum(e["confidence"] for e in evaluated) / len(evaluated), 4),
            }

        # Save
        output = {
            "method": "direct_market_prediction_evaluation",
            "timestamp": datetime.now().isoformat(),
            "total_matches": len(self.matches),
            "total_predictions": len(self.predictions),
            "agents": results,
        }

        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to {RESULTS_FILE}")
        self.print_summary(results)

    def _compute_roi(self, evaluated: List[Dict]) -> float:
        """Compute ROI"""
        total_stake = len(evaluated)
        total_return = 0

        for e in evaluated:
            prob = e["probability"]
            if prob > 0 and prob < 1:
                odds = 1 / prob
                if e["correct"]:
                    total_return += odds

        roi = (total_return - total_stake) / total_stake if total_stake > 0 else 0
        return roi

    def print_summary(self, results: Dict):
        """Print summary"""
        print("\n" + "="*80)
        print("AGENT PERFORMANCE SUMMARY")
        print("="*80)

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
                preds = stats.get("evaluable_predictions", 0)
                roi = stats.get("roi", 0)
                conf = stats.get("avg_confidence", 0)
                print(f"{agent_name:<30} {acc:>11.2%} {preds:>14} {roi:>9.2%} {conf:>9.2%}")

        # Detail by agent
        print("\n" + "="*80)
        print("DETAILED AGENT ANALYSIS")
        print("="*80)

        for agent_name, stats in sorted_results[:10]:
            if "accuracy" in stats:
                print(f"\n{agent_name}")
                print(f"  Accuracy: {stats['accuracy']:.2%}")
                print(f"  Predictions: {stats['evaluable_predictions']}/{stats['total_predictions']}")
                print(f"  ROI: {stats['roi']:.2%}")
                if stats.get("by_market"):
                    print(f"  Markets: {stats['by_market']}")
                if stats.get("by_league"):
                    print(f"  Leagues: {stats['by_league']}")


if __name__ == "__main__":
    backtest = FocusedBacktest()
    backtest.evaluate_direct_predictions()
