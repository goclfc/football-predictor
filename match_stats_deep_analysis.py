#!/usr/bin/env python3
"""
MATCH STATS DEEP ANALYSIS — Cross-reference EVERY stat with EVERY game state.

For 4,888 matches we analyze:
1. Score state → corners, shots, offsides, fouls, cards (by HT score)
2. Position matchup → all stats (title vs mid-table, etc.)
3. Goal diff at HT → 2H stat distributions
4. Team dominance patterns → stat flow
5. Correlations between all stat pairs
6. Per-league stat profiles under different conditions
7. Shot accuracy → corners → goals chain
8. Fouls → cards → reds chain
9. Leading team vs trailing team stat patterns
10. Home/away splits for every stat under every condition
"""
import sys, os, math
from datetime import datetime
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.multi_source_collector import FootballDataCollector


def load_all():
    collector = FootballDataCollector("/tmp/football_data")
    leagues = {"Premier League": "E0", "La Liga": "SP1", "Bundesliga": "D1",
               "Serie A": "I1", "Ligue 1": "F1"}
    seasons = ["2324", "2425", "2526"]
    all_m = []
    for ln in leagues:
        for s in seasons:
            matches = collector.get_historical_matches(ln, s)
            for m in matches:
                try: m["datetime"] = datetime.strptime(m["date"], "%d/%m/%Y")
                except: continue
                m["league"] = ln
                m["season"] = s
                # Compute all derived stats
                m["total_goals"] = m["home_goals"] + m["away_goals"]
                m["total_corners"] = m.get("home_corners", 0) + m.get("away_corners", 0)
                m["total_cards"] = m.get("home_yellows", 0) + m.get("away_yellows", 0) + m.get("home_reds", 0) + m.get("away_reds", 0)
                m["total_fouls"] = m.get("home_fouls", 0) + m.get("away_fouls", 0)
                m["total_shots"] = m.get("home_shots", 0) + m.get("away_shots", 0)
                m["total_sot"] = m.get("home_shots_target", 0) + m.get("away_shots_target", 0)
                m["total_reds"] = m.get("home_reds", 0) + m.get("away_reds", 0)
                m["ht_home"] = m.get("ht_home_goals", 0)
                m["ht_away"] = m.get("ht_away_goals", 0)
                m["ht_total"] = m["ht_home"] + m["ht_away"]
                m["ht_diff"] = m["ht_home"] - m["ht_away"]
                m["ft_diff"] = m["home_goals"] - m["away_goals"]
                m["2h_goals"] = m["total_goals"] - m["ht_total"]
                m["is_home_win"] = 1 if m["ft_diff"] > 0 else 0
                m["is_draw"] = 1 if m["ft_diff"] == 0 else 0
                m["is_away_win"] = 1 if m["ft_diff"] < 0 else 0
                # Shot accuracy
                ts = m["total_shots"] if m["total_shots"] > 0 else 1
                m["shot_accuracy"] = m["total_sot"] / ts
                m["goals_per_sot"] = m["total_goals"] / m["total_sot"] if m["total_sot"] > 0 else 0
                all_m.append(m)
    all_m.sort(key=lambda x: x["datetime"])

    # Build running standings for position
    standings = defaultdict(lambda: defaultdict(lambda: {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0}))
    for m in all_m:
        ls = f"{m['league']}_{m['season']}"
        s = standings[ls]
        # Position before this match
        sorted_t = sorted(s.keys(), key=lambda t: (-s[t]["pts"], -(s[t]["gf"]-s[t]["ga"]), -s[t]["gf"]))
        m["home_pos"] = (sorted_t.index(m["home"]) + 1) if m["home"] in sorted_t else 20
        m["away_pos"] = (sorted_t.index(m["away"]) + 1) if m["away"] in sorted_t else 20
        # Update
        h, a = m["home"], m["away"]
        s[h]["p"] += 1; s[a]["p"] += 1
        s[h]["gf"] += m["home_goals"]; s[h]["ga"] += m["away_goals"]
        s[a]["gf"] += m["away_goals"]; s[a]["ga"] += m["home_goals"]
        if m["ft_diff"] > 0: s[h]["w"] += 1; s[h]["pts"] += 3; s[a]["l"] += 1
        elif m["ft_diff"] == 0: s[h]["d"] += 1; s[h]["pts"] += 1; s[a]["d"] += 1; s[a]["pts"] += 1
        else: s[a]["w"] += 1; s[a]["pts"] += 3; s[h]["l"] += 1

    print(f"Loaded {len(all_m)} matches")
    return all_m


