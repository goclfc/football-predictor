#!/usr/bin/env python3
"""
Match Simulation Engine — Simulates a full 90-minute football match
using real team statistics and Poisson/probability models.
Generates a minute-by-minute transcript with all events.
"""
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from scipy.stats import poisson

# ============================================================
# REAL DATA: PSG vs Toulouse, April 3 2026
# ============================================================

PSG_SQUAD = [
    # Available players (Barcola & Ruiz OUT)
    {"name": "Donnarumma", "pos": "GK", "number": 99},
    {"name": "Hakimi", "pos": "RB", "number": 2, "cards_risk": 0.15, "goal_threat": 0.03, "assist_chance": 0.08},
    {"name": "Marquinhos", "pos": "CB", "number": 5, "cards_risk": 0.08, "goal_threat": 0.02},
    {"name": "Zabarnyi", "pos": "CB", "number": 4, "cards_risk": 0.12, "goal_threat": 0.01},
    {"name": "Mendes", "pos": "LB", "number": 25, "cards_risk": 0.10, "goal_threat": 0.02, "assist_chance": 0.07},
    {"name": "Vitinha", "pos": "CM", "number": 17, "cards_risk": 0.08, "goal_threat": 0.04, "assist_chance": 0.12},
    {"name": "Zaïre-Emery", "pos": "CM", "number": 33, "cards_risk": 0.06, "goal_threat": 0.05, "assist_chance": 0.08},
    {"name": "João Neves", "pos": "CM", "number": 87, "cards_risk": 0.07, "goal_threat": 0.03, "assist_chance": 0.09},
    {"name": "Dembélé", "pos": "RW", "number": 10, "cards_risk": 0.05, "goal_threat": 0.12, "assist_chance": 0.10},
    {"name": "Gonçalo Ramos", "pos": "ST", "number": 9, "cards_risk": 0.10, "goal_threat": 0.18, "assist_chance": 0.05},
    {"name": "Lee Kang-in", "pos": "LW", "number": 19, "cards_risk": 0.04, "goal_threat": 0.08, "assist_chance": 0.10},
]

PSG_SUBS = [
    {"name": "Mayulu", "pos": "MF", "number": 27, "goal_threat": 0.05},
    {"name": "Asensio", "pos": "FW", "number": 11, "goal_threat": 0.08},
    {"name": "Kolo Muani", "pos": "FW", "number": 23, "goal_threat": 0.10},
]

TOULOUSE_SQUAD = [
    # Missing: Francis, Messali, Cresswell, Hidalgo (suspended), Magri
    {"name": "Restes", "pos": "GK", "number": 1},
    {"name": "Desler", "pos": "RB", "number": 2, "cards_risk": 0.14, "goal_threat": 0.01},
    {"name": "Nicolaisen", "pos": "CB", "number": 3, "cards_risk": 0.15, "goal_threat": 0.01},
    {"name": "McKenzie", "pos": "CB", "number": 4, "cards_risk": 0.20, "goal_threat": 0.01},
    {"name": "Donnum", "pos": "LB", "number": 14, "cards_risk": 0.18, "goal_threat": 0.03, "assist_chance": 0.06},
    {"name": "Sierro", "pos": "CM", "number": 6, "cards_risk": 0.15, "goal_threat": 0.03, "assist_chance": 0.05},
    {"name": "Casseres Jr.", "pos": "CM", "number": 8, "cards_risk": 0.12, "goal_threat": 0.02, "assist_chance": 0.04},
    {"name": "Aboukhlal", "pos": "RW", "number": 7, "cards_risk": 0.08, "goal_threat": 0.06, "assist_chance": 0.06},
    {"name": "Gboho", "pos": "AM", "number": 20, "cards_risk": 0.07, "goal_threat": 0.10, "assist_chance": 0.08},
    {"name": "Dallinga", "pos": "ST", "number": 9, "cards_risk": 0.10, "goal_threat": 0.09, "assist_chance": 0.04},
    {"name": "Onaiwu", "pos": "LW", "number": 18, "cards_risk": 0.08, "goal_threat": 0.05, "assist_chance": 0.05},
]

TOULOUSE_SUBS = [
    {"name": "Suazo", "pos": "MF", "number": 22, "goal_threat": 0.04},
    {"name": "Babicka", "pos": "FW", "number": 15, "goal_threat": 0.06},
]

