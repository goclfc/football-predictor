"""
Full Agent Evaluation — 200 matches, 5 leagues, 36,000 predictions.
Maps each agent's specialized signals to verifiable match outcomes.
"""
import json
from collections import defaultdict

with open("expanded_agent_predictions.json") as f:
    ALL_PREDS = json.load(f)

# Index by (agent, match_id)
agent_match = defaultdict(lambda: defaultdict(list))
for p in ALL_PREDS:
    agent_match[p["agent_name"]][p["match_id"]].append(p)

# Unique matches
matches_by_id = {}
for p in ALL_PREDS:
    mid = p["match_id"]
    if mid not in matches_by_id:
        matches_by_id[mid] = {
            "home_team": p["home_team"],
            "away_team": p["away_team"],
            "home_score": p["home_score"],
            "away_score": p["away_score"],
            "league": p["league"],
        }

def result(m):
    return "H" if m["home_score"] > m["away_score"] else ("A" if m["home_score"] < m["away_score"] else "D")
def goals(m): return m["home_score"] + m["away_score"]
def btts(m): return m["home_score"] > 0 and m["away_score"] > 0
def cs_home(m): return m["away_score"] == 0
def cs_away(m): return m["home_score"] == 0


def get_val(preds, market):
    """Get numeric value for a market from predictions list."""
    for p in preds:
        if p["market"] == market:
            v = p["value"]
            if isinstance(v, (int, float)):
                return v
            try:
                return float(v)
            except (ValueError, TypeError):
                return None
    return None


def get_str(preds, market):
    for p in preds:
        if p["market"] == market:
            return str(p["value"])
    return None


# ============================================================
# EVALUATION FUNCTIONS — return list of (category, predicted_bool, actual_bool)
# ============================================================

def eval_fatigue(preds, m):
    tests = []
    hf = get_val(preds, "fatigue_level_home")
    af = get_val(preds, "fatigue_level_away")
    if hf is not None and af is not None:
        # Less fatigued team does better
        pred = hf < af  # home is fresher
        actual = result(m) in ["H", "D"]
        tests.append(("Fatigue→Result", pred, actual))
    return tests

def eval_venue(preds, m):
    tests = []
    v = get_val(preds, "home_advantage_modifier")
    if v is not None:
        # Strong venue = home doesn't lose
        pred = v > 0.05
        actual = result(m) in ["H", "D"]
        tests.append(("Venue→Home", pred, actual))

    atmo = get_val(preds, "atmosphere_rating")
    if atmo is not None:
        # High atmosphere → home benefit
        pred = atmo > 0.5
        actual = result(m) == "H"
        tests.append(("Atmosphere→HomeWin", pred, actual))
    return tests

def eval_tactical(preds, m):
    tests = []
    edge = get_val(preds, "tactical_edge")
    if edge is not None:
        pred = edge > 0
        actual = result(m) in ["H", "D"]
        tests.append(("TacticalEdge→Result", pred, actual))

    poss = get_val(preds, "possession_prediction")
    if poss is not None:
        pred = poss > 0.5  # home dominates possession
        actual = result(m) in ["H", "D"]
        tests.append(("Possession→Result", pred, actual))
    return tests

def eval_weather(preds, m):
    tests = []
    gi = get_val(preds, "goal_scoring_impact")
    if gi is not None:
        pred = gi > 0.5  # favorable for goals
        actual = goals(m) >= 3
        tests.append(("Weather→Over2.5", pred, actual))
    return tests

def eval_attacking(preds, m):
    tests = []
    xg_h = get_val(preds, "xg_home")
    xg_a = get_val(preds, "xg_away")
    btts_p = get_val(preds, "btts_probability")
    fg_h = get_val(preds, "first_goal_prob_home")

    if xg_h is not None and xg_a is not None:
        # Higher xG team scores more
        pred_home_more = xg_h > xg_a
        actual_home_more = m["home_score"] >= m["away_score"]
        tests.append(("xG→Scoring", pred_home_more, actual_home_more))

        # Combined xG → total goals
        pred_over = (xg_h + xg_a) > 1.5
        actual_over = goals(m) >= 3
        tests.append(("xG→Over2.5", pred_over, actual_over))

    if btts_p is not None:
        pred = btts_p > 0.5
        actual = btts(m)
        tests.append(("BTTS", pred, actual))

    if fg_h is not None:
        pred = fg_h > 0.5
        actual = m["home_score"] >= m["away_score"] and m["home_score"] > 0
        tests.append(("FirstGoal→Home", pred, actual))

    return tests