def avg(lst):
    return sum(lst) / len(lst) if lst else 0

def pct(count, total):
    return count / total * 100 if total else 0


# ═══════════════════════════════════════════════════════════════
# 1. HT SCORE → ALL 2H STATS
# ═══════════════════════════════════════════════════════════════

def analyze_ht_score_to_stats(matches):
    print("\n" + "=" * 100)
    print("1. HALFTIME SCORE → FULL-TIME STATS (What does each HT score produce?)")
    print("=" * 100)

    ht_buckets = defaultdict(list)
    for m in matches:
        key = f"{m['ht_home']}-{m['ht_away']}"
        ht_buckets[key].append(m)

    print(f"\n{'HT Score':<10} {'N':>5} {'FT Goals':>9} {'2H Goals':>9} {'Corners':>8} {'Cards':>7} "
          f"{'Fouls':>7} {'Shots':>7} {'SOT':>6} {'Reds':>6} {'HW%':>7} {'O2.5%':>7} {'BTTS%':>7}")
    print("-" * 115)

    scores = ["0-0", "1-0", "0-1", "1-1", "2-0", "0-2", "2-1", "1-2", "2-2", "3-0", "0-3", "3-1", "1-3"]
    results = {}

    for ht in scores:
        ms = ht_buckets.get(ht, [])
        if len(ms) < 15: continue
        n = len(ms)
        r = {
            "count": n,
            "ft_goals": avg([m["total_goals"] for m in ms]),
            "2h_goals": avg([m["2h_goals"] for m in ms]),
            "corners": avg([m["total_corners"] for m in ms]),
            "cards": avg([m["total_cards"] for m in ms]),
            "fouls": avg([m["total_fouls"] for m in ms]),
            "shots": avg([m["total_shots"] for m in ms]),
            "sot": avg([m["total_sot"] for m in ms]),
            "reds": avg([m["total_reds"] for m in ms]),
            "hw": pct(sum(m["is_home_win"] for m in ms), n),
            "o25": pct(sum(1 for m in ms if m["total_goals"] > 2.5), n),
            "btts": pct(sum(1 for m in ms if m["home_goals"] > 0 and m["away_goals"] > 0), n),
        }
        results[ht] = r
        print(f"{ht:<10} {n:>5} {r['ft_goals']:>9.2f} {r['2h_goals']:>9.2f} {r['corners']:>7.1f} {r['cards']:>6.1f} "
              f"{r['fouls']:>6.1f} {r['shots']:>6.1f} {r['sot']:>5.1f} {r['reds']:>5.2f} {r['hw']:>6.1f}% {r['o25']:>6.1f}% {r['btts']:>6.1f}%")

    # By HT goal difference
    print(f"\n  BY HT GOAL DIFFERENCE:")
    print(f"  {'HT Diff':<12} {'N':>6} {'2H Goals':>9} {'2H Corn':>8} {'2H Cards':>9} {'Fouls':>7} {'Shots':>7}")
    print(f"  {'-'*65}")

    diff_buckets = defaultdict(list)
    for m in matches:
        diff_buckets[m["ht_diff"]].append(m)

    for diff in sorted(diff_buckets.keys()):
        ms = diff_buckets[diff]
        if len(ms) < 30: continue
        n = len(ms)
        label = f"Home +{diff}" if diff > 0 else ("Level" if diff == 0 else f"Away +{abs(diff)}")
        print(f"  {label:<12} {n:>6} {avg([m['2h_goals'] for m in ms]):>9.2f} "
              f"{avg([m['total_corners'] for m in ms]):>7.1f} {avg([m['total_cards'] for m in ms]):>8.1f} "
              f"{avg([m['total_fouls'] for m in ms]):>6.1f} {avg([m['total_shots'] for m in ms]):>6.1f}")

    return results


# ═══════════════════════════════════════════════════════════════
# 2. FT SCORE → CORNER/SHOT/CARD DISTRIBUTIONS
# ═══════════════════════════════════════════════════════════════