# Match parameters from real data
MATCH_PARAMS = {
    "home_xg": 2.50,           # PSG expected goals
    "away_xg": 1.00,           # Toulouse expected goals
    "home_possession": 0.675,
    "home_corners_exp": 6.1,
    "away_corners_exp": 4.1,
    "home_cards_exp": 1.0,     # PSG lowest in top 5 leagues
    "away_cards_exp": 2.2,
    "home_shots_exp": 16,
    "away_shots_exp": 8,
    "home_sot_exp": 6,
    "away_sot_exp": 3,
    "home_fouls_exp": 10,
    "away_fouls_exp": 13,
    "total_throwins_exp": 44,
    "referee_card_tendency": 1.0,  # 1.0 = average
}


@dataclass
class MatchEvent:
    minute: int
    event_type: str  # GOAL, CORNER, CARD, SHOT, FOUL, THROW_IN, SUBSTITUTION, HALF_TIME, FULL_TIME, CHANCE, SAVE, OFFSIDE, VAR
    team: str
    player: str = ""
    detail: str = ""
    assist: str = ""
    score_home: int = 0
    score_away: int = 0


def simulate_match() -> Tuple[List[MatchEvent], Dict]:
    """Simulate the full 90 minutes + stoppage time."""
    random.seed()  # True random each run

    events = []
    stats = {
        "home_goals": 0, "away_goals": 0,
        "home_shots": 0, "away_shots": 0,
        "home_sot": 0, "away_sot": 0,
        "home_corners": 0, "away_corners": 0,
        "home_yellow": 0, "away_yellow": 0,
        "home_red": 0, "away_red": 0,
        "home_fouls": 0, "away_fouls": 0,
        "home_throwins": 0, "away_throwins": 0,
        "home_offsides": 0, "away_offsides": 0,
        "home_possession": 67, "away_possession": 33,
        "home_saves": 0, "away_saves": 0,
    }

    p = MATCH_PARAMS

    # Pre-calculate per-minute probabilities
    goal_prob_home = p["home_xg"] / 90
    goal_prob_away = p["away_xg"] / 90
    corner_prob_home = p["home_corners_exp"] / 90
    corner_prob_away = p["away_corners_exp"] / 90
    card_prob_home = p["home_cards_exp"] / 90
    card_prob_away = p["away_cards_exp"] / 90
    foul_prob_home = p["home_fouls_exp"] / 90
    foul_prob_away = p["away_fouls_exp"] / 90
    shot_prob_home = p["home_shots_exp"] / 90
    shot_prob_away = p["away_shots_exp"] / 90
    throwin_prob = p["total_throwins_exp"] / 90

    # Goal-scoring intensity by period (goals cluster in certain periods)
    def period_multiplier(minute):
        if minute <= 15: return 0.8    # slow start
        elif minute <= 30: return 1.1
        elif minute <= 45: return 1.3  # before half time push
        elif minute <= 60: return 1.0  # second half start
        elif minute <= 75: return 1.2
        else: return 1.5              # late game — most goals

    # Track substitutions
    home_subs_made = 0
    away_subs_made = 0
    psg_squad = list(PSG_SQUAD)
    tou_squad = list(TOULOUSE_SQUAD)

    # Simulate minute by minute
    total_minutes = 90 + random.randint(2, 5)  # stoppage time

    for minute in range(1, total_minutes + 1):
        mult = period_multiplier(minute)

        # Half time
        if minute == 46:
            events.append(MatchEvent(45, "HALF_TIME", "", detail=f"Half time. PSG {stats['home_goals']}-{stats['away_goals']} Toulouse"))

        # === POSSESSION PHASES (multiple events per minute possible) ===

        # Throw-ins (common, 1-2 per minute on average)
        if random.random() < throwin_prob:
            team = "PSG" if random.random() < p["home_possession"] else "Toulouse"
            squad = psg_squad if team == "PSG" else tou_squad
            player = random.choice([p for p in squad if p["pos"] != "GK"])
            side = "home" if team == "PSG" else "away"
            stats[f"{side}_throwins"] += 1
            # Only log some throw-ins (they're too common)
            if random.random() < 0.15:
                events.append(MatchEvent(minute, "THROW_IN", team, player["name"],
                    f"Throw-in to {team}", score_home=stats["home_goals"], score_away=stats["away_goals"]))

        # Fouls
        for team, prob, side, squad in [
            ("PSG", foul_prob_home, "home", psg_squad),
            ("Toulouse", foul_prob_away, "away", tou_squad)
        ]:
            if random.random() < prob:
                fouler = random.choice([p for p in squad if p["pos"] != "GK"])
                stats[f"{side}_fouls"] += 1

                # Foul might lead to a card
                card_base = fouler.get("cards_risk", 0.1)
                card_chance = card_base * p["referee_card_tendency"]
                # More cards in second half and late game
                if minute > 60: card_chance *= 1.3
                if minute > 80: card_chance *= 1.5

                if random.random() < card_chance:
                    # Yellow or red?
                    if random.random() < 0.03:  # ~3% chance of red
                        stats[f"{side}_red"] += 1
                        events.append(MatchEvent(minute, "CARD", team, fouler["name"],
                            f"RED CARD! {fouler['name']} is sent off!",
                            score_home=stats["home_goals"], score_away=stats["away_goals"]))
                        squad.remove(fouler)
                    else:
                        stats[f"{side}_yellow"] += 1
                        other_team = "Toulouse" if team == "PSG" else "PSG"
                        victim = random.choice([p for p in (tou_squad if team == "PSG" else psg_squad) if p["pos"] != "GK"])
                        events.append(MatchEvent(minute, "CARD", team, fouler["name"],
                            f"Yellow card for {fouler['name']} ({team}) for a foul on {victim['name']}",
                            score_home=stats["home_goals"], score_away=stats["away_goals"]))
                elif random.random() < 0.3:
                    other_team = "Toulouse" if team == "PSG" else "PSG"
                    victim = random.choice([p for p in (tou_squad if team == "PSG" else psg_squad) if p["pos"] != "GK"])
                    events.append(MatchEvent(minute, "FOUL", team, fouler["name"],
                        f"Foul by {fouler['name']} on {victim['name']}. Free kick {other_team}.",
                        score_home=stats["home_goals"], score_away=stats["away_goals"]))

        # === ATTACKING PHASES ===
        for team, s_prob, side, squad, opp_gk in [
            ("PSG", shot_prob_home * mult, "home", psg_squad, TOULOUSE_SQUAD[0]),
            ("Toulouse", shot_prob_away * mult, "away", tou_squad, PSG_SQUAD[0])
        ]:
            if random.random() < s_prob:
                attackers = [p for p in squad if p.get("goal_threat", 0) > 0]
                if not attackers:
                    continue
                # Weight by goal_threat
                weights = [p.get("goal_threat", 0.05) for p in attackers]
                shooter = random.choices(attackers, weights=weights, k=1)[0]

                stats[f"{side}_shots"] += 1

                # Is it on target? (~40% of shots)
                on_target = random.random() < 0.40

                if on_target:
                    stats[f"{side}_sot"] += 1

                    # Is it a goal?
                    g_prob = goal_prob_home if side == "home" else goal_prob_away
                    # Normalize: if we're shooting on target, goal probability given SoT
                    goal_given_sot = (g_prob * 90) / (p[f"{side}_sot_exp"])
                    goal_given_sot *= mult

                    if random.random() < goal_given_sot:
                        stats[f"{side}_goals"] += 1

                        # Find assister
                        assisters = [p for p in squad if p.get("assist_chance", 0) > 0 and p != shooter]
                        assist_name = ""
                        if assisters and random.random() < 0.75:
                            a_weights = [p.get("assist_chance", 0.05) for p in assisters]
                            assister = random.choices(assisters, weights=a_weights, k=1)[0]
                            assist_name = assister["name"]

                        # Goal descriptions
                        goal_types = [
                            f"GOAL! {shooter['name']} scores for {team}!",
                            f"GOAL! Brilliant finish from {shooter['name']}!",
                            f"GOAL! {shooter['name']} finds the net!",
                            f"GOAL! {shooter['name']} makes no mistake!",
                            f"GOAL! What a strike from {shooter['name']}!",
                        ]
                        detail = random.choice(goal_types)
                        if assist_name:
                            assist_descs = [
                                f"Assisted by {assist_name}.",
                                f"Great pass from {assist_name} to set it up.",
                                f"{assist_name} with the perfect delivery.",
                                f"Lovely through ball from {assist_name}.",
                            ]
                            detail += " " + random.choice(assist_descs)

                        # VAR check on some goals
                        if random.random() < 0.15:
                            detail += " VAR check... GOAL STANDS!"

                        events.append(MatchEvent(minute, "GOAL", team, shooter["name"],
                            detail, assist=assist_name,
                            score_home=stats["home_goals"], score_away=stats["away_goals"]))
                    else:
                        # Saved
                        opp_side = "away" if side == "home" else "home"
                        stats[f"{opp_side}_saves"] += 1
                        save_descs = [
                            f"Shot by {shooter['name']}, saved by {opp_gk['name']}!",
                            f"{shooter['name']} fires on target, but {opp_gk['name']} is equal to it.",
                            f"Good save by {opp_gk['name']} to deny {shooter['name']}.",
                            f"{shooter['name']} forces a save from {opp_gk['name']}.",
                        ]
                        if random.random() < 0.35:
                            events.append(MatchEvent(minute, "SAVE", team, shooter["name"],
                                random.choice(save_descs),
                                score_home=stats["home_goals"], score_away=stats["away_goals"]))
                else:
                    # Off target
                    miss_descs = [
                        f"{shooter['name']} shoots wide.",
                        f"{shooter['name']} fires over the bar.",
                        f"Shot from {shooter['name']}, but it's off target.",
                        f"{shooter['name']} tries from distance, blazes over.",
                    ]
                    if random.random() < 0.25:
                        events.append(MatchEvent(minute, "SHOT", team, shooter["name"],
                            random.choice(miss_descs),
                            score_home=stats["home_goals"], score_away=stats["away_goals"]))

                    # Off-target shot might lead to corner
                    if random.random() < 0.30:
                        stats[f"{side}_corners"] += 1
                        events.append(MatchEvent(minute, "CORNER", team, "",
                            f"Corner kick for {team}.",
                            score_home=stats["home_goals"], score_away=stats["away_goals"]))

        # Corners from general play (crosses blocked, etc.)
        for team, c_prob, side in [
            ("PSG", corner_prob_home * 0.5, "home"),
            ("Toulouse", corner_prob_away * 0.5, "away")
        ]:
            if random.random() < c_prob:
                stats[f"{side}_corners"] += 1
                if random.random() < 0.4:
                    events.append(MatchEvent(minute, "CORNER", team, "",
                        f"Corner kick for {team}.",
                        score_home=stats["home_goals"], score_away=stats["away_goals"]))

        # Offsides
        for team, side in [("PSG", "home"), ("Toulouse", "away")]:
            if random.random() < 0.025:
                stats[f"{side}_offsides"] += 1
                squad = psg_squad if team == "PSG" else tou_squad
                player = random.choice([p for p in squad if p["pos"] in ("ST", "RW", "LW", "FW", "AM")] or squad[1:])
                if random.random() < 0.3:
                    events.append(MatchEvent(minute, "OFFSIDE", team, player["name"],
                        f"Offside against {player['name']} ({team}).",
                        score_home=stats["home_goals"], score_away=stats["away_goals"]))

        # Substitutions (typically 60-80 min)
        if 58 <= minute <= 82:
            if home_subs_made < 3 and random.random() < 0.08:
                if PSG_SUBS:
                    sub_on = PSG_SUBS.pop(0)
                    sub_off = random.choice([p for p in psg_squad if p["pos"] not in ("GK",)])
                    psg_squad.remove(sub_off)
                    psg_squad.append(sub_on)
                    home_subs_made += 1
                    events.append(MatchEvent(minute, "SUBSTITUTION", "PSG", sub_on["name"],
                        f"Substitution PSG: {sub_on['name']} comes on for {sub_off['name']}.",
                        score_home=stats["home_goals"], score_away=stats["away_goals"]))

            if away_subs_made < 3 and random.random() < 0.10:
                if TOULOUSE_SUBS:
                    sub_on = TOULOUSE_SUBS.pop(0)
                    sub_off = random.choice([p for p in tou_squad if p["pos"] not in ("GK",)])
                    tou_squad.remove(sub_off)
                    tou_squad.append(sub_on)
                    away_subs_made += 1
                    events.append(MatchEvent(minute, "SUBSTITUTION", "Toulouse", sub_on["name"],
                        f"Substitution Toulouse: {sub_on['name']} comes on for {sub_off['name']}.",
                        score_home=stats["home_goals"], score_away=stats["away_goals"]))

    # Full time
    events.append(MatchEvent(total_minutes, "FULL_TIME", "",
        detail=f"FULL TIME! PSG {stats['home_goals']}-{stats['away_goals']} Toulouse"))

    # Sort by minute
    events.sort(key=lambda e: (e.minute, ["HALF_TIME","FULL_TIME","GOAL","CARD","SUBSTITUTION","CORNER","SAVE","SHOT","FOUL","OFFSIDE","THROW_IN","CHANCE","VAR"].index(e.event_type) if e.event_type in ["HALF_TIME","FULL_TIME","GOAL","CARD","SUBSTITUTION","CORNER","SAVE","SHOT","FOUL","OFFSIDE","THROW_IN","CHANCE","VAR"] else 99))

    return events, stats


