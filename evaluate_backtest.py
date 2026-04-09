"""
Fast evaluation script to process intermediate backtest results
"""

import json
from collections import defaultdict
from typing import List, Dict, Optional

INTERMEDIATE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_intermediate.json"
RESULTS_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/agent_backtest_results.json"


class BacktestEvaluator:
    """Evaluate backtest results from intermediate file"""

    def __init__(self):
        self.matches = []
        self.predictions = []
        self.load_intermediate()

    def load_intermediate(self):
        """Load intermediate results"""
        try:
            with open(INTERMEDIATE_FILE, 'r') as f:
                data = json.load(f)
                self.matches = data.get('matches', [])
                self.predictions = data.get('predictions', [])
                print(f"Loaded {len(self.matches)} matches and {len(self.predictions)} predictions")
        except Exception as e:
            print(f"Error loading intermediate file: {e}")

    def determine_1x2_winner(self, match: Dict) -> str:
        """Determine actual 1X2 result"""
        if match["home_score"] > match["away_score"]:
            return "Home"
        elif match["home_score"] < match["away_score"]:
            return "Away"
        else:
            return "Draw"

    def determine_goals_ou25(self, match: Dict) -> str:
        """Determine actual Over/Under 2.5"""
        total = match["home_score"] + match["away_score"]
        return "Over" if total > 2.5 else "Under"

    def determine_btts(self, match: Dict) -> str:
        """Determine actual BTTS"""
        return "Yes" if match["home_score"] > 0 and match["away_score"] > 0 else "No"

    def evaluate_prediction(self, agent_name: str, match: Dict,
                           prediction: Dict) -> Optional[bool]:
        """Check if a prediction was correct"""
        market = prediction["market"].lower()
        outcome = str(prediction["predicted_outcome"]).lower()

        # 1X2
        if "1x2" in market or "match_winner" in market or "draw" in market:
            actual = self.determine_1x2_winner(match).lower()
            if "home" in outcome or "1" in outcome or match["home_team"].lower() in outcome:
                return actual == "home"
            elif "away" in outcome or "2" in outcome or match["away_team"].lower() in outcome:
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

        # Binary positive/negative (from new agents)
        elif "injury" in market or "fatigue" in market or "lineup" in market:
            # These are binary predictions about impacts
            # probability > 0.5 = positive/yes, < 0.5 = negative/no
            # We can't really evaluate these without knowing the true impact
            # So we skip them
            return None

        return None

    def evaluate_results(self):
        """Compute per-agent statistics"""
        print("\n" + "="*80)
        print("EVALUATING BACKTEST RESULTS")
        print("="*80)

        # Match map for quick lookup
        match_map = {m["match_id"]: m for m in self.matches}

        # Organize by agent
        agent_preds = defaultdict(list)
        for pred in self.predictions:
            agent_preds[pred["agent_name"]].append(pred)

        results = {}

        for agent_name in sorted(set(p["agent_name"] for p in self.predictions)):
            preds = agent_preds[agent_name]
            if not preds:
                continue

            # Evaluate each prediction
            evaluated = []
            for pred in preds:
                match = match_map.get(pred["match_id"])
                if not match:
                    continue

                is_correct = self.evaluate_prediction(agent_name, match, pred)
                if is_correct is not None:
                    evaluated.append({
                        "prediction": pred,
                        "correct": is_correct,
                    })

            if not evaluated:
                results[agent_name] = {
                    "status": f"No evaluable predictions (had {len(preds)} total)",
                    "total_predictions": len(preds),
                }
                continue

            correct = sum(1 for e in evaluated if e["correct"])
            accuracy = correct / len(evaluated) if evaluated else 0

            # Calibration
            calibration = self._compute_calibration(evaluated)

            # Confidence-weighted accuracy
            conf_sum = sum(e["prediction"]["confidence"] for e in evaluated)
            conf_weighted = sum(
                e["prediction"]["confidence"] for e in evaluated if e["correct"]
            ) / conf_sum if conf_sum > 0 else 0

            # By market
            by_market = defaultdict(lambda: {"total": 0, "correct": 0})
            for e in evaluated:
                market = e["prediction"]["market"]
                by_market[market]["total"] += 1
                if e["correct"]:
                    by_market[market]["correct"] += 1

            market_acc = {
                market: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                for market, stats in by_market.items()
            }

            # By league
            by_league = defaultdict(lambda: {"total": 0, "correct": 0})
            for e in evaluated:
                match = match_map.get(e["prediction"]["match_id"])
                if match:
                    league = match["league"]
                    by_league[league]["total"] += 1
                    if e["correct"]:
                        by_league[league]["correct"] += 1

            league_acc = {
                league: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                for league, stats in by_league.items()
            }

            # ROI
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
                "avg_confidence": round(
                    sum(e["prediction"]["confidence"] for e in evaluated) / len(evaluated), 4
                ),
                "avg_probability": round(
                    sum(e["prediction"]["probability"] for e in evaluated) / len(evaluated), 4
                ),
            }

        # Save results
        output = {
            "timestamp": json.dumps(None)[:20],  # Simple timestamp
            "total_matches": len(self.matches),
            "total_predictions": len(self.predictions),
            "agents": results,
        }

        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to {RESULTS_FILE}")
        self.print_summary(results)

    def _compute_calibration(self, evaluated: List[Dict]) -> Dict:
        """Compute calibration across probability deciles"""
        deciles = defaultdict(lambda: {"total": 0, "correct": 0})

        for e in evaluated:
            prob = e["prediction"]["probability"]
            decile = int(prob * 10) * 0.1
            deciles[decile]["total"] += 1
            if e["correct"]:
                deciles[decile]["correct"] += 1

        return {
            f"{decile:.1f}": {
                "predicted": decile,
                "actual": stats["correct"] / stats["total"] if stats["total"] > 0 else 0,
                "count": stats["total"],
            }
            for decile, stats in sorted(deciles.items())
        }

    def _compute_roi(self, evaluated: List[Dict], stake_per_pred: float = 1.0) -> float:
        """Compute ROI assuming we bet at fair odds"""
        total_stake = len(evaluated) * stake_per_pred
        total_return = 0

        for e in evaluated:
            prob = e["prediction"]["probability"]
            if prob > 0:
                odds = 1 / prob
                if e["correct"]:
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

        # Summary statistics
        evaluated_agents = [s for s in results.values() if "accuracy" in s]
        if evaluated_agents:
            avg_accuracy = sum(s["accuracy"] for s in evaluated_agents) / len(evaluated_agents)
            print("\n" + "-" * 80)
            print(f"Average accuracy across all agents: {avg_accuracy:.2%}")
            print(f"Agents with evaluable predictions: {len(evaluated_agents)}/{len(results)}")


if __name__ == "__main__":
    evaluator = BacktestEvaluator()
    evaluator.evaluate_results()