def analyze_ft_score_stats(matches):
    print("\n" + "=" * 100)
    print("2. FINAL SCORE → MATCH STATS (What stats come with each scoreline?)")
    print("=" * 100)

    ft_buckets = defaultdict(list)
    for m in matches:
        key = f"{m['home_goals']}-{m['away_goals']}"
        ft_buckets[key].append(m)

    print(f"\n{'FT Score':<10} {'N':>5} {'Corners':>8} {'Cards':>7} {'Fouls':>7} {'Shots':>7} "
          f"{'SOT':>6} {'Reds':>6} {'Shot Acc':>9}")
    print("-" * 75)

    for ft in ["0-0", "1-0", "0-1", "1-1", "2-0", "0-2", "2-1", "1-2", "2-2",
               "3-0", "0-3", "3-1", "1-3", "3-2", "2-3", "4-0", "4-1", "4-2"]:
        ms = ft_buckets.get(ft, [])
        if len(ms) < 10: continue
        n = len(ms)
        print(f"{ft:<10} {n:>5} {avg([m['total_corners'] for m in ms]):>7.1f} "
              f"{avg([m['total_cards'] for m in ms]):>6.1f} {avg([m['total_fouls'] for m in ms]):>6.1f} "
              f"{avg([m['total_shots'] for m in ms]):>6.1f} {avg([m['total_sot'] for m in ms]):>5.1f} "
              f"{avg([m['total_reds'] for m in ms]):>5.2f} {avg([m['shot_accuracy'] for m in ms]):>8.1%}")

    # Goal difference → stats
    print(f"\n  GOAL DIFFERENCE → STATS:")
    gd_buckets = defaultdict(list)
    for m in matches:
        gd_buckets[abs(m["ft_diff"])].append(m)

    print(f"  {'Abs GD':<10} {'N':>6} {'Corners':>8} {'Cards':>7} {'Fouls':>7} {'Shots':>7} {'Reds':>6}")
    print(f"  {'-'*55}")
    for gd in range(0, 6):
        ms = gd_buckets.get(gd, [])
        if len(ms) < 20: continue
        n = len(ms)
        print(f"  {gd:<10} {n:>6} {avg([m['total_corners'] for m in ms]):>7.1f} "
              f"{avg([m['total_cards'] for m in ms]):>6.1f} {avg([m['total_fouls'] for m in ms]):>6.1f} "
              f"{avg([m['total_shots'] for m in ms]):>6.1f} {avg([m['total_reds'] for m in ms]):>5.2f}")


# ═══════════════════════════════════════════════════════════════
# 3. POSITION MATCHUP → ALL STATS
# ═══════════════════════════════════════════════════════════════

def analyze_position_matchup_stats(matches):
    print("\n" + "=" * 100)
    print("3. POSITION MATCHUP → ALL STATS")
    print("=" * 100)

    def cat(pos):
        if pos <= 3: return "top3"
        if pos <= 6: return "cl_spots"
        if pos <= 10: return "upper_mid"
        if pos <= 14: return "lower_mid"
        return "relegation"

    # Only use matches after ~5 matchdays where positions are meaningful
    valid = [m for m in matches if m.get("home_pos", 20) != 20 or m.get("away_pos", 20) != 20]

    matchups = defaultdict(list)
    for m in valid:
        hc = cat(m["home_pos"])
        ac = cat(m["away_pos"])
        matchups[f"{hc} vs {ac}"].append(m)

    key_matchups = [
        "top3 vs relegation", "top3 vs top3", "top3 vs lower_mid", "top3 vs upper_mid",
        "cl_spots vs cl_spots", "cl_spots vs relegation",
        "upper_mid vs upper_mid", "lower_mid vs lower_mid",
        "relegation vs relegation", "relegation vs top3",
        "upper_mid vs relegation", "lower_mid vs top3",
    ]

    print(f"\n{'Matchup':<30} {'N':>5} {'Goals':>7} {'Corn':>6} {'Cards':>7} {'Fouls':>7} "
          f"{'Shots':>7} {'SOT':>6} {'Reds':>6} {'HW%':>7} {'O2.5%':>7}")
    print("-" * 105)

    results = {}
    for key in key_matchups:
        ms = matchups.get(key, [])
        if len(ms) < 15: continue
        n = len(ms)
        r = {
            "goals": avg([m["total_goals"] for m in ms]),
            "corners": avg([m["total_corners"] for m in ms]),
            "cards": avg([m["total_cards"] for m in ms]),
            "fouls": avg([m["total_fouls"] for m in ms]),
            "shots": avg([m["total_shots"] for m in ms]),
            "sot": avg([m["total_sot"] for m in ms]),
            "reds": avg([m["total_reds"] for m in ms]),
            "hw": pct(sum(m["is_home_win"] for m in ms), n),
            "o25": pct(sum(1 for m in ms if m["total_goals"] > 2.5), n),
        }
        results[key] = r
        print(f"{key:<30} {n:>5} {r['goals']:>6.2f} {r['corners']:>5.1f} {r['cards']:>6.1f} "
              f"{r['fouls']:>6.1f} {r['shots']:>6.1f} {r['sot']:>5.1f} {r['reds']:>5.2f} "
              f"{r['hw']:>6.1f}% {r['o25']:>6.1f}%")

    # Home/Away splits for top vs bottom
    print(f"\n  HOME vs AWAY STAT SPLITS (Top 3 at home vs away):")
    top_home = [m for m in valid if m["home_pos"] <= 3]
    top_away = [m for m in valid if m["away_pos"] <= 3]

    if top_home and top_away:
        for label, ms in [("Top 3 HOME", top_home), ("Top 3 AWAY", top_away)]:
            n = len(ms)
            hc = avg([m.get("home_corners", 0) for m in ms])
            ac = avg([m.get("away_corners", 0) for m in ms])
            hs = avg([m.get("home_shots", 0) for m in ms])
            as_ = avg([m.get("away_shots", 0) for m in ms])
            hf = avg([m.get("home_fouls", 0) for m in ms])
            af = avg([m.get("away_fouls", 0) for m in ms])
            hca = avg([m.get("home_yellows", 0) + m.get("home_reds", 0) for m in ms])
            aca = avg([m.get("away_yellows", 0) + m.get("away_reds", 0) for m in ms])
            print(f"    {label:<15} ({n:>4}) | Corners H:{hc:.1f} A:{ac:.1f} | Shots H:{hs:.1f} A:{as_:.1f} | "
                  f"Fouls H:{hf:.1f} A:{af:.1f} | Cards H:{hca:.1f} A:{aca:.1f}")

    return results