def generate_transcript_html(events: List[MatchEvent], stats: Dict, output_path: str):
    """Generate a beautiful HTML match transcript."""

    # Build events HTML
    events_html = ""
    for e in events:
        icon = {
            "GOAL": "⚽", "CORNER": "🚩", "CARD": "🟨" if "Yellow" in e.detail else "🟥",
            "FOUL": "⚠️", "SHOT": "💨", "SAVE": "🧤", "SUBSTITUTION": "🔄",
            "THROW_IN": "📍", "HALF_TIME": "⏸️", "FULL_TIME": "🏁",
            "OFFSIDE": "🚫", "VAR": "📺", "CHANCE": "❗"
        }.get(e.event_type, "•")

        css_class = e.event_type.lower().replace("_", "-")
        team_class = "psg" if e.team == "PSG" else "toulouse" if e.team == "Toulouse" else "neutral"
        score_display = f"{e.score_home} - {e.score_away}" if e.event_type == "GOAL" else ""

        minute_display = f"{e.minute}'" if e.minute <= 90 else f"90+{e.minute - 90}'"

        events_html += f"""
        <div class="event {css_class} {team_class}">
            <div class="event-time">{minute_display}</div>
            <div class="event-icon">{icon}</div>
            <div class="event-detail">
                <span class="event-text">{e.detail}</span>
                {"<span class='event-score'>" + score_display + "</span>" if score_display else ""}
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PSG vs Toulouse — Match Simulation</title>
<style>
  :root {{
    --bg: #0c1021; --surface: #141b2d; --surface2: #1c2540;
    --border: #2a3555; --text: #e8ecf4; --text2: #7d8bb0;
    --psg-color: #004170; --psg-light: #0066a8;
    --tou-color: #6a1b7d; --tou-light: #9c27b0;
    --gold: #ffd700; --green: #22c55e; --red: #ef4444; --yellow: #eab308;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}

  /* Header */
  .match-header {{
    background: linear-gradient(135deg, var(--psg-color), #1a1a2e, var(--tou-color));
    border-radius: 16px; padding: 32px; text-align: center; margin-bottom: 24px;
    border: 1px solid var(--border);
  }}
  .match-title {{ font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 2px; }}
  .match-teams {{ display: flex; justify-content: center; align-items: center; gap: 32px; margin: 20px 0; }}
  .team-name {{ font-size: 28px; font-weight: 700; }}
  .team-name.home {{ color: #5ea3e0; }}
  .team-name.away {{ color: #c77dff; }}
  .match-score {{ font-size: 56px; font-weight: 800; color: var(--gold); letter-spacing: 4px; }}
  .match-info {{ color: var(--text2); font-size: 13px; margin-top: 8px; }}

  /* Stats Grid */
  .stats-grid {{
    display: grid; grid-template-columns: 1fr auto 1fr; gap: 8px;
    background: var(--surface); border-radius: 12px; padding: 20px; margin-bottom: 24px;
    border: 1px solid var(--border);
  }}
  .stats-grid h3 {{ grid-column: 1/-1; text-align:center; font-size:14px; color:var(--text2);
    text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; }}
  .stat-row {{ display: contents; }}
  .stat-home, .stat-away {{ font-size: 18px; font-weight: 700; padding: 6px 0; }}
  .stat-home {{ text-align: right; color: #5ea3e0; }}
  .stat-away {{ text-align: left; color: #c77dff; }}
  .stat-label {{ text-align: center; font-size: 12px; color: var(--text2); padding: 8px 16px;
    text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat-bar {{ grid-column: 1/-1; display:flex; height:4px; border-radius:2px; overflow:hidden; margin: 2px 0 8px; }}
  .stat-bar .home-bar {{ background: #5ea3e0; }}
  .stat-bar .away-bar {{ background: #c77dff; }}

  /* Events Timeline */
  .timeline {{ background: var(--surface); border-radius: 12px; padding: 20px; border: 1px solid var(--border); }}
  .timeline h3 {{ font-size: 14px; color: var(--text2); text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 16px; text-align: center; }}

  .event {{
    display: flex; align-items: flex-start; gap: 12px; padding: 8px 12px;
    border-radius: 8px; margin-bottom: 4px; transition: background 0.15s;
  }}
  .event:hover {{ background: var(--surface2); }}
  .event-time {{ min-width: 40px; font-size: 13px; color: var(--text2); font-weight: 600; text-align: right; padding-top: 2px; }}
  .event-icon {{ font-size: 16px; min-width: 24px; text-align: center; }}
  .event-detail {{ flex: 1; }}
  .event-text {{ font-size: 14px; line-height: 1.5; }}
  .event-score {{
    display: inline-block; background: var(--gold); color: #000; font-weight: 800;
    padding: 2px 10px; border-radius: 4px; margin-left: 8px; font-size: 13px;
  }}

  /* Event type styling */
  .event.goal {{ background: rgba(255,215,0,0.08); border-left: 3px solid var(--gold); }}
  .event.goal .event-text {{ font-weight: 700; font-size: 15px; }}
  .event.card {{ background: rgba(234,179,8,0.06); }}
  .event.card.event-text {{ color: var(--yellow); }}
  .event.half-time, .event.full-time {{
    background: var(--surface2); justify-content: center; text-align: center;
    border: 1px dashed var(--border); margin: 16px 0;
  }}
  .event.half-time .event-text, .event.full-time .event-text {{
    font-weight: 700; color: var(--text2); font-size: 13px; text-transform: uppercase; letter-spacing: 1px;
  }}
  .event.substitution {{ opacity: 0.85; }}
  .event.psg .event-time {{ color: #5ea3e0; }}
  .event.toulouse .event-time {{ color: #c77dff; }}

  .footer {{ text-align:center; color:var(--text2); font-size:11px; margin-top:24px; padding:16px; }}
</style>
</head>
<body>
<div class="container">

  <div class="match-header">
    <div class="match-title">Ligue 1 — Parc des Princes — April 3, 2026</div>
    <div class="match-teams">
      <div class="team-name home">Paris Saint-Germain</div>
      <div class="match-score">{stats['home_goals']} - {stats['away_goals']}</div>
      <div class="team-name away">Toulouse</div>
    </div>
    <div class="match-info">Full Time | Attendance: 47,929</div>
  </div>

  <div class="stats-grid">
    <h3>Match Statistics</h3>

    <div class="stat-home">{stats['home_possession']}%</div>
    <div class="stat-label">Possession</div>
    <div class="stat-away">{stats['away_possession']}%</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_possession']}%"></div>
      <div class="away-bar" style="width:{stats['away_possession']}%"></div>
    </div>

    <div class="stat-home">{stats['home_shots']}</div>
    <div class="stat-label">Total Shots</div>
    <div class="stat-away">{stats['away_shots']}</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_shots']*100/max(stats['home_shots']+stats['away_shots'],1):.0f}%"></div>
      <div class="away-bar" style="width:{stats['away_shots']*100/max(stats['home_shots']+stats['away_shots'],1):.0f}%"></div>
    </div>

    <div class="stat-home">{stats['home_sot']}</div>
    <div class="stat-label">Shots on Target</div>
    <div class="stat-away">{stats['away_sot']}</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_sot']*100/max(stats['home_sot']+stats['away_sot'],1):.0f}%"></div>
      <div class="away-bar" style="width:{stats['away_sot']*100/max(stats['home_sot']+stats['away_sot'],1):.0f}%"></div>
    </div>

    <div class="stat-home">{stats['home_corners']}</div>
    <div class="stat-label">Corners</div>
    <div class="stat-away">{stats['away_corners']}</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_corners']*100/max(stats['home_corners']+stats['away_corners'],1):.0f}%"></div>
      <div class="away-bar" style="width:{stats['away_corners']*100/max(stats['home_corners']+stats['away_corners'],1):.0f}%"></div>
    </div>

    <div class="stat-home">{stats['home_fouls']}</div>
    <div class="stat-label">Fouls</div>
    <div class="stat-away">{stats['away_fouls']}</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_fouls']*100/max(stats['home_fouls']+stats['away_fouls'],1):.0f}%"></div>
      <div class="away-bar" style="width:{stats['away_fouls']*100/max(stats['home_fouls']+stats['away_fouls'],1):.0f}%"></div>
    </div>

    <div class="stat-home">{stats['home_yellow']}</div>
    <div class="stat-label">Yellow Cards</div>
    <div class="stat-away">{stats['away_yellow']}</div>
    <div class="stat-bar">
      <div class="home-bar" style="width:{stats['home_yellow']*100/max(stats['home_yellow']+stats['away_yellow'],1):.0f}%"></div>
      <div class="away-bar" style="width:{stats['away_yellow']+0.01*100/max(stats['home_yellow']+stats['away_yellow'],1):.0f}%"></div>
    </div>

    <div class="stat-home">{stats['home_offsides']}</div>
    <div class="stat-label">Offsides</div>
    <div class="stat-away">{stats['away_offsides']}</div>

    <div class="stat-home">{stats['home_saves']}</div>
    <div class="stat-label">Saves</div>
    <div class="stat-away">{stats['away_saves']}</div>
  </div>

  <div class="timeline">
    <h3>Match Timeline</h3>
    {events_html}
  </div>

  <div class="footer">
    Simulated using Poisson probability models with real team data<br>
    PSG xG: 2.50 | Toulouse xG: 1.00 | Based on 2025/26 season statistics
  </div>

</div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return output_path


if __name__ == "__main__":
    events, stats = simulate_match()
    output = generate_transcript_html(events, stats,
        "/sessions/intelligent-sleepy-bell/mnt/predictions/psg_vs_toulouse_simulation.html")

    print(f"Score: PSG {stats['home_goals']}-{stats['away_goals']} Toulouse")
    print(f"Shots: {stats['home_shots']}-{stats['away_shots']} (On target: {stats['home_sot']}-{stats['away_sot']})")
    print(f"Corners: {stats['home_corners']}-{stats['away_corners']} (Total: {stats['home_corners']+stats['away_corners']})")
    print(f"Cards: {stats['home_yellow']+stats['home_red']}-{stats['away_yellow']+stats['away_red']} (Total: {stats['home_yellow']+stats['home_red']+stats['away_yellow']+stats['away_red']})")
    print(f"Fouls: {stats['home_fouls']}-{stats['away_fouls']}")
    print(f"Saves: {stats['home_saves']}-{stats['away_saves']}")
    print(f"\nDashboard: {output}")

    # Check our bets
    total_cards = stats['home_yellow'] + stats['home_red'] + stats['away_yellow'] + stats['away_red']
    total_corners = stats['home_corners'] + stats['away_corners']
    total_goals = stats['home_goals'] + stats['away_goals']
    print(f"\n--- BET CHECK ---")
    print(f"Cards Under 3.5: {'WIN' if total_cards < 4 else 'LOSE'} (Total cards: {total_cards})")
    print(f"Corners Over 9.5: {'WIN' if total_corners > 9 else 'LOSE'} (Total corners: {total_corners})")
    print(f"BTTS Yes: {'WIN' if stats['home_goals'] > 0 and stats['away_goals'] > 0 else 'LOSE'}")
    print(f"Over 2.5 Goals: {'WIN' if total_goals > 2 else 'LOSE'} (Total goals: {total_goals})")