def eval_defensive(preds, m):
    tests = []
    cs_h = get_val(preds, "clean_sheet_prob_home")
    cs_a = get_val(preds, "clean_sheet_prob_away")

    if cs_h is not None:
        pred = cs_h > 0.35
        actual = cs_home(m)
        tests.append(("CleanSheet_Home", pred, actual))

    if cs_a is not None:
        pred = cs_a > 0.35
        actual = cs_away(m)
        tests.append(("CleanSheet_Away", pred, actual))
    return tests

def eval_goalkeeper(preds, m):
    tests = []
    cs_h = get_val(preds, "clean_sheet_adj_home")
    cs_a = get_val(preds, "clean_sheet_adj_away")
    gk_h = get_val(preds, "home_gk_rating")
    gk_a = get_val(preds, "away_gk_rating")

    if gk_h is not None and gk_a is not None:
        # Better GK rating → fewer goals conceded
        pred_home_gk_better = gk_h > gk_a
        actual = m["home_score"] <= m["away_score"]  # fewer goals conceded = opponent scores less
        # Actually: better GK = team doesn't lose
        actual = result(m) in ["H", "D"]
        tests.append(("GK_Rating→Result", pred_home_gk_better, actual))

    if cs_h is not None:
        pred = cs_h > 0.25
        actual = cs_home(m)
        tests.append(("GK_CS_Home", pred, actual))
    if cs_a is not None:
        pred = cs_a > 0.25
        actual = cs_away(m)
        tests.append(("GK_CS_Away", pred, actual))
    return tests

def eval_injury(preds, m):
    tests = []
    hi = get_val(preds, "injury_impact_home")
    ai = get_val(preds, "injury_impact_away")
    ls_h = get_val(preds, "lineup_strength_home")
    ls_a = get_val(preds, "lineup_strength_away")

    if hi is not None and ai is not None:
        pred = hi <= ai  # home less injured
        actual = result(m) in ["H", "D"]
        tests.append(("InjuryDiff→Result", pred, actual))

    if ls_h is not None and ls_a is not None:
        pred = ls_h > ls_a
        actual = result(m) in ["H", "D"]
        tests.append(("LineupStrength→Result", pred, actual))
    return tests

def eval_manager(preds, m):
    tests = []
    adv = get_val(preds, "advantage_magnitude")
    if adv is not None:
        pred = adv > 0  # home manager has edge
        actual = result(m) in ["H", "D"]
        tests.append(("ManagerEdge→Result", pred, actual))

    # Tactical adjustments
    adj_h = get_val(preds, "in_game_adjustment_rating_home")
    adj_a = get_val(preds, "in_game_adjustment_rating_away")
    if adj_h is not None and adj_a is not None:
        pred = adj_h > adj_a
        actual = result(m) in ["H", "D"]
        tests.append(("ManagerAdjust→Result", pred, actual))

    # Attacking creativity
    atk_h = get_val(preds, "home_attacking_creativity")
    atk_a = get_val(preds, "away_attacking_creativity")
    if atk_h is not None and atk_a is not None:
        pred = atk_h > atk_a
        actual = m["home_score"] >= m["away_score"]
        tests.append(("ManagerCreativity→Scoring", pred, actual))
    return tests

def eval_stakes(preds, m):
    tests = []
    mot_h = get_val(preds, "motivation_multiplier_home")
    mot_a = get_val(preds, "motivation_multiplier_away")
    if mot_h is not None and mot_a is not None:
        pred = mot_h > mot_a
        actual = result(m) in ["H", "D"]
        tests.append(("Motivation→Result", pred, actual))

    intensity = get_val(preds, "match_intensity_prediction")
    if intensity is not None:
        pred = intensity > 0.7  # intense match → more cards/fouls → potentially more goals
        actual = goals(m) >= 3
        tests.append(("Intensity→Goals", pred, actual))
    return tests