# ═══════════════════════════════════════════════════════════════
# 4. STAT CORRELATIONS — WHAT PREDICTS WHAT
# ═══════════════════════════════════════════════════════════════

def analyze_stat_correlations(matches):
    print("\n" + "=" * 100)
    print("4. STAT CORRELATIONS — What predicts what?")
    print("=" * 100)

    def pearson(x_list, y_list):
        n = len(x_list)
        if n < 10: return 0
        mx = sum(x_list) / n
        my = sum(y_list) / n
        num = sum((x - mx) * (y - my) for x, y in zip(x_list, y_list))
        dx = math.sqrt(sum((x - mx) ** 2 for x in x_list))
        dy = math.sqrt(sum((y - my) ** 2 for y in y_list))
        if dx == 0 or dy == 0: return 0
        return num / (dx * dy)

    stats = {
        "goals": [m["total_goals"] for m in matches],
        "corners": [m["total_corners"] for m in matches],
        "cards": [m["total_cards"] for m in matches],
        "fouls": [m["total_fouls"] for m in matches],
        "shots": [m["total_shots"] for m in matches],
        "sot": [m["total_sot"] for m in matches],
        "reds": [m["total_reds"] for m in matches],
        "abs_gd": [abs(m["ft_diff"]) for m in matches],
    }

    print(f"\n  CORRELATION MATRIX (Pearson r):")
    keys = list(stats.keys())
    print(f"  {'':>10}", end="")
    for k in keys:
        print(f" {k:>8}", end="")
    print()

    for k1 in keys:
        print(f"  {k1:>10}", end="")
        for k2 in keys:
            r = pearson(stats[k1], stats[k2])
            marker = "██" if abs(r) > 0.3 else ("▓▓" if abs(r) > 0.15 else "  ")
            print(f" {r:>+6.3f}{marker}", end="")
        print()

    # Key correlations with interpretation
    print(f"\n  KEY CORRELATIONS:")
    pairs = [
        ("shots", "corners", "Shots → Corners"),
        ("shots", "goals", "Shots → Goals"),
        ("sot", "goals", "Shots on Target → Goals"),
        ("fouls", "cards", "Fouls → Cards"),
        ("fouls", "corners", "Fouls → Corners"),
        ("corners", "goals", "Corners → Goals"),
        ("cards", "goals", "Cards → Goals"),
        ("abs_gd", "cards", "Goal Diff → Cards"),
        ("abs_gd", "fouls", "Goal Diff → Fouls"),
        ("abs_gd", "corners", "Goal Diff → Corners"),
        ("abs_gd", "shots", "Goal Diff → Shots"),
        ("goals", "corners", "Goals → Corners"),
    ]

    for k1, k2, label in pairs:
        r = pearson(stats[k1], stats[k2])
        strength = "STRONG" if abs(r) > 0.3 else ("moderate" if abs(r) > 0.15 else "weak")
        direction = "positive" if r > 0 else "negative"
        print(f"    r={r:>+.3f} ({strength:>8} {direction:<8}) | {label}")


