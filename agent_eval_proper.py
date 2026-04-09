"""
Proper Agent Evaluation — Maps agent signals to verifiable match outcomes.

Each agent produces specialized signals. This evaluator maps them to
actual match results across 200 matches from 5 leagues (2023-2024 seasons).
"""
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============================================================
# Load data
# ============================================================
with open("backtest_intermediate.json") as f:
    raw = json.load(f)

MATCHES = {m["match_id"]: m for m in raw["matches"]}
PREDICTIONS = raw["predictions"]

# Index predictions by (match_id, agent)
agent_match_preds = defaultdict(lambda: defaultdict(list))
for p in PREDICTIONS:
    agent_match_preds[p["agent_name"]][p["match_id"]].append(p)


def match_result(m):
    hs, as_ = m["home_score"], m["away_score"]
    if hs > as_:
        return "H"
    elif hs < as_:
        return "A"
    return "D"


def total_goals(m):
    return m["home_score"] + m["away_score"]


def btts(m):
    return m["home_score"] > 0 and m["away_score"] > 0


def clean_sheet_home(m):
    return m["away_score"] == 0


def clean_sheet_away(m):
    return m["home_score"] == 0


# ============================================================
# Per-agent evaluation logic
# ============================================================

@dataclass
class AgentEval:
    name: str
    total_matches: int = 0
    # Direct testable predictions
    testable_predictions: int = 0
    correct_predictions: int = 0
    # Category breakdowns
    categories: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {"total": 0, "correct": 0, "details": []}))
    # Calibration bins
    calibration: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {"predicted_prob": 0.0, "actual_hit": 0, "count": 0}))
    # By league
    by_league: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {"total": 0, "correct": 0}))
    # Signal correlation
    signal_correlation: float = 0.0
    useful_signal_rate: float = 0.0
    notes: List[str] = field(default_factory=list)