def eval_referee(preds, m):
    tests = []
    pen = get_val(preds, "penalty_probability")
    if pen is not None:
        # High penalty prob → more goals
        pred = pen > 0.3
        actual = goals(m) >= 3
        tests.append(("RefPenalty→Goals", pred, actual))

    strict = get_val(preds, "referee_strictness")
    if strict is not None:
        # Strict referee → under 2.5 (cautious play)
        pred = strict > 0.7
        actual = goals(m) < 3
        tests.append(("RefStrict→Under2.5", pred, actual))
    return tests

def eval_rivalry(preds, m):
    tests = []
    riv = get_val(preds, "rivalry_score")
    if riv is not None:
        pred = riv > 0.5  # high rivalry → more goals and drama
        actual = goals(m) >= 3
        tests.append(("Rivalry→Goals", pred, actual))

    card_mult = get_val(preds, "card_multiplier")
    if card_mult is not None:
        # High card multiplier → intense match → BTTS
        pred = card_mult > 1.0
        actual = btts(m)
        tests.append(("RivalryCards→BTTS", pred, actual))
    return tests

def eval_rest_days(preds, m):
    tests = []
    fresh_h = get_val(preds, "freshness_home")
    fresh_a = get_val(preds, "freshness_away")
    if fresh_h is not None and fresh_a is not None:
        pred = fresh_h > fresh_a
        actual = result(m) in ["H", "D"]
        tests.append(("Rest→Result", pred, actual))

    rd_h = get_val(preds, "rest_days_home")
    rd_a = get_val(preds, "rest_days_away")
    if rd_h is not None and rd_a is not None and isinstance(rd_h, (int, float)) and isinstance(rd_a, (int, float)):
        pred = rd_h >= rd_a  # more rest = advantage
        actual = result(m) in ["H", "D"]
        tests.append(("RestDays→Result", pred, actual))
    return tests

def eval_media_pressure(preds, m):
    tests = []
    focus_h = get_val(preds, "focus_rating_home")
    focus_a = get_val(preds, "focus_rating_away")
    if focus_h is not None and focus_a is not None:
        pred = focus_h > focus_a
        actual = result(m) in ["H", "D"]
        tests.append(("Focus→Result", pred, actual))

    press_h = get_val(preds, "pressure_level_home")
    press_a = get_val(preds, "pressure_level_away")
    if press_h is not None and press_a is not None:
        # Less pressure → better performance
        pred = press_h < press_a
        actual = result(m) in ["H", "D"]
        tests.append(("LessPressure→Result", pred, actual))
    return tests

def eval_key_player(preds, m):
    tests = []
    kp_h = get_val(preds, "key_player_influence_home")
    kp_a = get_val(preds, "key_player_influence_away")
    if kp_h is not None and kp_a is not None:
        pred = kp_h > kp_a
        actual = result(m) in ["H", "D"]
        tests.append(("KeyPlayer→Result", pred, actual))

    gt = get_val(preds, "goal_threat_rating")
    if gt is not None:
        pred = gt > 0.5  # high threat → goals
        actual = goals(m) >= 3
        tests.append(("GoalThreat→Over2.5", pred, actual))
    return tests

def eval_set_piece(preds, m):
    tests = []
    pen = get_val(preds, "penalty_probability")
    if pen is not None:
        pred = pen > 0.2
        actual = goals(m) >= 3
        tests.append(("SetPiecePen→Goals", pred, actual))

    ca = get_val(preds, "corner_advantage_score")
    if ca is not None:
        # Home corner advantage → more goals for home
        pred = ca > 0  # positive = home advantage
        actual = m["home_score"] > 0
        tests.append(("CornerAdv→HomeScores", pred, actual))

    dbt = get_val(preds, "dead_ball_threat_rating")
    if dbt is not None:
        pred = dbt > 0.5
        actual = goals(m) >= 2
        tests.append(("DeadBall→Goals", pred, actual))
    return tests