# ═══════════════════════════════════════════════════════════════
# 5. LEADING TEAM vs TRAILING TEAM STAT PATTERNS
# ═══════════════════════════════════════════════════════════════

def analyze_leading_vs_trailing(matches):
    print("\n" + "=" * 100)
    print("5. LEADING vs TRAILING TEAM — How stats change by game state")
    print("=" * 100)

    # Compare stats when home team wins vs loses vs draws
    home_wins = [m for m in matches if m["is_home_win"]]
    draws = [m for m in matches if m["is_draw"]]
    away_wins = [m for m in matches if m["is_away_win"]]

    print(f"\n  {'Result':<15} {'N':>6} {'H-Corn':>7} {'A-Corn':>7} {'H-Shots':>8} {'A-Shots':>8} "
          f"{'H-Fouls':>8} {'A-Fouls':>8} {'H-Cards':>8} {'A-Cards':>8} {'H-SOT':>6} {'A-SOT':>6}")
    print(f"  {'-'*110}")

    for label, ms in [("Home Win", home_wins), ("Draw", draws), ("Away Win", away_wins)]:
        n = len(ms)
        print(f"  {label:<15} {n:>6} "
              f"{avg([m.get('home_corners',0) for m in ms]):>6.1f} {avg([m.get('away_corners',0) for m in ms]):>6.1f} "
              f"{avg([m.get('home_shots',0) for m in ms]):>7.1f} {avg([m.get('away_shots',0) for m in ms]):>7.1f} "
              f"{avg([m.get('home_fouls',0) for m in ms]):>7.1f} {avg([m.get('away_fouls',0) for m in ms]):>7.1f} "
              f"{avg([m.get('home_yellows',0)+m.get('home_reds',0) for m in ms]):>7.1f} "
              f"{avg([m.get('away_yellows',0)+m.get('away_reds',0) for m in ms]):>7.1f} "
              f"{avg([m.get('home_shots_target',0) for m in ms]):>5.1f} {avg([m.get('away_shots_target',0) for m in ms]):>5.1f}")

    # Derived: winning team stats vs losing team stats (regardless of home/away)
    print(f"\n  WINNER vs LOSER stats (H/A normalized):")
    win_stats = {"corners": [], "shots": [], "sot": [], "fouls": [], "cards": []}
    lose_stats = {"corners": [], "shots": [], "sot": [], "fouls": [], "cards": []}

    for m in matches:
        if m["is_draw"]: continue
        if m["is_home_win"]:
            win_stats["corners"].append(m.get("home_corners", 0))
            win_stats["shots"].append(m.get("home_shots", 0))
            win_stats["sot"].append(m.get("home_shots_target", 0))
            win_stats["fouls"].append(m.get("home_fouls", 0))
            win_stats["cards"].append(m.get("home_yellows", 0) + m.get("home_reds", 0))
            lose_stats["corners"].append(m.get("away_corners", 0))
            lose_stats["shots"].append(m.get("away_shots", 0))
            lose_stats["sot"].append(m.get("away_shots_target", 0))
            lose_stats["fouls"].append(m.get("away_fouls", 0))
            lose_stats["cards"].append(m.get("away_yellows", 0) + m.get("away_reds", 0))
        else:
            win_stats["corners"].append(m.get("away_corners", 0))
            win_stats["shots"].append(m.get("away_shots", 0))
            win_stats["sot"].append(m.get("away_shots_target", 0))
            win_stats["fouls"].append(m.get("away_fouls", 0))
            win_stats["cards"].append(m.get("away_yellows", 0) + m.get("away_reds", 0))
            lose_stats["corners"].append(m.get("home_corners", 0))
            lose_stats["shots"].append(m.get("home_shots", 0))
            lose_stats["sot"].append(m.get("home_shots_target", 0))
            lose_stats["fouls"].append(m.get("home_fouls", 0))
            lose_stats["cards"].append(m.get("home_yellows", 0) + m.get("home_reds", 0))

    for stat in ["corners", "shots", "sot", "fouls", "cards"]:
        w = avg(win_stats[stat])
        l = avg(lose_stats[stat])
        ratio = w / l if l > 0 else 0
        print(f"    {stat:<10}: Winner {w:.2f} vs Loser {l:.2f} (ratio: {ratio:.2f}x)")


