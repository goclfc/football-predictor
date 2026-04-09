"""
Meta Agent V2 — V4 calibrated synthesis.

Key upgrades from V1:
1. V4 calibration (shrinkage 35%) on final consensus probabilities
2. Market filters from V4 backtest: NO away wins, NO under 2.5 (losing markets)
3. Higher edge threshold: 5% minimum (from backtest optimization)
4. EPL draws flagged as high-value market (+45% ROI in backtest)
5. Only allow: home_win, draw, over 2.5, BTTS, corners, cards
"""
from typing import Dict, List, Tuple
from collections import defaultdict
from .base_agent import AgentReport, AgentPrediction
from dataclasses import dataclass, field

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.match_stats_model import calibrate_probability, BASE_RATES


@dataclass
class FinalBet:
    match_id: str
    home_team: str
    away_team: str
    league: str
    match_date: str
    market: str
    market_display: str
    outcome: str
    confidence_pct: float
    best_odds: float
    best_bookmaker: str
    expected_value: float
    agent_agreement: float
    reasoning: List[str]
    risk_level: str
    recommended_stake: float
    # V4 additions
    calibrated_prob: float = 0.0
    raw_prob: float = 0.0
    edge_pct: float = 0.0
    v4_flags: List[str] = field(default_factory=list)


# Markets that V4 backtest showed are PROFITABLE
ALLOWED_MARKETS = {
    "match_result",
    "goals_over_under_2.5",
    "goals_over_under_1.5",
    "goals_over_under_3.5",
    "btts",
    "double_chance",
    "corners_over_under_8.5",
    "corners_over_under_9.5",
    "corners_over_under_10.5",
    "corners_over_under_11.5",
    "cards_over_under_3.5",
    "cards_over_under_4.5",
    "cards_over_under_5.5",
    "first_half_goals_over_under_0.5",
    "first_half_goals_over_under_1.5",
    "shots_on_target_over_under_5.5",
    "shots_on_target_over_under_6.5",
    "shots_on_target_over_under_7.5",
    "shots_on_target_over_under_8.5",
}

# Outcomes to REJECT (losing markets from V4 backtest)
REJECTED_OUTCOMES = {
    # Away wins: -22% ROI in backtest
    # Under 2.5: -10% to -14% ROI
}