def eval_lineup(preds, m):
    tests = []
    hi = get_val(preds, "home_injury_impact")
    ai = get_val(preds, "away_injury_impact")
    if hi is not None and ai is not None:
        pred = hi <= ai
        actual = result(m) in ["H", "D"]
        tests.append(("LineupInjury→Result", pred, actual))

    hs = get_val(preds, "home_squad_size")
    as_ = get_val(preds, "away_squad_size")
    if hs is not None and as_ is not None and isinstance(hs, (int, float)) and isinstance(as_, (int, float)):
        pred = hs >= as_
        actual = result(m) in ["H", "D"]
        tests.append(("SquadSize→Result", pred, actual))
    return tests

def eval_player_news(preds, m):
    tests = []
    hg = get_val(preds, "home_total_goals_top5")
    ag = get_val(preds, "away_total_goals_top5")
    if hg is not None and ag is not None:
        if hg + ag > 0:
            pred = hg > ag
            actual = m["home_score"] >= m["away_score"]
            tests.append(("PlayerGoals→Scoring", pred, actual))
    return tests

def eval_momentum(preds, m):
    tests = []
    mom_h = get_val(preds, "momentum_score_home")
    mom_a = get_val(preds, "momentum_score_away")
    if mom_h is not None and mom_a is not None:
        pred = mom_h > mom_a
        actual = result(m) in ["H", "D"]
        tests.append(("Momentum→Result", pred, actual))

    # Check trend
    trend_h = get_str(preds, "home_trend")
    trend_a = get_str(preds, "away_trend")
    if trend_h and trend_a:
        home_up = "up" in str(trend_h).lower() or "improving" in str(trend_h).lower()
        away_up = "up" in str(trend_a).lower() or "improving" in str(trend_a).lower()
        if home_up != away_up:
            pred = home_up
            actual = result(m) in ["H", "D"]
            tests.append(("Trend→Result", pred, actual))
    return tests

def eval_schedule(preds, m):
    tests = []
    # Schedule context gives congestion info
    cong_h = get_val(preds, "home_congestion_score")
    cong_a = get_val(preds, "away_congestion_score")
    if cong_h is not None and cong_a is not None:
        pred = cong_h < cong_a  # less congested = advantage
        actual = result(m) in ["H", "D"]
        tests.append(("Schedule→Result", pred, actual))

    next_h = get_val(preds, "home_days_to_next")
    next_a = get_val(preds, "away_days_to_next")
    if next_h is not None and next_a is not None and isinstance(next_h, (int, float)) and isinstance(next_a, (int, float)):
        # More rest before next game = can go all out
        pred = next_h >= next_a
        actual = result(m) in ["H", "D"]
        tests.append(("NextGame→Result", pred, actual))
    return tests


EVALUATORS = {
    "FatigueAgent": eval_fatigue,
    "VenueAgent": eval_venue,
    "TacticalAgent": eval_tactical,
    "WeatherAgent": eval_weather,
    "AttackingProfileAgent": eval_attacking,
    "DefensiveProfileAgent": eval_defensive,
    "GoalkeeperAgent": eval_goalkeeper,
    "InjuryAgent": eval_injury,
    "ManagerAgent": eval_manager,
    "StakesAgent": eval_stakes,
    "RefereeAgent": eval_referee,
    "RivalryIntensityAgent": eval_rivalry,
    "RestDaysAgent": eval_rest_days,
    "MediaPressureAgent": eval_media_pressure,
    "KeyPlayerAgent": eval_key_player,
    "SetPieceAgent": eval_set_piece,
    "LineupAgent": eval_lineup,
    "PlayerNewsAgent": eval_player_news,
    "MomentumAgent": eval_momentum,
    "ScheduleContextAgent": eval_schedule,
}

# ============================================================
# RUN
# ============================================================
results = {}