# ═══════════════════════════════════════════════════════════════
# 6. SHOTS → CORNERS → GOALS CHAIN
# ═══════════════════════════════════════════════════════════════

def analyze_stat_chains(matches):
    print("\n" + "=" * 100)
    print("6. STAT CHAINS — Shots → Corners → Goals probability")
    print("=" * 100)

    # Bucket by total shots
    print(f"\n  SHOTS → Everything else:")
    print(f"  {'Shots':<12} {'N':>5} {'Goals':>7} {'Corners':>8} {'Cards':>7} {'SOT':>6} {'O2.5%':>7} {'BTTS%':>7}")
    print(f"  {'-'*65}")

    shot_buckets = defaultdict(list)
    for m in matches:
        bucket = (m["total_shots"] // 5) * 5  # 0-4, 5-9, 10-14, etc.
        shot_buckets[bucket].append(m)

    for bucket in sorted(shot_buckets.keys()):
        ms = shot_buckets[bucket]
        if len(ms) < 20: continue
        n = len(ms)
        print(f"  {bucket}-{bucket+4:<8} {n:>5} {avg([m['total_goals'] for m in ms]):>6.2f} "
              f"{avg([m['total_corners'] for m in ms]):>7.1f} {avg([m['total_cards'] for m in ms]):>6.1f} "
              f"{avg([m['total_sot'] for m in ms]):>5.1f} "
              f"{pct(sum(1 for m in ms if m['total_goals']>2.5), n):>6.1f}% "
              f"{pct(sum(1 for m in ms if m['home_goals']>0 and m['away_goals']>0), n):>6.1f}%")

    # Corners → Goals
    print(f"\n  CORNERS → Goals:")
    print(f"  {'Corners':<12} {'N':>5} {'Goals':>7} {'O2.5%':>7} {'BTTS%':>7}")
    print(f"  {'-'*45}")

    corner_buckets = defaultdict(list)
    for m in matches:
        bucket = (m["total_corners"] // 3) * 3
        corner_buckets[bucket].append(m)

    for bucket in sorted(corner_buckets.keys()):
        ms = corner_buckets[bucket]
        if len(ms) < 20: continue
        n = len(ms)
        print(f"  {bucket}-{bucket+2:<8} {n:>5} {avg([m['total_goals'] for m in ms]):>6.2f} "
              f"{pct(sum(1 for m in ms if m['total_goals']>2.5), n):>6.1f}% "
              f"{pct(sum(1 for m in ms if m['home_goals']>0 and m['away_goals']>0), n):>6.1f}%")

    # Fouls → Cards chain
    print(f"\n  FOULS → Cards/Reds:")
    print(f"  {'Fouls':<12} {'N':>5} {'Cards':>7} {'Reds':>6} {'Goals':>7}")
    print(f"  {'-'*45}")

    foul_buckets = defaultdict(list)
    for m in matches:
        bucket = (m["total_fouls"] // 5) * 5
        foul_buckets[bucket].append(m)

    for bucket in sorted(foul_buckets.keys()):
        ms = foul_buckets[bucket]
        if len(ms) < 20: continue
        n = len(ms)
        print(f"  {bucket}-{bucket+4:<8} {n:>5} {avg([m['total_cards'] for m in ms]):>6.1f} "
              f"{avg([m['total_reds'] for m in ms]):>5.2f} {avg([m['total_goals'] for m in ms]):>6.2f}")


# ═══════════════════════════════════════════════════════════════
# 7. SHOT ACCURACY & CONVERSION
# ═══════════════════════════════════════════════════════════════

def analyze_shot_conversion(matches):
    print("\n" + "=" * 100)
    print("7. SHOT ACCURACY & CONVERSION RATES")
    print("=" * 100)

    for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
        lm = [m for m in matches if m["league"] == league]
        n = len(lm)
        total_shots = sum(m["total_shots"] for m in lm)
        total_sot = sum(m["total_sot"] for m in lm)
        total_goals = sum(m["total_goals"] for m in lm)
        accuracy = total_sot / total_shots if total_shots else 0
        conversion = total_goals / total_shots if total_shots else 0
        sot_to_goal = total_goals / total_sot if total_sot else 0
        shots_per_goal = total_shots / total_goals if total_goals else 0
        sot_per_goal = total_sot / total_goals if total_goals else 0

        print(f"\n  {league} ({n} matches)")
        print(f"    Shot accuracy (SOT/Shots): {accuracy:.1%}")
        print(f"    Conversion rate (Goals/Shots): {conversion:.1%}")
        print(f"    SOT → Goal rate: {sot_to_goal:.1%}")
        print(f"    Shots per goal: {shots_per_goal:.1f}")
        print(f"    SOT per goal: {sot_per_goal:.1f}")

    # Home vs Away conversion
    print(f"\n  HOME vs AWAY conversion rates:")
    h_shots = sum(m.get("home_shots", 0) for m in matches)
    h_sot = sum(m.get("home_shots_target", 0) for m in matches)
    h_goals = sum(m["home_goals"] for m in matches)
    a_shots = sum(m.get("away_shots", 0) for m in matches)
    a_sot = sum(m.get("away_shots_target", 0) for m in matches)
    a_goals = sum(m["away_goals"] for m in matches)

    print(f"    Home: {h_sot/h_shots:.1%} accuracy, {h_goals/h_shots:.1%} conversion, {h_goals/h_sot:.1%} SOT→Goal")
    print(f"    Away: {a_sot/a_shots:.1%} accuracy, {a_goals/a_shots:.1%} conversion, {a_goals/a_sot:.1%} SOT→Goal")


# ═══════════════════════════════════════════════════════════════
# 8. HIGH-SCORING vs LOW-SCORING MATCH PROFILES
# ═══════════════════════════════════════════════════════════════

def analyze_match_profiles(matches):
    print("\n" + "=" * 100)
    print("8. MATCH PROFILES — High-scoring vs Low-scoring")
    print("=" * 100)

    profiles = {
        "0-1 goals (low)": [m for m in matches if m["total_goals"] <= 1],
        "2 goals": [m for m in matches if m["total_goals"] == 2],
        "3 goals": [m for m in matches if m["total_goals"] == 3],
        "4 goals": [m for m in matches if m["total_goals"] == 4],
        "5+ goals (high)": [m for m in matches if m["total_goals"] >= 5],
    }

    print(f"\n{'Profile':<22} {'N':>5} {'Corners':>8} {'Cards':>7} {'Fouls':>7} {'Shots':>7} {'SOT':>6} "
          f"{'Reds':>6} {'HW%':>7} {'BTTS%':>7}")
    print("-" * 90)

    for label, ms in profiles.items():
        if not ms: continue
        n = len(ms)
        print(f"{label:<22} {n:>5} {avg([m['total_corners'] for m in ms]):>7.1f} "
              f"{avg([m['total_cards'] for m in ms]):>6.1f} {avg([m['total_fouls'] for m in ms]):>6.1f} "
              f"{avg([m['total_shots'] for m in ms]):>6.1f} {avg([m['total_sot'] for m in ms]):>5.1f} "
              f"{avg([m['total_reds'] for m in ms]):>5.2f} "
              f"{pct(sum(m['is_home_win'] for m in ms), n):>6.1f}% "
              f"{pct(sum(1 for m in ms if m['home_goals']>0 and m['away_goals']>0), n):>6.1f}%")


# ═══════════════════════════════════════════════════════════════
# 9. PER-LEAGUE STAT PROFILES BY CONDITION
# ═══════════════════════════════════════════════════════════════

def analyze_league_stat_profiles(matches):
    print("\n" + "=" * 100)
    print("9. PER-LEAGUE STAT PROFILES UNDER DIFFERENT CONDITIONS")
    print("=" * 100)

    for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
        lm = [m for m in matches if m["league"] == league]
        if not lm: continue

        print(f"\n  {league} ({len(lm)} matches)")

        # Tight (GD ≤ 1) vs Blowout (GD ≥ 3)
        tight = [m for m in lm if abs(m["ft_diff"]) <= 1]
        blowout = [m for m in lm if abs(m["ft_diff"]) >= 3]

        if tight and blowout:
            print(f"    Tight (GD≤1):    Corn:{avg([m['total_corners'] for m in tight]):.1f} "
                  f"Cards:{avg([m['total_cards'] for m in tight]):.1f} "
                  f"Fouls:{avg([m['total_fouls'] for m in tight]):.1f} "
                  f"Shots:{avg([m['total_shots'] for m in tight]):.1f} "
                  f"({len(tight)} matches)")
            print(f"    Blowout (GD≥3):  Corn:{avg([m['total_corners'] for m in blowout]):.1f} "
                  f"Cards:{avg([m['total_cards'] for m in blowout]):.1f} "
                  f"Fouls:{avg([m['total_fouls'] for m in blowout]):.1f} "
                  f"Shots:{avg([m['total_shots'] for m in blowout]):.1f} "
                  f"({len(blowout)} matches)")

        # Top team home vs Bottom team home
        top_home = [m for m in lm if m.get("home_pos", 20) <= 3]
        bot_home = [m for m in lm if m.get("home_pos", 20) >= 16]

        if top_home and bot_home:
            print(f"    Top3 home:       Corn:{avg([m['total_corners'] for m in top_home]):.1f} "
                  f"Cards:{avg([m['total_cards'] for m in top_home]):.1f} "
                  f"Goals:{avg([m['total_goals'] for m in top_home]):.2f} "
                  f"({len(top_home)} matches)")
            print(f"    Bottom5 home:    Corn:{avg([m['total_corners'] for m in bot_home]):.1f} "
                  f"Cards:{avg([m['total_cards'] for m in bot_home]):.1f} "
                  f"Goals:{avg([m['total_goals'] for m in bot_home]):.2f} "
                  f"({len(bot_home)} matches)")

        # 0-0 HT → 2H stats in this league
        zero_ht = [m for m in lm if m["ht_total"] == 0]
        if zero_ht:
            print(f"    0-0 at HT → 2H: {avg([m['2h_goals'] for m in zero_ht]):.2f}g, "
                  f"Corn:{avg([m['total_corners'] for m in zero_ht]):.1f}, "
                  f"Cards:{avg([m['total_cards'] for m in zero_ht]):.1f} "
                  f"({len(zero_ht)} matches)")


# ═══════════════════════════════════════════════════════════════
# 10. CORNER DISTRIBUTION ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_corner_distributions(matches):
    print("\n" + "=" * 100)
    print("10. CORNER DISTRIBUTION — Probability of Over/Under at each line")
    print("=" * 100)

    for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
        lm = [m for m in matches if m["league"] == league]
        if not lm: continue
        n = len(lm)

        print(f"\n  {league} ({n} matches, avg: {avg([m['total_corners'] for m in lm]):.1f}):")
        for line in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]:
            over = pct(sum(1 for m in lm if m["total_corners"] > line), n)
            print(f"    O{line}: {over:.1f}%  |  U{line}: {100-over:.1f}%")

        # By result type
        hw = [m for m in lm if m["is_home_win"]]
        dr = [m for m in lm if m["is_draw"]]
        aw = [m for m in lm if m["is_away_win"]]
        print(f"    By result: HW:{avg([m['total_corners'] for m in hw]):.1f} "
              f"Draw:{avg([m['total_corners'] for m in dr]):.1f} "
              f"AW:{avg([m['total_corners'] for m in aw]):.1f}")

    # Cards distribution
    print(f"\n  CARDS DISTRIBUTION — Over/Under probabilities:")
    for league in ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]:
        lm = [m for m in matches if m["league"] == league]
        n = len(lm)
        print(f"\n  {league} (avg: {avg([m['total_cards'] for m in lm]):.1f}):")
        for line in [2.5, 3.5, 4.5, 5.5, 6.5]:
            over = pct(sum(1 for m in lm if m["total_cards"] > line), n)
            print(f"    O{line}: {over:.1f}%  |  U{line}: {100-over:.1f}%")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 100)
    print("  MATCH STATS DEEP ANALYSIS — Every stat under every condition")
    print("═" * 100)

    matches = load_all()

    analyze_ht_score_to_stats(matches)
    analyze_ft_score_stats(matches)
    analyze_position_matchup_stats(matches)
    analyze_stat_correlations(matches)
    analyze_leading_vs_trailing(matches)
    analyze_stat_chains(matches)
    analyze_shot_conversion(matches)
    analyze_match_profiles(matches)
    analyze_league_stat_profiles(matches)
    analyze_corner_distributions(matches)

    print("\n" + "═" * 100)
    print("  ANALYSIS COMPLETE")
    print("═" * 100)
