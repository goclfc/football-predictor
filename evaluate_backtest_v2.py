"""
Advanced backtest evaluation with meta-prediction synthesis
Converts agent-specific metrics into match outcome predictions
"""

import json
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
import math

INTERMEDIATE_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/backtest_intermediate.json"
RESULTS_FILE = "/sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor/agent_backtest_results.json"


class AdvancedBacktestEvaluator:
    """Advanced evaluator that synthesizes agent predictions into match outcomes"""

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

    def determine_actual_outcome(self, match: Dict) -> Dict:
        """Determine all actual outcomes for a match"""
        home_score = match["home_score"]
        away_score = match["away_score"]
        total_goals = home_score + away_score

        return {
            "1x2": "home" if home_score > away_score else ("away" if away_score > home_score else "draw"),
            "over_2.5": "over" if total_goals > 2.5 else "under",
            "btts": "yes" if home_score > 0 and away_score > 0 else "no",
            "home_goals": home_score,
            "away_goals": away_score,
            "total_goals": total_goals,
        }

    def synthesize_1x2_from_metrics(self, agent_name: str, match_id: int,
                                     agent_preds: List[Dict]) -> Optional[Tuple[str, float]]:
        """
        Synthesize a 1X2 prediction from various agent metrics.
        Returns (prediction: "home"/"away"/"draw", confidence: float)
        """

        # Collect all metric signals for home/away advantage
        home_signals = []
        away_signals = []
        confidence = 0.5

        for pred in agent_preds:
            market = pred["market"].lower()
            probability = pred["probability"]
            outcome = pred["predicted_outcome"].lower()
            conf = pred["confidence"]

            # Attacking/defensive metrics -> goal expectation
            if "xg_home" in market:
                # Higher xG for home = home advantage
                home_signals.append((probability, conf))
            elif "xg_away" in market:
                away_signals.append((probability, conf))

            # Clean sheet -> defensive strength
            elif "clean_sheet" in market and "home" in market:
                if "positive" in outcome:
                    home_signals.append((probability * 0.7, conf * 0.7))  # Weak signal
            elif "clean_sheet" in market and "away" in market:
                if "positive" in outcome:
                    away_signals.append((probability * 0.7, conf * 0.7))

            # Fatigue -> reduced performance (away team often more fatigued)
            elif "fatigue" in market and "away" in market:
                if "positive" not in outcome:  # Fatigued = problem
                    away_signals.append((1 - probability, conf * 0.6))
            elif "fatigue" in market and "home" in market:
                if "positive" not in outcome:
                    home_signals.append((1 - probability, conf * 0.6))

            # Injury impact
            elif "injury_impact" in market:
                if "home" in market:
                    away_signals.append((probability, conf * 0.5))  # Home injuries help away
                else:
                    home_signals.append((probability, conf * 0.5))  # Away injuries help home

            # Motivation/stakes/momentum
            elif "motivation" in market:
                if "home" in market and "positive" not in outcome:
                    away_signals.append((probability, conf * 0.6))
                elif "away" in market and "positive" not in outcome:
                    home_signals.append((probability, conf * 0.6))

        # Aggregate signals (weighted average)
        home_score = 0.5  # Base
        away_score = 0.5

        if home_signals:
            home_avg = sum(sig[0] for sig in home_signals) / len(home_signals)
            home_conf = sum(sig[1] for sig in home_signals) / len(home_signals)
            home_score += (home_avg - 0.5) * home_conf * 0.3

        if away_signals:
            away_avg = sum(sig[0] for sig in away_signals) / len(away_signals)
            away_conf = sum(sig[1] for sig in away_signals) / len(away_signals)
            away_score += (away_avg - 0.5) * away_conf * 0.3

        # Normalize
        total = home_score + away_score
        if total == 0:
            return None
        home_prob = home_score / total
        away_prob = away_score / total

        # Determine prediction
        if abs(home_prob - away_prob) < 0.15:
            prediction = "draw"
            confidence = 0.4 + (sum(p[1] for p in home_signals + away_signals) /
                               max(len(home_signals + away_signals), 1) * 0.3)
        elif home_prob > away_prob:
            prediction = "home"
            confidence = min(0.95, home_prob)
        else:
            prediction = "away"
            confidence = min(0.95, away_prob)

        return (prediction, confidence)

    def evaluate_results(self):
        """Compute per-agent statistics using synthesis"""
        print("\n" + "="*80)
        print("ADVANCED BACKTEST EVALUATION WITH META-PREDICTION SYNTHESIS")
        print("="*80)

        # Match map
        match_map = {m["match_id"]: m for m in self.matches}

        # Organize by agent
        agent_preds = defaultdict(list)
        for pred in self.predictions:
            agent_preds[pred["agent_name"]].append(pred)

        results = {}

        for agent_name in sorted(agent_preds.keys()):
            preds = agent_preds[agent_name]
            if not preds:
                continue

            # Group predictions by match
            preds_by_match = defaultdict(list)
            for pred in preds:
                preds_by_match[pred["match_id"]].append(pred)

            # Synthesize 1X2 predictions for each match
            evaluated = []
            for match_id, match_agent_preds in preds_by_match.items():
                match = match_map.get(match_id)
                if not match:
                    continue

                # Try synthesis
                result = self.synthesize_1x2_from_metrics(agent_name, match_id, match_agent_preds)
                if result is None:
                    continue

                prediction, confidence = result
                actual = self.determine_actual_outcome(match)
                is_correct = actual["1x2"] == prediction

                evaluated.append({
                    "prediction": prediction,
                    "actual": actual["1x2"],
                    "correct": is_correct,
                    "confidence": confidence,
                    "probability": confidence,
                    "match_id": match_id,
                    "league": match["league"],
                })

            if not evaluated:
                results[agent_name] = {
                    "status": f"No synthesizable predictions (had {len(preds)} total)",
                    "total_predictions": len(preds),
                }
                continue

            correct = sum(1 for e in evaluated if e["correct"])
            accuracy = correct / len(evaluated) if evaluated else 0

            # By league
            by_league = defaultdict(lambda: {"total": 0, "correct": 0})
            for e in evaluated:
                league = e["league"]
                by_league[league]["total"] += 1
                if e["correct"]:
                    by_league[league]["correct"] += 1

            league_acc = {
                league: stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                for league, stats in by_league.items()
            }

            # Calibration
            calibration = self._compute_calibration(evaluated)

            # ROI
            roi = self._compute_roi(evaluated)

            # Confidence-weighted
            conf_weighted = sum(
                e["confidence"] for e in evaluated if e["correct"]
            ) / sum(e["confidence"] for e in evaluated) if evaluated else 0

            results[agent_name] = {
                "total_predictions": len(preds),
                "synthesized_1x2_predictions": len(evaluated),
                "accuracy": round(accuracy, 4),
                "confidence_weighted_accuracy": round(conf_weighted, 4),
                "by_league": {k: round(v, 4) for k, v in league_acc.items()},
                "roi": round(roi, 4),
                "avg_confidence": round(
                    sum(e["confidence"] for e in evaluated) / len(evaluated), 4
                ) if evaluated else 0,
                "calibration": calibration,
            }

        # Save results
        output = {
            "evaluation_method": "meta_prediction_synthesis",
            "total_matches": len(self.matches),
            "total_predictions": len(self.predictions),
            "agents": results,
        }

        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to {RESULTS_FILE}")
        self.print_summary(results)

    def _compute_calibration(self, evaluated: List[Dict]) -> Dict:
        """Compute calibration"""
        deciles = defaultdict(lambda: {"total": 0, "correct": 0})

        for e in evaluated:
            prob = e["confidence"]
            decile = int(prob * 10) * 0.1
            deciles[decile]["total"] += 1
            if e["correct"]:
                deciles[decile]["correct"] += 1

        return {
            f"{decile:.1f}": {
                "predicted": decile,
                "actual": round(stats["correct"] / stats["total"], 3) if stats["total"] > 0 else 0,
                "count": stats["total"],
            }
            for decile, stats in sorted(deciles.items())
        }

    def _compute_roi(self, evaluated: List[Dict], stake: float = 1.0) -> float:
        """Compute ROI"""
        total_stake = len(evaluated) * stake
        total_return = 0

        for e in evaluated:
            if e["confidence"] > 0:
                odds = 1 / e["confidence"]
                if e["correct"]:
                    total_return += odds * stake

        roi = (total_return - total_stake) / total_stake if total_stake > 0 else 0
        return roi

    def print_summary(self, results: Dict):
        """Print summary"""
        print("\n" + "="*80)
        print("AGENT PERFORMANCE SUMMARY (1X2 META-PREDICTIONS)")
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
                preds = stats.get("synthesized_1x2_predictions", 0)
                roi = stats.get("roi", 0)
                conf = stats.get("avg_confidence", 0)
                print(f"{agent_name:<30} {acc:>11.2%} {preds:>14} {roi:>9.2%} {conf:>9.2%}")

        # Summary
        evaluated_agents = [s for s in results.values() if "accuracy" in s]
        if evaluated_agents:
            avg_accuracy = sum(s["accuracy"] for s in evaluated_agents) / len(evaluated_agents)
            print("\n" + "-" * 80)
            print(f"Average accuracy: {avg_accuracy:.2%}")
            print(f"Agents with evaluable predictions: {len(evaluated_agents)}/{len(results)}")

        # Top performers
        print("\n" + "="*80)
        print("TOP 10 AGENTS BY ACCURACY")
        print("="*80)
        for i, (agent_name, stats) in enumerate(sorted_results[:10], 1):
            if "accuracy" in stats:
                acc = stats.get("accuracy", 0)
                preds = stats.get("synthesized_1x2_predictions", 0)
                roi = stats.get("roi", 0)
                print(f"{i}. {agent_name}")
                print(f"   Accuracy: {acc:.2%}, Predictions: {preds}, ROI: {roi:.2%}")
                if stats.get("by_league"):
                    print(f"   By League: {', '.join(f'{l}={a:.1%}' for l, a in stats['by_league'].items())}")


if __name__ == "__main__":
    evaluator = AdvancedBacktestEvaluator()
    evaluator.evaluate_results()