for agent_name, evaluator in EVALUATORS.items():
    agent_data = {
        "total_tests": 0,
        "correct": 0,
        "categories": defaultdict(lambda: {"total": 0, "correct": 0}),
        "by_league": defaultdict(lambda: {"total": 0, "correct": 0}),
    }

    for mid, preds in agent_match[agent_name].items():
        m = matches_by_id.get(mid)
        if not m:
            continue

        tests = evaluator(preds, m)
        for cat, predicted, actual in tests:
            correct = predicted == actual
            agent_data["total_tests"] += 1
            if correct:
                agent_data["correct"] += 1
            agent_data["categories"][cat]["total"] += 1
            if correct:
                agent_data["categories"][cat]["correct"] += 1
            agent_data["by_league"][m["league"]]["total"] += 1
            if correct:
                agent_data["by_league"][m["league"]]["correct"] += 1

    accuracy = agent_data["correct"] / agent_data["total_tests"] if agent_data["total_tests"] > 0 else 0
    results[agent_name] = {
        "accuracy": accuracy,
        "total_tests": agent_data["total_tests"],
        "correct": agent_data["correct"],
        "categories": dict(agent_data["categories"]),
        "by_league": dict(agent_data["by_league"]),
    }

# ============================================================
# PRINT RESULTS
# ============================================================
print("\n" + "=" * 100)
print("FULL AGENT BACKTEST — 200 MATCHES, 5 LEAGUES, 2023-2024 SEASONS, 36,000 RAW PREDICTIONS")
print("=" * 100)

sorted_agents = sorted(results.items(), key=lambda x: (-x[1]["accuracy"], -x[1]["total_tests"]))

print(f"\n{'Agent':<28} {'Tests':>7} {'Correct':>8} {'Accuracy':>9} {'Signal':>10}")
print("-" * 100)

for name, data in sorted_agents:
    acc = f"{data['accuracy']:.1%}"
    signal = "★ STRONG" if data["accuracy"] > 0.58 else ("● GOOD" if data["accuracy"] > 0.53 else ("◐ USEFUL" if data["accuracy"] > 0.48 else "○ WEAK"))
    if data["total_tests"] < 20:
        signal = "? LOW DATA"
    print(f"{name:<28} {data['total_tests']:>7} {data['correct']:>8} {acc:>9} {signal:>10}")

# Category breakdown for top agents
print("\n\n" + "=" * 100)
print("DETAILED CATEGORY BREAKDOWN — TOP AGENTS")
print("=" * 100)

for name, data in sorted_agents:
    if data["accuracy"] < 0.48 and data["total_tests"] >= 20:
        continue
    if data["total_tests"] < 20:
        continue

    print(f"\n{'─'*60}")
    print(f"  {name} — {data['accuracy']:.1%} overall ({data['total_tests']} tests)")
    print(f"{'─'*60}")

    for cat, cd in sorted(data["categories"].items(), key=lambda x: -x[1]["total"]):
        ca = cd["correct"] / cd["total"] if cd["total"] > 0 else 0
        bar = "█" * int(ca * 20) + "░" * (20 - int(ca * 20))
        print(f"  {cat:<30} {cd['correct']:>4}/{cd['total']:<4} {ca:>6.1%}  {bar}")

    print(f"  By League:")
    for lg, ld in sorted(data["by_league"].items()):
        la = ld["correct"] / ld["total"] if ld["total"] > 0 else 0
        print(f"    {lg:<25} {ld['correct']:>3}/{ld['total']:<3} = {la:.1%}")

# ============================================================
# TIER RANKING
# ============================================================
print("\n\n" + "=" * 100)
print("FINAL AGENT TIER RANKING")
print("=" * 100)

tier1 = [(n, d) for n, d in sorted_agents if d["accuracy"] >= 0.58 and d["total_tests"] >= 50]
tier2 = [(n, d) for n, d in sorted_agents if 0.53 <= d["accuracy"] < 0.58 and d["total_tests"] >= 50]
tier3 = [(n, d) for n, d in sorted_agents if 0.48 <= d["accuracy"] < 0.53 and d["total_tests"] >= 50]
tier4 = [(n, d) for n, d in sorted_agents if d["accuracy"] < 0.48 and d["total_tests"] >= 50]
low_data = [(n, d) for n, d in sorted_agents if d["total_tests"] < 50]