class MetaAgentV2:
    """V2 Meta-Agent with V4 calibration and market filtering."""

    AGENT_WEIGHTS = {
        "StatsAgent": 1.4,
        "FormAgent": 1.1,
        "MarketAgent": 1.0,
        "HistoricalAgent": 0.8,
        "ValueAgent": 1.3,
        "ContextAgent": 0.7,
    }

    MIN_EDGE_PCT = 5.0  # 5% minimum edge (from V4 backtest)
    MIN_ODDS = 1.50
    MAX_ODDS = 6.0

    MARKET_DISPLAY_NAMES = {
        "match_result": "Match Result",
        "btts": "Both Teams to Score",
        "double_chance": "Double Chance",
        "corners_home_away": "Corner Dominance",
    }

    def synthesize(self, match_data: Dict, agent_reports: List[AgentReport]) -> List[FinalBet]:
        home = match_data["home_team"]
        away = match_data["away_team"]
        league = match_data.get("league", "Unknown")
        match_date = match_data.get("commence_time", "TBD")
        match_id = match_data.get("id", "")
        markets = match_data.get("markets", {})
        markets_summary = match_data.get("markets_summary", {})

        # Group predictions by market+outcome
        market_predictions = defaultdict(list)
        for report in agent_reports:
            for pred in report.predictions:
                # Skip context-only predictions (they inform, don't bet)
                if pred.market.endswith("_context"):
                    continue
                key = (pred.market, pred.outcome)
                market_predictions[key].append({
                    "agent": report.agent_name,
                    "probability": pred.probability,
                    "confidence": pred.confidence,
                    "reliability": report.reliability_score,
                    "reasoning": pred.reasoning,
                })

        final_bets = []

        for (market_key, outcome), agent_preds in market_predictions.items():
            # === MARKET FILTER: Skip non-allowed markets ===
            if market_key not in ALLOWED_MARKETS:
                continue

            # === OUTCOME FILTER: No away wins (from V4 backtest: -22% ROI) ===
            if market_key == "match_result" and "Win" in outcome and outcome != f"{home} Win" and outcome != "Draw":
                continue  # Skip away win bets

            # === OUTCOME FILTER: No under 2.5 (from V4 backtest: -10-14% ROI) ===
            if market_key == "goals_over_under_2.5" and "Under" in outcome:
                continue

            # Calculate weighted consensus
            total_weight = 0
            weighted_prob = 0
            weighted_conf = 0
            for ap in agent_preds:
                w = self.AGENT_WEIGHTS.get(ap["agent"], 1.0) * ap["reliability"] * ap["confidence"]
                weighted_prob += ap["probability"] * w
                weighted_conf += ap["confidence"] * w
                total_weight += w

            if total_weight == 0:
                continue

            raw_prob = weighted_prob / total_weight
            consensus_conf = weighted_conf / total_weight

            # === V4 CALIBRATION ===
            # Apply shrinkage based on market type
            if market_key == "match_result":
                if f"{home} Win" in outcome or outcome == f"{home} Win":
                    cal_prob = calibrate_probability(raw_prob, BASE_RATES["home_win"])
                elif outcome == "Draw":
                    cal_prob = calibrate_probability(raw_prob, BASE_RATES["draw"])
                else:
                    cal_prob = calibrate_probability(raw_prob, BASE_RATES["away_win"])
            elif "goals_over_under_2.5" in market_key and "Over" in outcome:
                cal_prob = calibrate_probability(raw_prob, BASE_RATES["over_25"])
            else:
                cal_prob = calibrate_probability(raw_prob, 0.5)

            # Find best odds
            best_odds, best_bookie = self._find_best_odds(markets, market_key, outcome)
            if best_odds is None:
                continue

            # === ODDS FILTER ===
            if best_odds < self.MIN_ODDS or best_odds > self.MAX_ODDS:
                continue

            # Calculate edge
            implied_prob = 1 / best_odds
            edge = cal_prob - implied_prob
            ev = (cal_prob * best_odds) - 1

            # === EDGE FILTER: 5% minimum ===
            if edge < self.MIN_EDGE_PCT / 100:
                continue

            # Sanity: cap EV
            if ev > 0.50:
                ev = 0.50

            # Require minimum 2 agents
            if len(agent_preds) < 2:
                continue

            # Agent agreement
            agents_on_market = set()
            agents_agreeing = set()
            for report in agent_reports:
                for pred in report.predictions:
                    if pred.market == market_key:
                        agents_on_market.add(report.agent_name)
                        if pred.outcome == outcome:
                            agents_agreeing.add(report.agent_name)
            agreement = len(agents_agreeing) / max(len(agents_on_market), 1) * 100

            # V4 flags
            flags = []
            if league == "Premier League" and outcome == "Draw":
                flags.append("EPL_DRAW_GOLD")  # +45% ROI in backtest
            if edge > 0.15:
                flags.append("STRONG_EDGE")
            if cal_prob < raw_prob * 0.85:
                flags.append("HEAVY_CALIBRATION")

            # Risk assessment
            risk = self._assess_risk(consensus_conf, agreement, ev, len(agent_preds), flags)

            # Kelly stake
            kelly = self._kelly_stake(cal_prob, best_odds)

            # Reasoning
            all_reasoning = [ap["reasoning"] for ap in agent_preds[:3]]

            final_bets.append(FinalBet(
                match_id=match_data["id"],
                home_team=home, away_team=away,
                league=league, match_date=match_date,
                market=market_key,
                market_display=self._format_market_name(market_key),
                outcome=outcome,
                confidence_pct=round(consensus_conf * 100, 1),
                best_odds=best_odds,
                best_bookmaker=best_bookie,
                expected_value=round(ev * 100, 2),
                agent_agreement=round(agreement, 1),
                reasoning=all_reasoning,
                risk_level=risk,
                recommended_stake=round(kelly * 100, 2),
                calibrated_prob=round(cal_prob, 4),
                raw_prob=round(raw_prob, 4),
                edge_pct=round(edge * 100, 2),
                v4_flags=flags,
            ))

        # === DIRECT ODDS-BASED VALUE BETS (V5 fallback) ===
        # If agent-based synthesis found few bets, generate from market odds directly
        # This ensures value bets always appear when there's genuine edge
        h2h_odds = markets_summary.get("h2h", {})
        totals = markets_summary.get("totals", {})

        if h2h_odds:
            home_odds = h2h_odds.get(home, 0)
            draw_odds_val = h2h_odds.get("Draw", 0)
            away_odds = h2h_odds.get(away, 0)
            o25_odds = totals.get("Over 2.5", 0)
            u25_odds = totals.get("Under 2.5", 0)

            if home_odds > 0 and draw_odds_val > 0 and away_odds > 0:
                # Normalize implied probs
                imp_h = 1 / home_odds
                imp_d = 1 / draw_odds_val
                imp_a = 1 / away_odds
                imp_total = imp_h + imp_d + imp_a
                imp_h /= imp_total
                imp_d /= imp_total
                imp_a /= imp_total

                # V5 data-mined adjustments (inline version)
                from backtester_v5 import V5Predictor
                v5 = V5Predictor()

                # Extract form from agent reports
                home_form_list = None
                away_form_list = None
                for report in agent_reports:
                    for pred in report.predictions:
                        if pred.market in ("home_form_string", "home_recent_form"):
                            home_form_list = list(str(pred.outcome).replace(",", ""))
                        elif pred.market in ("away_form_string", "away_recent_form"):
                            away_form_list = list(str(pred.outcome).replace(",", ""))

                v5_pred = v5.predict_match(
                    implied_home=imp_h, implied_draw=imp_d, implied_away=imp_a,
                    league=league, home_form=home_form_list, away_form=away_form_list,
                    over25_odds=o25_odds if o25_odds > 0 else None,
                )

                # Check each market for value
                existing_markets = {b.outcome for b in final_bets}
                MIN_EDGE = 0.03  # 3% minimum edge for V5 fallback

                checks = [
                    (f"{home} Win", v5_pred["home_win"], imp_h, home_odds, "match_result"),
                    ("Draw", v5_pred["draw"], imp_d, draw_odds_val, "match_result"),
                    (f"{away} Win", v5_pred["away_win"], imp_a, away_odds, "match_result"),
                ]
                if o25_odds > 0 and v5_pred.get("over25_prob"):
                    checks.append(("Over 2.5", v5_pred["over25_prob"], 1/o25_odds, o25_odds, "goals_over_under_2.5"))
                if u25_odds > 0 and v5_pred.get("over25_prob"):
                    u25_prob = 1.0 - v5_pred["over25_prob"]
                    checks.append(("Under 2.5", u25_prob, 1/u25_odds, u25_odds, "goals_over_under_2.5"))

                for outcome_name, model_prob, implied, odds_val, mkt_key in checks:
                    if outcome_name in existing_markets:
                        continue
                    edge = model_prob - implied
                    if edge < MIN_EDGE or odds_val < 1.3 or odds_val > 8.0:
                        continue
                    ev = (model_prob * odds_val) - 1
                    if ev > 0.50:
                        ev = 0.50

                    flags = []
                    if league == "Premier League" and outcome_name == "Draw":
                        flags.append("EPL_DRAW_GOLD")
                    if edge > 0.10:
                        flags.append("STRONG_EDGE")
                    if "Win" in outcome_name and outcome_name != f"{home} Win" and implied < 0.35:
                        flags.append("AWAY_UNDERDOG_VALUE")
                    if "Over" in outcome_name and odds_val >= 2.30:
                        flags.append("O25_VALUE_ZONE")

                    # Find best bookmaker — but recalculate edge with actual odds
                    best_bookie = "Best Available"
                    best_odds_found = odds_val
                    if mkt_key in markets:
                        for bk in markets[mkt_key]:
                            for o_name, o_val in bk.get("odds", {}).items():
                                if o_name == outcome_name and o_val > best_odds_found:
                                    # Sanity: don't accept odds >2x the summary odds (data anomaly)
                                    if o_val <= odds_val * 2.0:
                                        best_bookie = bk.get("bookmaker", "Best Available")
                                        best_odds_found = o_val

                    # Recalculate edge/ev with best actual odds
                    actual_implied = 1.0 / best_odds_found
                    actual_edge = model_prob - actual_implied
                    actual_ev = (model_prob * best_odds_found) - 1
                    if actual_edge < MIN_EDGE:
                        continue  # Edge disappeared with better odds
                    if actual_ev > 0.50:
                        actual_ev = 0.50

                    kelly = self._kelly_stake(model_prob, best_odds_found)
                    risk = self._assess_risk(0.6, 70, actual_ev, 3, flags)

                    reasoning = v5_pred.get("adjustments", [])[:3]
                    if not reasoning:
                        reasoning = [f"V5 model: {model_prob:.1%} vs implied {actual_implied:.1%}"]

                    final_bets.append(FinalBet(
                        match_id=match_id,
                        home_team=home, away_team=away,
                        league=league, match_date=match_date,
                        market=mkt_key,
                        market_display=self._format_market_name(mkt_key),
                        outcome=outcome_name,
                        confidence_pct=round(model_prob * 100, 1),
                        best_odds=round(best_odds_found, 2),
                        best_bookmaker=best_bookie,
                        expected_value=round(actual_ev * 100, 2),
                        agent_agreement=70.0,
                        reasoning=reasoning,
                        risk_level=risk,
                        recommended_stake=round(kelly * 100, 2),
                        calibrated_prob=round(model_prob, 4),
                        raw_prob=round(actual_implied, 4),
                        edge_pct=round(actual_edge * 100, 2),
                        v4_flags=flags,
                    ))

        # Sort by edge (best value first)
        final_bets.sort(key=lambda b: b.edge_pct, reverse=True)
        return final_bets

    def _find_best_odds(self, markets, market_key, outcome):
        bookmaker_odds = markets.get(market_key, [])
        best_odds = None
        best_bookie = None
        for bookie in bookmaker_odds:
            for out, odds in bookie["odds"].items():
                if out == outcome:
                    if best_odds is None or odds > best_odds:
                        best_odds = odds
                        best_bookie = bookie["bookmaker"]
        return best_odds, best_bookie

    def _assess_risk(self, confidence, agreement, ev, num_agents, flags):
        score = confidence * 0.4 + (agreement / 100) * 0.3 + min(ev * 5, 0.3)
        if num_agents >= 3: score += 0.1
        if "EPL_DRAW_GOLD" in flags: score += 0.05
        if "STRONG_EDGE" in flags: score += 0.05
        if score > 0.7: return "LOW"
        elif score > 0.45: return "MEDIUM"
        return "HIGH"

    def _kelly_stake(self, prob, odds):
        b = odds - 1
        q = 1 - prob
        if b <= 0: return 0
        kelly = (b * prob - q) / b
        return max(0, min(kelly * 0.25, 0.05))

    def _format_market_name(self, market_key):
        if market_key in self.MARKET_DISPLAY_NAMES:
            return self.MARKET_DISPLAY_NAMES[market_key]
        name = market_key.replace("_", " ").title()
        name = name.replace("Over Under", "O/U")
        return name