def evaluate_attacking_profile(agent_preds, match):
    """AttackingProfileAgent: xg, first_goal_prob, btts_probability"""
    results = []
    for p in agent_preds:
        if p["market"] == "btts_probability":
            predicted_btts = p["probability"] > 0.5
            actual_btts = btts(match)
            results.append({
                "category": "BTTS",
                "predicted": predicted_btts,
                "actual": actual_btts,
                "correct": predicted_btts == actual_btts,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "xg_home":
            # Higher xG home → more likely home scores
            home_scored = match["home_score"] > 0
            pred_home_scores = p["probability"] > 0.3  # xG > 0.3 means expected to score
            results.append({
                "category": "Home Scoring",
                "predicted": pred_home_scores,
                "actual": home_scored,
                "correct": pred_home_scores == home_scored,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "xg_away":
            away_scored = match["away_score"] > 0
            pred_away_scores = p["probability"] > 0.3
            results.append({
                "category": "Away Scoring",
                "predicted": pred_away_scores,
                "actual": away_scored,
                "correct": pred_away_scores == away_scored,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "first_goal_prob_home":
            # If home first goal prob > 0.5, predict home scores first
            pred_home_first = p["probability"] > 0.5
            # Approximate: if home won or drew with goals, home likely scored first
            actual_home_first = match["home_score"] >= match["away_score"] and match["home_score"] > 0
            results.append({
                "category": "First Goal",
                "predicted": pred_home_first,
                "actual": actual_home_first,
                "correct": pred_home_first == actual_home_first,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_defensive_profile(agent_preds, match):
    """DefensiveProfileAgent: clean_sheet_prob, vulnerability"""
    results = []
    for p in agent_preds:
        if p["market"] == "clean_sheet_prob_home":
            pred_cs = p["probability"] > 0.35  # predict clean sheet if prob > 35%
            actual_cs = clean_sheet_home(match)
            results.append({
                "category": "Clean Sheet Home",
                "predicted": pred_cs,
                "actual": actual_cs,
                "correct": pred_cs == actual_cs,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "clean_sheet_prob_away":
            pred_cs = p["probability"] > 0.35
            actual_cs = clean_sheet_away(match)
            results.append({
                "category": "Clean Sheet Away",
                "predicted": pred_cs,
                "actual": actual_cs,
                "correct": pred_cs == actual_cs,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_goalkeeper(agent_preds, match):
    """GoalkeeperAgent: clean_sheet adjustments, GK ratings"""
    results = []
    for p in agent_preds:
        if p["market"] == "clean_sheet_adj_home":
            # Higher adj = more likely clean sheet
            pred_cs = p["probability"] > 0.25
            actual_cs = clean_sheet_home(match)
            results.append({
                "category": "GK Clean Sheet Home",
                "predicted": pred_cs,
                "actual": actual_cs,
                "correct": pred_cs == actual_cs,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "clean_sheet_adj_away":
            pred_cs = p["probability"] > 0.25
            actual_cs = clean_sheet_away(match)
            results.append({
                "category": "GK Clean Sheet Away",
                "predicted": pred_cs,
                "actual": actual_cs,
                "correct": pred_cs == actual_cs,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_tactical(agent_preds, match):
    """TacticalAgent: tactical_edge, possession_prediction"""
    results = []
    for p in agent_preds:
        if p["market"] == "tactical_edge":
            # Positive tactical edge = home advantage
            pred_home_advantage = p["probability"] > 0.0
            actual_result = match_result(match)
            actual_home_advantage = actual_result in ["H", "D"]  # home didn't lose
            results.append({
                "category": "Tactical Edge → Home Result",
                "predicted": pred_home_advantage,
                "actual": actual_home_advantage,
                "correct": pred_home_advantage == actual_home_advantage,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
        elif p["market"] == "possession_prediction":
            # If home possession > 0.5, they dominate
            pred_home_dom = p["probability"] > 0.5
            # Possession dominance correlates with not losing
            actual_home_dom = match_result(match) in ["H", "D"]
            results.append({
                "category": "Possession → Result",
                "predicted": pred_home_dom,
                "actual": actual_home_dom,
                "correct": pred_home_dom == actual_home_dom,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_set_piece(agent_preds, match):
    """SetPieceAgent: corner advantage, penalty probability"""
    results = []
    for p in agent_preds:
        if p["market"] == "penalty_probability":
            # High penalty prob → more goals
            pred_high_scoring = p["probability"] > 0.25
            actual_high = total_goals(match) >= 3
            results.append({
                "category": "Penalty → Goals",
                "predicted": pred_high_scoring,
                "actual": actual_high,
                "correct": pred_high_scoring == actual_high,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_injury(agent_preds, match):
    """InjuryAgent: injury_impact, lineup_strength"""
    results = []
    home_impact = None
    away_impact = None
    for p in agent_preds:
        if p["market"] == "injury_impact_home":
            home_impact = p["probability"]
        elif p["market"] == "injury_impact_away":
            away_impact = p["probability"]

    if home_impact is not None and away_impact is not None:
        # Team with worse injury impact should perform worse
        pred_home_better = home_impact < away_impact  # lower impact = healthier
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Injury Differential → Result",
            "predicted": pred_home_better,
            "actual": actual_home_better,
            "correct": pred_home_better == actual_home_better,
            "prob": abs(home_impact - away_impact),
            "confidence": 0.5
        })
    return results


def evaluate_fatigue(agent_preds, match):
    """FatigueAgent: fatigue_level, rest days"""
    results = []
    home_fatigue = None
    away_fatigue = None
    for p in agent_preds:
        if p["market"] == "fatigue_level_home":
            home_fatigue = p["probability"]
        elif p["market"] == "fatigue_level_away":
            away_fatigue = p["probability"]

    if home_fatigue is not None and away_fatigue is not None:
        # Less fatigued team should do better
        pred_home_fresher = home_fatigue < away_fatigue
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Fatigue Differential → Result",
            "predicted": pred_home_fresher,
            "actual": actual_home_better,
            "correct": pred_home_fresher == actual_home_better,
            "prob": abs(home_fatigue - away_fatigue),
            "confidence": 0.5
        })
    return results


def evaluate_manager(agent_preds, match):
    """ManagerAgent: advantage_magnitude, in-game adjustment ratings"""
    results = []
    for p in agent_preds:
        if p["market"] == "advantage_magnitude":
            # Positive = home manager advantage
            pred_home_wins = p["probability"] > 0.0
            actual_home_wins = match_result(match) == "H"
            results.append({
                "category": "Manager Edge → Win",
                "predicted": pred_home_wins,
                "actual": actual_home_wins,
                "correct": pred_home_wins == actual_home_wins,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_venue(agent_preds, match):
    """VenueAgent: home_advantage_modifier, atmosphere"""
    results = []
    for p in agent_preds:
        if p["market"] == "home_advantage_modifier":
            # Strong home advantage → home win more likely
            strong_home = p["probability"] > 0.1
            actual_home_result = match_result(match) in ["H", "D"]
            results.append({
                "category": "Venue → Home Result",
                "predicted": strong_home,
                "actual": actual_home_result,
                "correct": strong_home == actual_home_result,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_weather(agent_preds, match):
    """WeatherAgent: goal_scoring_impact, weather_impact"""
    results = []
    for p in agent_preds:
        if p["market"] == "goal_scoring_impact":
            # High goal scoring impact → more goals
            pred_many_goals = p["probability"] > 0.5
            actual_many = total_goals(match) >= 3
            results.append({
                "category": "Weather → Goals",
                "predicted": pred_many_goals,
                "actual": actual_many,
                "correct": pred_many_goals == actual_many,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_referee(agent_preds, match):
    """RefereeAgent: expected_yellows, strictness, penalty_prob"""
    results = []
    for p in agent_preds:
        if p["market"] == "penalty_probability":
            # If penalty prob high, more goals likely
            pred_goals = p["probability"] > 0.3
            actual_goals = total_goals(match) >= 3
            results.append({
                "category": "Ref Penalty → Goals",
                "predicted": pred_goals,
                "actual": actual_goals,
                "correct": pred_goals == actual_goals,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_stakes(agent_preds, match):
    """StakesAgent: stakes_level, motivation_multiplier"""
    results = []
    home_motivation = None
    away_motivation = None
    for p in agent_preds:
        if p["market"] == "motivation_multiplier_home":
            home_motivation = p["probability"]
        elif p["market"] == "motivation_multiplier_away":
            away_motivation = p["probability"]

    if home_motivation is not None and away_motivation is not None:
        pred_home_more_motivated = home_motivation > away_motivation
        actual_home_result = match_result(match) in ["H", "D"]
        results.append({
            "category": "Motivation → Result",
            "predicted": pred_home_more_motivated,
            "actual": actual_home_result,
            "correct": pred_home_more_motivated == actual_home_result,
            "prob": abs(home_motivation - away_motivation),
            "confidence": 0.55
        })
    return results


def evaluate_rivalry(agent_preds, match):
    """RivalryIntensityAgent: rivalry_score, card_multiplier"""
    results = []
    for p in agent_preds:
        if p["market"] == "rivalry_score":
            # High rivalry → more goals (intensity)
            pred_intense = p["probability"] > 0.5
            actual_intense = total_goals(match) >= 3
            results.append({
                "category": "Rivalry → Goals",
                "predicted": pred_intense,
                "actual": actual_intense,
                "correct": pred_intense == actual_intense,
                "prob": p["probability"],
                "confidence": p["confidence"]
            })
    return results


def evaluate_rest_days(agent_preds, match):
    """RestDaysAgent: rest_days, freshness"""
    results = []
    home_fresh = None
    away_fresh = None
    for p in agent_preds:
        if p["market"] == "freshness_home":
            home_fresh = p["probability"]
        elif p["market"] == "freshness_away":
            away_fresh = p["probability"]

    if home_fresh is not None and away_fresh is not None:
        pred_home_fresher = home_fresh > away_fresh
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Rest → Result",
            "predicted": pred_home_fresher,
            "actual": actual_home_better,
            "correct": pred_home_fresher == actual_home_better,
            "prob": abs(home_fresh - away_fresh),
            "confidence": 0.5
        })
    return results


def evaluate_media_pressure(agent_preds, match):
    """MediaPressureAgent: pressure_level, focus_rating"""
    results = []
    home_focus = None
    away_focus = None
    for p in agent_preds:
        if p["market"] == "focus_rating_home":
            home_focus = p["probability"]
        elif p["market"] == "focus_rating_away":
            away_focus = p["probability"]

    if home_focus is not None and away_focus is not None:
        pred_home_focused = home_focus > away_focus
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Focus → Result",
            "predicted": pred_home_focused,
            "actual": actual_home_better,
            "correct": pred_home_focused == actual_home_better,
            "prob": abs(home_focus - away_focus),
            "confidence": 0.45
        })
    return results


def evaluate_key_player(agent_preds, match):
    """KeyPlayerAgent: key_player_influence, creative_edge"""
    results = []
    home_inf = None
    away_inf = None
    for p in agent_preds:
        if p["market"] == "key_player_influence_home":
            home_inf = p["probability"]
        elif p["market"] == "key_player_influence_away":
            away_inf = p["probability"]

    if home_inf is not None and away_inf is not None:
        pred_home_edge = home_inf > away_inf
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Key Player → Result",
            "predicted": pred_home_edge,
            "actual": actual_home_better,
            "correct": pred_home_edge == actual_home_better,
            "prob": abs(home_inf - away_inf),
            "confidence": 0.5
        })
    return results


def evaluate_lineup(agent_preds, match):
    """LineupAgent: squad size, injuries count, injury impact"""
    results = []
    home_impact = None
    away_impact = None
    for p in agent_preds:
        if p["market"] == "home_injury_impact":
            home_impact = p["probability"]
        elif p["market"] == "away_injury_impact":
            away_impact = p["probability"]

    if home_impact is not None and away_impact is not None:
        pred_home_healthier = home_impact <= away_impact
        actual_home_better = match_result(match) in ["H", "D"]
        results.append({
            "category": "Lineup Strength → Result",
            "predicted": pred_home_healthier,
            "actual": actual_home_better,
            "correct": pred_home_healthier == actual_home_better,
            "prob": abs(home_impact - away_impact),
            "confidence": 0.45
        })
    return results


def evaluate_player_news(agent_preds, match):
    """PlayerNewsAgent: total goals of top 5 players"""
    results = []
    home_goals = None
    away_goals = None
    for p in agent_preds:
        if p["market"] == "home_total_goals_top5":
            home_goals = p["probability"]
        elif p["market"] == "away_total_goals_top5":
            away_goals = p["probability"]

    if home_goals is not None and away_goals is not None:
        pred_home_threat = home_goals > away_goals
        actual_home_scored_more = match["home_score"] >= match["away_score"]
        results.append({
            "category": "Player News → Scoring",
            "predicted": pred_home_threat,
            "actual": actual_home_scored_more,
            "correct": pred_home_threat == actual_home_scored_more,
            "prob": abs(home_goals - away_goals) if (home_goals + away_goals) > 0 else 0.5,
            "confidence": 0.4
        })
    return results


# ============================================================
# Dispatch table
# ============================================================
EVALUATORS = {
    "AttackingProfileAgent": evaluate_attacking_profile,
    "DefensiveProfileAgent": evaluate_defensive_profile,
    "GoalkeeperAgent": evaluate_goalkeeper,
    "TacticalAgent": evaluate_tactical,
    "SetPieceAgent": evaluate_set_piece,
    "InjuryAgent": evaluate_injury,
    "FatigueAgent": evaluate_fatigue,
    "ManagerAgent": evaluate_manager,
    "VenueAgent": evaluate_venue,
    "WeatherAgent": evaluate_weather,
    "RefereeAgent": evaluate_referee,
    "StakesAgent": evaluate_stakes,
    "RivalryIntensityAgent": evaluate_rivalry,
    "RestDaysAgent": evaluate_rest_days,
    "MediaPressureAgent": evaluate_media_pressure,
    "KeyPlayerAgent": evaluate_key_player,
    "LineupAgent": evaluate_lineup,
    "PlayerNewsAgent": evaluate_player_news,
}


# ============================================================
# Run evaluation
# ============================================================
def run_evaluation():
    all_results = {}

    for agent_name, evaluator in EVALUATORS.items():
        eval_obj = AgentEval(name=agent_name)
        all_agent_results = []

        match_preds = agent_match_preds.get(agent_name, {})
        eval_obj.total_matches = len(match_preds)

        for match_id, preds in match_preds.items():
            match = MATCHES.get(match_id)
            if not match or match["home_score"] is None:
                continue

            results = evaluator(preds, match)
            league = match["league"]

            for r in results:
                eval_obj.testable_predictions += 1
                if r["correct"]:
                    eval_obj.correct_predictions += 1

                cat = r["category"]
                eval_obj.categories[cat]["total"] += 1
                if r["correct"]:
                    eval_obj.categories[cat]["correct"] += 1

                eval_obj.by_league[league]["total"] += 1
                if r["correct"]:
                    eval_obj.by_league[league]["correct"] += 1

                # Calibration
                prob_bin = f"{round(r['prob'] * 5) / 5:.1f}"
                eval_obj.calibration[prob_bin]["count"] += 1
                eval_obj.calibration[prob_bin]["predicted_prob"] += r["prob"]
                if r["correct"]:
                    eval_obj.calibration[prob_bin]["actual_hit"] += 1

                all_agent_results.append(r)

        # Compute accuracy
        if eval_obj.testable_predictions > 0:
            eval_obj.useful_signal_rate = eval_obj.correct_predictions / eval_obj.testable_predictions

        # Compute confidence-weighted accuracy
        if all_agent_results:
            cw_correct = sum(r["confidence"] for r in all_agent_results if r["correct"])
            cw_total = sum(r["confidence"] for r in all_agent_results)
            eval_obj.signal_correlation = cw_correct / cw_total if cw_total > 0 else 0

        all_results[agent_name] = eval_obj

    return all_results


def print_results(results):
    print("\n" + "=" * 90)
    print("AGENT PERFORMANCE BACKTEST — 200 MATCHES, 5 LEAGUES, 2023-2024 SEASONS")
    print("=" * 90)

    # Sort by accuracy
    sorted_agents = sorted(
        results.items(),
        key=lambda x: (x[1].useful_signal_rate, x[1].testable_predictions),
        reverse=True
    )

    print(f"\n{'Agent':<28} {'Tests':>6} {'Correct':>8} {'Accuracy':>9} {'Conf-Wtd':>9} {'Signal':>8}")
    print("-" * 90)

    for name, ev in sorted_agents:
        acc = f"{ev.useful_signal_rate:.1%}" if ev.testable_predictions > 0 else "N/A"
        cw = f"{ev.signal_correlation:.1%}" if ev.signal_correlation > 0 else "N/A"
        signal = "STRONG" if ev.useful_signal_rate > 0.55 else ("USEFUL" if ev.useful_signal_rate > 0.50 else "WEAK")
        if ev.testable_predictions == 0:
            signal = "NO DATA"
        print(f"{name:<28} {ev.testable_predictions:>6} {ev.correct_predictions:>8} {acc:>9} {cw:>9} {signal:>8}")

    # Detailed per-agent breakdown
    print("\n\n" + "=" * 90)
    print("DETAILED PER-AGENT BREAKDOWN")
    print("=" * 90)

    for name, ev in sorted_agents:
        if ev.testable_predictions == 0:
            continue
        print(f"\n--- {name} ({ev.useful_signal_rate:.1%} accuracy, {ev.testable_predictions} predictions) ---")

        # Categories
        for cat, data in sorted(ev.categories.items(), key=lambda x: -x[1]["total"]):
            cat_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            print(f"  {cat:<35} {data['correct']:>3}/{data['total']:<3} = {cat_acc:.1%}")

        # By league
        if ev.by_league:
            print(f"  League breakdown:")
            for league, data in sorted(ev.by_league.items()):
                lg_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
                print(f"    {league:<25} {data['correct']:>3}/{data['total']:<3} = {lg_acc:.1%}")

    # ============================================================
    # TIER RANKING
    # ============================================================
    print("\n\n" + "=" * 90)
    print("AGENT TIER RANKING")
    print("=" * 90)

    tier1 = [(n, e) for n, e in sorted_agents if e.useful_signal_rate >= 0.55 and e.testable_predictions >= 10]
    tier2 = [(n, e) for n, e in sorted_agents if 0.50 <= e.useful_signal_rate < 0.55 and e.testable_predictions >= 10]
    tier3 = [(n, e) for n, e in sorted_agents if e.useful_signal_rate < 0.50 and e.testable_predictions >= 10]
    tier_nodata = [(n, e) for n, e in sorted_agents if e.testable_predictions < 10]

    print("\nTIER 1 — HIGH VALUE (>55% accuracy, actionable signals):")
    for n, e in tier1:
        print(f"  ★ {n}: {e.useful_signal_rate:.1%} ({e.testable_predictions} tests)")
    if not tier1:
        print("  (none)")

    print("\nTIER 2 — USEFUL (50-55% accuracy, marginal edge):")
    for n, e in tier2:
        print(f"  ● {n}: {e.useful_signal_rate:.1%} ({e.testable_predictions} tests)")
    if not tier2:
        print("  (none)")

    print("\nTIER 3 — WEAK (<50% accuracy, negative or no signal):")
    for n, e in tier3:
        print(f"  ○ {n}: {e.useful_signal_rate:.1%} ({e.testable_predictions} tests)")
    if not tier3:
        print("  (none)")

    print("\nINSUFFICIENT DATA (<10 testable predictions):")
    for n, e in tier_nodata:
        print(f"  ? {n}: {e.testable_predictions} tests")

    return sorted_agents


def save_results(results):
    output = {
        "evaluation": "proper_agent_backtest",
        "total_matches": len(MATCHES),
        "seasons": "2023-2024",
        "leagues": list(set(m["league"] for m in MATCHES.values())),
        "agents": {}
    }

    for name, ev in results.items():
        agent_data = {
            "total_matches_analyzed": ev.total_matches,
            "testable_predictions": ev.testable_predictions,
            "correct_predictions": ev.correct_predictions,
            "accuracy": round(ev.useful_signal_rate, 4),
            "confidence_weighted_accuracy": round(ev.signal_correlation, 4),
            "signal_strength": "STRONG" if ev.useful_signal_rate > 0.55 else ("USEFUL" if ev.useful_signal_rate > 0.50 else "WEAK"),
            "categories": {},
            "by_league": {},
        }

        for cat, data in ev.categories.items():
            cat_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            agent_data["categories"][cat] = {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": round(cat_acc, 4)
            }

        for league, data in ev.by_league.items():
            lg_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            agent_data["by_league"][league] = {
                "total": data["total"],
                "correct": data["correct"],
                "accuracy": round(lg_acc, 4)
            }

        output["agents"][name] = agent_data

    with open("agent_eval_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to agent_eval_results.json")


if __name__ == "__main__":
    results = run_evaluation()
    sorted_agents = print_results(results)
    save_results(results)