print("\n🏆 TIER 1 — HIGH VALUE (58%+ accuracy) — INCREASE WEIGHT IN META-AGENT:")
for n, d in tier1:
    print(f"  ★ {n}: {d['accuracy']:.1%} ({d['total_tests']} tests)")
    # Best category
    best_cat = max(d["categories"].items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"]>5 else 0)
    bc_acc = best_cat[1]["correct"]/best_cat[1]["total"]
    print(f"    Best signal: {best_cat[0]} ({bc_acc:.0%})")

print("\n● TIER 2 — GOOD (53-58% accuracy) — KEEP CURRENT WEIGHT:")
for n, d in tier2:
    print(f"  ● {n}: {d['accuracy']:.1%} ({d['total_tests']} tests)")

print("\n◐ TIER 3 — MARGINAL (48-53% accuracy) — REDUCE WEIGHT:")
for n, d in tier3:
    print(f"  ◐ {n}: {d['accuracy']:.1%} ({d['total_tests']} tests)")

print("\n○ TIER 4 — WEAK (<48% accuracy) — CONSIDER REMOVING OR INVERTING:")
for n, d in tier4:
    print(f"  ○ {n}: {d['accuracy']:.1%} ({d['total_tests']} tests)")
    # Worst category
    if d["categories"]:
        worst_cat = min(d["categories"].items(), key=lambda x: x[1]["correct"]/x[1]["total"] if x[1]["total"]>5 else 1)
        wc_acc = worst_cat[1]["correct"]/worst_cat[1]["total"] if worst_cat[1]["total"] > 5 else 0
        print(f"    Worst signal: {worst_cat[0]} ({wc_acc:.0%})")

if low_data:
    print("\n? INSUFFICIENT DATA (<50 tests):")
    for n, d in low_data:
        print(f"  ? {n}: {d['accuracy']:.1%} ({d['total_tests']} tests)")

# ============================================================
# LEAGUE-SPECIFIC BEST AGENTS
# ============================================================
print("\n\n" + "=" * 100)
print("BEST AGENTS BY LEAGUE")
print("=" * 100)

leagues = set()
for d in results.values():
    leagues.update(d["by_league"].keys())

for league in sorted(leagues):
    print(f"\n  {league}:")
    league_agents = []
    for name, data in results.items():
        if league in data["by_league"]:
            ld = data["by_league"][league]
            if ld["total"] >= 10:
                la = ld["correct"] / ld["total"]
                league_agents.append((name, la, ld["total"]))

    league_agents.sort(key=lambda x: -x[1])
    for n, a, t in league_agents[:5]:
        print(f"    {n:<28} {a:.1%} ({t} tests)")

# Save JSON
output = {
    "evaluation": "full_agent_backtest_v2",
    "total_matches": len(matches_by_id),
    "total_raw_predictions": len(ALL_PREDS),
    "seasons": "2023-2024",
    "agents": {}
}
for name, data in results.items():
    cats = {}
    for cat, cd in data["categories"].items():
        cats[cat] = {"total": cd["total"], "correct": cd["correct"],
                     "accuracy": round(cd["correct"]/cd["total"], 4) if cd["total"] > 0 else 0}
    lgs = {}
    for lg, ld in data["by_league"].items():
        lgs[lg] = {"total": ld["total"], "correct": ld["correct"],
                   "accuracy": round(ld["correct"]/ld["total"], 4) if ld["total"] > 0 else 0}

    output["agents"][name] = {
        "accuracy": round(data["accuracy"], 4),
        "total_tests": data["total_tests"],
        "correct": data["correct"],
        "tier": 1 if data["accuracy"]>=0.58 else (2 if data["accuracy"]>=0.53 else (3 if data["accuracy"]>=0.48 else 4)),
        "categories": cats,
        "by_league": lgs,
    }

with open("agent_eval_full_results.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\n\nSaved to agent_eval_full_results.json")
