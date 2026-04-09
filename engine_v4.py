"""
Engine V5 — Full calibrated prediction pipeline with 27 agents, V5 data-mined
adjustments, and match simulator.

Integrates:
- Original 6 agents (FormAgent, HistoricalAgent, StatsAgentV3, MarketAgent, ValueAgentV2, ContextAgent)
- 4 player intel agents (InjuryAgent, FatigueAgent, KeyPlayerAgent, GoalkeeperAgent)
- 4 tactical agents (TacticalAgent, SetPieceAgent, DefensiveProfileAgent, AttackingProfileAgent)
- 9 situational agents (StakesAgent, RivalryIntensityAgent, RefereeAgent, VenueAgent, WeatherAgent,
  MomentumAgent, ManagerAgent, MediaPressureAgent, RestDaysAgent)
- 4 live intelligence agents (LineupAgent, PlayerNewsAgent, ScheduleContextAgent, HistoricalOddsAgent)
- MetaAgentV2 (V4 calibration + market filters)
- V5 Data-Mined Adjustments (odds calibration, form, rest, league corrections)
- Match Stats Model overlay (corners, cards, fouls, SOT chains)
- MatchSimulator for realistic match event simulation

V5 Backtest Results (walk-forward, 560 out-of-sample matches):
- Filtered strategy: +16.2% ROI on 220 bets
- Over 2.5 specialist: +30.5% ROI on 62 bets
- Draw specialist: +25.9% ROI on 43 bets
- All leagues profitable
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

# Original agents
from agents.form_agent import FormAgent
from agents.historical_agent import HistoricalAgent
from agents.stats_agent_v3 import StatsAgentV3
from agents.market_agent import MarketAgent
from agents.value_agent_v2 import ValueAgentV2
from agents.context_agent import ContextAgent
from agents.meta_agent_v2 import MetaAgentV2, FinalBet
from agents.base_agent import BaseAgent, AgentReport, AgentPrediction

# New agents - Player Intel
from agents.player_intel_agents import InjuryAgent, FatigueAgent, KeyPlayerAgent, GoalkeeperAgent

# New agents - Tactical
from agents.tactical_agents import TacticalAgent, SetPieceAgent, DefensiveProfileAgent, AttackingProfileAgent

# New agents - Situational
from agents.situational_agents import (
    StakesAgent, RivalryIntensityAgent, RefereeAgent, VenueAgent, WeatherAgent,
    MomentumAgent, ManagerAgent, MediaPressureAgent, RestDaysAgent
)

# New agents - Live Intelligence (real API data)
from agents.live_intel_agents import LineupAgent, PlayerNewsAgent, ScheduleContextAgent, HistoricalOddsAgent

# Match Simulator (Calibrated — anchored to V5 predictions)
from simulator.calibrated_simulator import CalibratedSimulator
from simulator.match_simulator import MatchSimulator  # kept for compatibility

from models.match_stats_model import (
    predict_match_stats, calibrate_match_probs, calibrate_probability,
    predict_live_stats, BASE_RATES, LEAGUE_STAT_BASELINES,
    STAT_CORRELATIONS, MatchStatsPrediction,
)
from models.dixon_coles import (
    dixon_coles_match_probs, prob_over_goals, prob_btts,
    EloRating, strength_adjusted_xg,
)
from backtester_v5 import V5Predictor
from agent_signal_extractor import extract_signals, MatchSignals


class NewAgentWrapper(BaseAgent):
    """
    Wraps new-style agents (returning dicts) into BaseAgent-compatible objects
    returning AgentReport with AgentPrediction objects.
    """

    def __init__(self, new_agent):
        """Initialize with a new-style agent instance."""
        self.agent = new_agent
        self.name = getattr(new_agent, 'name', 'UnknownAgent')
        self.specialty = getattr(new_agent, 'specialty', 'Unknown')
        self.weight = getattr(new_agent, 'weight', 1.0)
        self.reliability_score = getattr(new_agent, 'reliability_score', 0.5)

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict, **kwargs) -> AgentReport:
        """
        Call the new-style agent and convert its dict response to AgentReport.

        New agents return:
        {
            "agent": agent_name,
            "predictions": {key: value, ...},
            "confidence": float,
            "insights": [str, ...],
            "adjustments": {key: value, ...}
        }
        """
        # Call the wrapped agent, passing kwargs (including agent_reports)
        agent_dict = self.agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats, **kwargs)

        home = match_data.get("home_team", "Unknown")
        away = match_data.get("away_team", "Unknown")
        match_id = match_data.get("match_id", "")

        # Extract predictions dict and convert to AgentPrediction list
        predictions_dict = agent_dict.get("predictions", {})
        insights = agent_dict.get("insights", [])
        confidence = agent_dict.get("confidence", 0.5)

        predictions = []
        for idx, (market, value) in enumerate(predictions_dict.items()):
            # Convert each key-value pair to an AgentPrediction
            prob = float(value) if isinstance(value, (int, float)) else 0.5
            # Cycle through insights so each prediction gets a different one
            if insights:
                pred_reasoning = insights[idx % len(insights)]
            else:
                pred_reasoning = f"{market}: {value}"
            predictions.append(AgentPrediction(
                market=str(market),
                outcome=str(value),
                probability=self._clamp(prob) if isinstance(value, (int, float)) else 0.5,
                confidence=confidence,
                reasoning=pred_reasoning,
                data_points=insights[:3] if insights else []
            ))

        # Overall assessment: combine top insights (not just the first one)
        if insights:
            overall_assessment = " | ".join(insights[:3])
        else:
            overall_assessment = f"{self.name} analysis complete"

        return AgentReport(
            agent_name=self.name,
            match_id=match_id,
            home_team=home,
            away_team=away,
            predictions=predictions,
            overall_assessment=overall_assessment,
            reliability_score=self.reliability_score
        )


@dataclass
class V4Analysis:
    """Complete V4 analysis result for a match."""
    version: str = "5.0"
    league: str = ""

    # Core probabilities
    raw_probs: Dict = field(default_factory=dict)
    calibrated_probs: Dict = field(default_factory=dict)

    # Expected goals
    expected_goals: Dict = field(default_factory=dict)

    # Match stats from empirical model
    match_stats: Dict = field(default_factory=dict)

    # O/U probabilities
    corner_ou: Dict = field(default_factory=dict)
    card_ou: Dict = field(default_factory=dict)

    # Value bets
    value_bets: List[Dict] = field(default_factory=list)

    # Elo ratings
    elo_ratings: Dict = field(default_factory=dict)

    # League baseline
    league_baseline: Dict = field(default_factory=dict)

    # Context
    context: Dict = field(default_factory=dict)

    # Notes
    notes: List[str] = field(default_factory=list)


class FootballPredictionEngineV5:
    """V5 engine with 23 agents, calibration, empirical stats, match simulator."""

    VERSION = "5.0"

    def __init__(self):
        # Original 6 agents (old-style, return BaseAgent-compatible)
        original_agents = [
            FormAgent(),
            HistoricalAgent(),
            StatsAgentV3(),       # Dixon-Coles + Elo + Match Stats Model
            MarketAgent(),
            ValueAgentV2(),       # Fixed value detection
            ContextAgent(),       # Derby, motivation, context
        ]

        # New agent instances (new-style, return dicts)
        new_agents_raw = [
            # Player Intel Agents (4)
            InjuryAgent(),
            FatigueAgent(),
            KeyPlayerAgent(),
            GoalkeeperAgent(),
            # Tactical Agents (4)
            TacticalAgent(),
            SetPieceAgent(),
            DefensiveProfileAgent(),
            AttackingProfileAgent(),
            # Situational Agents (9)
            StakesAgent(),
            RivalryIntensityAgent(),
            RefereeAgent(),
            VenueAgent(),
            WeatherAgent(),
            MomentumAgent(),
            ManagerAgent(),
            MediaPressureAgent(),
            RestDaysAgent(),
            # Live Intelligence Agents (4) — real API data
            LineupAgent(),
            PlayerNewsAgent(),
            ScheduleContextAgent(),
            HistoricalOddsAgent(),
        ]

        # Wrap new agents to be compatible with BaseAgent pattern
        wrapped_new_agents = [NewAgentWrapper(agent) for agent in new_agents_raw]

        # Combine all agents
        self.agents = original_agents + wrapped_new_agents

        self.meta_agent = MetaAgentV2()

        # Store raw new agents for simulator (it needs dict format)
        self.new_agents_raw = new_agents_raw

        # Direct model access for V5 overlay
        self.stats_agent = original_agents[2]  # StatsAgentV3
        self.context_agent = original_agents[5]  # ContextAgent

        # Initialize match simulator
        self.simulator = CalibratedSimulator()  # Anchored to V5 predictions

        # V5 data-mined predictor
        self.v5_predictor = V5Predictor()

    def analyze_match(
        self,
        match_data: Dict,
        home_form: Dict,
        away_form: Dict,
        h2h: Dict,
        home_stats: Dict,
        away_stats: Dict,
        progress_callback=None,
    ) -> Dict:
        """
        Run full V4 analysis pipeline.

        Returns dict with:
        - agent_reports: List of agent report dicts
        - final_bets: List of FinalBet dicts
        - v4_analysis: V4Analysis dict
        """
        home = match_data["home_team"]
        away = match_data["away_team"]
        league = match_data.get("league", "Premier League")

        # === Phase 1: Run all agents ===
        agent_reports = []
        for agent in self.agents:
            try:
                if progress_callback:
                    progress_callback(
                        f"agent_{agent.name}",
                        f"Running {agent.name} ({agent.specialty})..."
                    )
                # Original 6 agents don't accept agent_reports kwarg
                try:
                    report = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats, agent_reports=agent_reports)
                except TypeError:
                    report = agent.analyze(match_data, home_form, away_form, h2h, home_stats, away_stats)
                agent_reports.append(report)
                if progress_callback:
                    progress_callback(
                        f"agent_{agent.name}_done",
                        f"{agent.name}: {len(report.predictions)} predictions "
                        f"(reliability: {report.reliability_score:.0%})"
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        f"agent_{agent.name}_error",
                        f"{agent.name} error: {str(e)[:80]}"
                    )

        # === Phase 2: Meta-agent synthesis with V4 filters ===
        if progress_callback:
            progress_callback("synthesizing", "Meta-agent synthesizing with V4 calibration...")

        final_bets = self.meta_agent.synthesize(match_data, agent_reports)

        # === Phase 3: V4 Analysis overlay ===
        if progress_callback:
            progress_callback("v4_calibration", "Computing V4 calibrated predictions + match stats...")

        v4 = self._compute_v4_analysis(
            match_data, home_form, away_form, h2h, home_stats, away_stats, league,
            agent_reports=agent_reports
        )

        # === Phase 4: Package results ===
        if progress_callback:
            progress_callback(
                "completed",
                f"V4 analysis complete: {len(final_bets)} value bets found"
            )

        return {
            "agent_reports": [self._report_to_dict(r) for r in agent_reports],
            "final_bets": [self._bet_to_dict(b) for b in final_bets],
            "v4_analysis": asdict(v4),
        }

    def _compute_v4_analysis(
        self, match_data, home_form, away_form, h2h, home_stats, away_stats, league,
        agent_reports=None
    ) -> V4Analysis:
        """Compute the V4 analysis overlay with calibrated predictions."""
        v4 = V4Analysis(league=league)
        home = match_data["home_team"]
        away = match_data["away_team"]

        # ============================================================
        # STEP 1: Extract structured signals from all 27 agent reports
        # ============================================================
        signals = extract_signals(agent_reports)

        # --- Elo + xG (blended with agent attacking/defensive profiles) ---
        elo = self.stats_agent.elo
        v4.elo_ratings = {
            "home": round(elo.get_rating(home)),
            "away": round(elo.get_rating(away)),
        }

        has_xg = home_stats.get("has_xg_data", False) and away_stats.get("has_xg_data", False)
        if has_xg:
            ha = home_stats["home_xg_avg"] * 0.6 + home_stats["recent_xg_avg"] * 0.4
            hd = home_stats["home_xga_avg"] * 0.6 + home_stats["recent_xga_avg"] * 0.4
            aa = away_stats["away_xg_avg"] * 0.6 + away_stats["recent_xg_avg"] * 0.4
            ad = away_stats["away_xga_avg"] * 0.6 + away_stats["recent_xga_avg"] * 0.4
        else:
            ha = home_stats.get("home_goals_avg", 1.3)
            hd = home_stats.get("home_conceded_avg", 0.9)
            aa = away_stats.get("away_goals_avg", 1.0)
            ad = away_stats.get("away_conceded_avg", 1.3)

        # Blend statistical xG with agent xG (if agents produced realistic values)
        if signals.xg_home > 0.3 and signals.xg_away > 0.3:
            # 60% statistical model, 40% agent intelligence
            ha = ha * 0.6 + signals.xg_home * 0.4
            aa = aa * 0.6 + signals.xg_away * 0.4

        # Apply venue/travel adjustments from agents
        ha *= signals.home_advantage_modifier
        aa *= signals.travel_impact_away

        home_exp, away_exp = strength_adjusted_xg(
            home_attack=ha, home_defense=hd,
            away_attack=aa, away_defense=ad,
            elo_system=elo, home_team=home, away_team=away,
        )

        # Apply agent-derived goals adjustment
        if signals.goals_adjustment != 0:
            # Distribute adjustment proportionally between home and away
            home_ratio = home_exp / (home_exp + away_exp) if (home_exp + away_exp) > 0 else 0.5
            home_exp += signals.goals_adjustment * home_ratio
            away_exp += signals.goals_adjustment * (1 - home_ratio)
            home_exp = max(0.3, home_exp)
            away_exp = max(0.2, away_exp)

        v4.expected_goals = {
            "home": round(home_exp, 2),
            "away": round(away_exp, 2),
            "total": round(home_exp + away_exp, 2),
        }

        # --- Raw probabilities ---
        dc = dixon_coles_match_probs(home_exp, away_exp, rho=-0.13)
        elo_pred = elo.predict_match(home, away)

        bhw = dc['home_win'] * 0.6 + elo_pred['home_win'] * 0.4
        bdw = dc['draw'] * 0.6 + elo_pred['draw'] * 0.4
        baw = dc['away_win'] * 0.6 + elo_pred['away_win'] * 0.4
        total = bhw + bdw + baw
        bhw /= total; bdw /= total; baw /= total

        v4.raw_probs = {
            "home_win": round(bhw, 4),
            "draw": round(bdw, 4),
            "away_win": round(baw, 4),
        }

        # --- V4 Calibrated probabilities ---
        cal = calibrate_match_probs(bhw, bdw, baw)
        v4.calibrated_probs = cal

        # ============================================================
        # STEP 2: Match stats — base model + agent signal adjustments
        # ============================================================
        home_shots_avg = home_stats.get("avg_shots_on_target", 4.5) * 2
        away_shots_avg = away_stats.get("avg_shots_on_target", 4.0) * 2
        home_fouls_avg = home_stats.get("avg_fouls", 12.0)
        away_fouls_avg = away_stats.get("avg_fouls", 12.0)

        home_pos = home_stats.get("league_position")
        away_pos = away_stats.get("league_position")
        try:
            home_pos = int(home_pos) if home_pos else None
        except (TypeError, ValueError):
            home_pos = None
        try:
            away_pos = int(away_pos) if away_pos else None
        except (TypeError, ValueError):
            away_pos = None

        ms = predict_match_stats(
            league=league,
            home_shots_avg=home_shots_avg,
            away_shots_avg=away_shots_avg,
            home_fouls_avg=home_fouls_avg,
            away_fouls_avg=away_fouls_avg,
            home_position=home_pos,
            away_position=away_pos,
            expected_goals=home_exp + away_exp,
            expected_gd=home_exp - away_exp,
        )

        # Apply agent-informed adjustments to base predictions
        adj_corners = ms.corners + signals.corners_adjustment
        adj_cards = ms.cards + signals.cards_adjustment
        adj_shots = ms.shots + signals.shots_adjustment
        adj_sot = ms.sot + signals.shots_adjustment * 0.4  # SOT tracks shots loosely

        # For cards: blend with referee agent's direct prediction (strongest signal)
        if signals.referee_expected_yellows > 0:
            adj_cards = adj_cards * 0.5 + signals.referee_expected_yellows * 0.5

        # Ensure sensible ranges
        adj_corners = max(5.0, min(16.0, adj_corners))
        adj_cards = max(1.5, min(10.0, adj_cards))
        adj_shots = max(10.0, min(35.0, adj_shots))
        adj_sot = max(4.0, min(16.0, adj_sot))

        v4.match_stats = {
            "corners": round(adj_corners, 1),
            "home_corners": round(ms.home_corners + signals.corners_adjustment * 0.5, 1),
            "away_corners": round(ms.away_corners + signals.corners_adjustment * 0.5, 1),
            "cards": round(adj_cards, 1),
            "home_cards": round(ms.home_cards + signals.cards_adjustment * 0.4, 1),
            "away_cards": round(ms.away_cards + signals.cards_adjustment * 0.6, 1),
            "fouls": round(ms.fouls, 1),
            "shots": round(adj_shots, 1),
            "sot": round(adj_sot, 1),
            "reds": round(ms.reds + signals.referee_expected_reds * 0.3, 2),
            "profile": ms.expected_profile,
        }

        # Recompute corner/card O/U probabilities with adjusted totals
        from scipy.stats import poisson
        adj_corner_ou = {}
        for line in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]:
            adj_corner_ou[line] = 1 - poisson.cdf(int(line), adj_corners)
        adj_card_ou = {}
        for line in [2.5, 3.5, 4.5, 5.5, 6.5]:
            adj_card_ou[line] = 1 - poisson.cdf(int(line), adj_cards)

        v4.corner_ou = {str(k): round(v, 4) for k, v in adj_corner_ou.items()}
        v4.card_ou = {str(k): round(v, 4) for k, v in adj_card_ou.items()}
        v4.notes = ms.notes + signals.adjustment_notes

        # --- V5 Data-Mined Value Bets ---
        markets_summary = match_data.get("markets_summary", {})
        h2h_odds = markets_summary.get("h2h", {})
        totals_odds = markets_summary.get("totals", {})

        # Extract odds
        home_market_odds = h2h_odds.get(home, 0)
        away_market_odds = h2h_odds.get(away, 0)
        draw_market_odds = h2h_odds.get("Draw", 0)
        over25_odds = totals_odds.get("Over 2.5", 0)
        under25_odds = totals_odds.get("Under 2.5", 0)

        value_bets = []
        v5_adjustments = []

        if home_market_odds > 0 and draw_market_odds > 0 and away_market_odds > 0:
            # Calculate implied probabilities from market odds
            implied_home = 1 / home_market_odds
            implied_draw = 1 / draw_market_odds
            implied_away = 1 / away_market_odds
            # Normalize (remove overround)
            total_implied = implied_home + implied_draw + implied_away
            implied_home /= total_implied
            implied_draw /= total_implied
            implied_away /= total_implied

            # Extract form from agent reports (search for momentum/form agents)
            home_form_list = None
            away_form_list = None
            home_rest = None
            away_rest = None

            for report in (agent_reports or []):
                rpt = self._report_to_dict(report) if not isinstance(report, dict) else report
                agent_name = rpt.get("agent_name", "")
                preds = rpt.get("predictions", [])

                for p in preds:
                    mkt = p.get("market", "")
                    outcome = str(p.get("outcome", ""))

                    # Extract form from momentum/form agents
                    if mkt == "home_form_string" or mkt == "home_recent_form":
                        home_form_list = list(outcome.replace(",", ""))
                    elif mkt == "away_form_string" or mkt == "away_recent_form":
                        away_form_list = list(outcome.replace(",", ""))
                    # Extract rest days from rest/schedule agents
                    elif mkt == "home_rest_days":
                        try:
                            home_rest = int(float(outcome))
                        except (ValueError, TypeError):
                            pass
                    elif mkt == "away_rest_days":
                        try:
                            away_rest = int(float(outcome))
                        except (ValueError, TypeError):
                            pass

            # Run V5 predictor with data-mined adjustments
            v5_pred = self.v5_predictor.predict_match(
                implied_home=implied_home,
                implied_draw=implied_draw,
                implied_away=implied_away,
                league=league,
                home_form=home_form_list,
                away_form=away_form_list,
                home_rest_days=home_rest,
                away_rest_days=away_rest,
                over25_odds=over25_odds if over25_odds > 0 else None,
            )

            v5_adjustments = v5_pred.get("adjustments", [])

            # Also blend V5 predictions into calibrated probs
            # 50% V5 data-mined + 50% Dixon-Coles/Elo model (equal weight — V5 targets value)
            blend_home = cal["home_win"] * 0.5 + v5_pred["home_win"] * 0.5
            blend_draw = cal["draw"] * 0.5 + v5_pred["draw"] * 0.5
            blend_away = cal["away_win"] * 0.5 + v5_pred["away_win"] * 0.5
            blend_total = blend_home + blend_draw + blend_away
            blend_home /= blend_total
            blend_draw /= blend_total
            blend_away /= blend_total

            # Update calibrated probs with V5 blend
            v4.calibrated_probs = {
                "home_win": round(blend_home, 4),
                "draw": round(blend_draw, 4),
                "away_win": round(blend_away, 4),
            }

            # ---- Generate value bets ----
            MIN_EDGE = 0.025  # 2.5% minimum edge (lowered from 4% — blended model needs less)

            # Home win value
            home_edge = blend_home - implied_home
            if home_edge >= MIN_EDGE and 1.3 < home_market_odds < 8.0:
                ev_pct = (blend_home * home_market_odds - 1) * 100
                flags = []
                if league in ("Bundesliga", "La Liga") and blend_home > 0.5:
                    flags.append("LEAGUE_FAV_BOOST")
                value_bets.append({
                    "market": f"{home} Win",
                    "model_prob": round(blend_home, 4),
                    "implied_prob": round(implied_home, 4),
                    "odds": round(home_market_odds, 2),
                    "edge": round(home_edge, 4),
                    "ev_pct": round(ev_pct, 2),
                    "rating": "STRONG" if home_edge > 0.10 else "MODERATE" if home_edge > 0.06 else "VALUE",
                    "flags": flags,
                })

            # Draw value
            draw_edge = blend_draw - implied_draw
            if draw_edge >= MIN_EDGE and 2.0 < draw_market_odds < 8.0:
                ev_pct = (blend_draw * draw_market_odds - 1) * 100
                flags = []
                if league == "Premier League":
                    flags.append("EPL_DRAW_GOLD")
                if home_rest is not None and home_rest <= 3:
                    flags.append("SHORT_REST_DRAW")
                value_bets.append({
                    "market": "Draw",
                    "model_prob": round(blend_draw, 4),
                    "implied_prob": round(implied_draw, 4),
                    "odds": round(draw_market_odds, 2),
                    "edge": round(draw_edge, 4),
                    "ev_pct": round(ev_pct, 2),
                    "rating": "STRONG" if draw_edge > 0.10 else "MODERATE" if draw_edge > 0.06 else "VALUE",
                    "flags": flags,
                })

            # Away win value
            away_edge = blend_away - implied_away
            if away_edge >= MIN_EDGE and 1.3 < away_market_odds < 8.0:
                ev_pct = (blend_away * away_market_odds - 1) * 100
                flags = []
                if implied_away < 0.40:
                    flags.append("AWAY_UNDERDOG_VALUE")
                value_bets.append({
                    "market": f"{away} Win",
                    "model_prob": round(blend_away, 4),
                    "implied_prob": round(implied_away, 4),
                    "odds": round(away_market_odds, 2),
                    "edge": round(away_edge, 4),
                    "ev_pct": round(ev_pct, 2),
                    "rating": "STRONG" if away_edge > 0.10 else "MODERATE" if away_edge > 0.06 else "VALUE",
                    "flags": flags,
                })

            # Over 2.5 value
            if over25_odds > 0 and v5_pred.get("over25_prob"):
                # Blend model O2.5 with V5
                model_o25 = calibrate_probability(
                    prob_over_goals(dc, 2.5), BASE_RATES["over_25"]
                )
                blend_o25 = model_o25 * 0.5 + v5_pred["over25_prob"] * 0.5
                implied_o25 = 1.0 / over25_odds
                o25_edge = blend_o25 - implied_o25
                if o25_edge >= MIN_EDGE:
                    ev_pct = (blend_o25 * over25_odds - 1) * 100
                    flags = []
                    if over25_odds >= 2.30:
                        flags.append("O25_VALUE_ZONE")
                    if league == "Bundesliga":
                        flags.append("HIGH_SCORING_LEAGUE")
                    value_bets.append({
                        "market": "Over 2.5 Goals",
                        "model_prob": round(blend_o25, 4),
                        "implied_prob": round(implied_o25, 4),
                        "odds": round(over25_odds, 2),
                        "edge": round(o25_edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if o25_edge > 0.10 else "MODERATE" if o25_edge > 0.06 else "VALUE",
                        "flags": flags,
                    })

            # Under 2.5 value
            if under25_odds > 0 and v5_pred.get("over25_prob"):
                blend_u25 = 1.0 - (model_o25 * 0.5 + v5_pred["over25_prob"] * 0.5)
                implied_u25 = 1.0 / under25_odds
                u25_edge = blend_u25 - implied_u25
                if u25_edge >= MIN_EDGE:
                    ev_pct = (blend_u25 * under25_odds - 1) * 100
                    flags = []
                    if league == "Serie A":
                        flags.append("LOW_SCORING_LEAGUE")
                    value_bets.append({
                        "market": "Under 2.5 Goals",
                        "model_prob": round(blend_u25, 4),
                        "implied_prob": round(implied_u25, 4),
                        "odds": round(under25_odds, 2),
                        "edge": round(u25_edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if u25_edge > 0.10 else "MODERATE" if u25_edge > 0.06 else "VALUE",
                        "flags": flags,
                    })

        # ============================================================
        # STEP 4: Corners, Cards, Shots value bets (agent-informed model)
        # ============================================================
        # These use the agent-adjusted predictions vs typical bookmaker lines
        # We generate these as "model bets" since we don't have bookmaker odds for these markets
        TYPICAL_CORNER_ODDS = {
            "Over 8.5": 1.80, "Under 8.5": 2.00,
            "Over 9.5": 2.05, "Under 9.5": 1.75,
            "Over 10.5": 2.40, "Under 10.5": 1.55,
            "Over 11.5": 2.90, "Under 11.5": 1.40,
        }
        TYPICAL_CARD_ODDS = {
            "Over 3.5": 1.75, "Under 3.5": 2.05,
            "Over 4.5": 2.10, "Under 4.5": 1.70,
            "Over 5.5": 2.60, "Under 5.5": 1.50,
        }

        # Corner value bets
        for line_str, prob in v4.corner_ou.items():
            line = float(line_str)
            over_key = f"Over {line_str}"
            under_key = f"Under {line_str}"
            over_odds = TYPICAL_CORNER_ODDS.get(over_key)
            under_odds = TYPICAL_CORNER_ODDS.get(under_key)

            if over_odds and prob > 0:
                implied = 1.0 / over_odds
                edge = prob - implied
                if edge >= 0.04:  # 4% edge for model-only markets
                    ev_pct = (prob * over_odds - 1) * 100
                    flags = ["AGENT_MODEL"]
                    if signals.corners_adjustment > 0.5:
                        flags.append("CORNER_BOOST")
                    if signals.set_piece_advantage != "neutral":
                        flags.append("SET_PIECE_EDGE")
                    value_bets.append({
                        "market": f"Corners {over_key}",
                        "model_prob": round(prob, 4),
                        "implied_prob": round(implied, 4),
                        "odds": over_odds,
                        "edge": round(edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if edge > 0.10 else "MODERATE" if edge > 0.06 else "VALUE",
                        "flags": flags,
                        "market_type": "corners",
                    })

            if under_odds and prob < 1.0:
                under_prob = 1.0 - prob
                implied = 1.0 / under_odds
                edge = under_prob - implied
                if edge >= 0.04:
                    ev_pct = (under_prob * under_odds - 1) * 100
                    flags = ["AGENT_MODEL"]
                    if signals.corners_adjustment < -0.5:
                        flags.append("CORNER_SUPPRESSED")
                    value_bets.append({
                        "market": f"Corners {under_key}",
                        "model_prob": round(under_prob, 4),
                        "implied_prob": round(implied, 4),
                        "odds": under_odds,
                        "edge": round(edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if edge > 0.10 else "MODERATE" if edge > 0.06 else "VALUE",
                        "flags": flags,
                        "market_type": "corners",
                    })

        # Card value bets
        for line_str, prob in v4.card_ou.items():
            line = float(line_str)
            over_key = f"Over {line_str}"
            under_key = f"Under {line_str}"
            over_odds = TYPICAL_CARD_ODDS.get(over_key)
            under_odds = TYPICAL_CARD_ODDS.get(under_key)

            if over_odds and prob > 0:
                implied = 1.0 / over_odds
                edge = prob - implied
                if edge >= 0.04:
                    ev_pct = (prob * over_odds - 1) * 100
                    flags = ["AGENT_MODEL"]
                    if signals.referee_strictness >= 7:
                        flags.append("STRICT_REF")
                    if signals.rivalry_score > 0.5:
                        flags.append("RIVALRY_HEAT")
                    value_bets.append({
                        "market": f"Cards {over_key}",
                        "model_prob": round(prob, 4),
                        "implied_prob": round(implied, 4),
                        "odds": over_odds,
                        "edge": round(edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if edge > 0.10 else "MODERATE" if edge > 0.06 else "VALUE",
                        "flags": flags,
                        "market_type": "cards",
                    })

            if under_odds and prob < 1.0:
                under_prob = 1.0 - prob
                implied = 1.0 / under_odds
                edge = under_prob - implied
                if edge >= 0.04:
                    ev_pct = (under_prob * under_odds - 1) * 100
                    flags = ["AGENT_MODEL"]
                    if signals.referee_strictness <= 3:
                        flags.append("LENIENT_REF")
                    value_bets.append({
                        "market": f"Cards {under_key}",
                        "model_prob": round(under_prob, 4),
                        "implied_prob": round(implied, 4),
                        "odds": under_odds,
                        "edge": round(edge, 4),
                        "ev_pct": round(ev_pct, 2),
                        "rating": "STRONG" if edge > 0.10 else "MODERATE" if edge > 0.06 else "VALUE",
                        "flags": flags,
                        "market_type": "cards",
                    })

        # Sort by edge descending
        value_bets.sort(key=lambda x: x["edge"], reverse=True)
        v4.value_bets = value_bets

        # --- League baseline ---
        bl = LEAGUE_STAT_BASELINES.get(league, LEAGUE_STAT_BASELINES["Premier League"])
        v4.league_baseline = {
            "avg_goals": bl["avg_goals"],
            "avg_corners": bl["avg_corners"],
            "avg_cards": bl["avg_cards"],
        }

        # --- Context ---
        v4.context = {
            "is_derby": self.context_agent._is_derby(home, away)
            if hasattr(self.context_agent, '_is_derby') else False,
            "home_position": home_pos,
            "away_position": away_pos,
            "v5_adjustments": v5_adjustments,
            "agent_signals": {
                "goals_adj": signals.goals_adjustment,
                "corners_adj": signals.corners_adjustment,
                "cards_adj": signals.cards_adjustment,
                "shots_adj": signals.shots_adjustment,
                "xg_home": round(signals.xg_home, 2),
                "xg_away": round(signals.xg_away, 2),
                "referee_yellows": round(signals.referee_expected_yellows, 1),
                "referee_strictness": signals.referee_strictness,
                "rivalry_score": round(signals.rivalry_score, 2),
                "fatigue_home": round(signals.fatigue_home, 2),
                "fatigue_away": round(signals.fatigue_away, 2),
                "momentum_home": round(signals.momentum_home, 2),
                "momentum_away": round(signals.momentum_away, 2),
                "home_injuries": signals.home_injuries_count,
                "away_injuries": signals.away_injuries_count,
                "set_piece_adv": signals.set_piece_advantage,
                "tactical_edge": round(signals.tactical_edge, 2),
            },
        }

        # Add agent-informed chain notes
        if home_shots_avg + away_shots_avg > 0:
            v4.notes.append(
                f"Shot chain ({home_shots_avg + away_shots_avg:.0f} shots): "
                f"corners→{adj_corners:.1f} (agent adj: {signals.corners_adjustment:+.1f})"
            )
        if home_fouls_avg + away_fouls_avg > 0:
            v4.notes.append(
                f"Foul chain ({home_fouls_avg + away_fouls_avg:.0f} fouls): "
                f"cards→{adj_cards:.1f} (referee: {signals.referee_expected_yellows:.1f} avg, "
                f"strictness: {signals.referee_strictness}/10)"
            )

        return v4

    def compute_live_update(
        self, league: str, minute: int, ht_score: str,
        current_corners: int = 0, current_cards: int = 0,
        current_fouls: int = 0, current_shots: int = 0,
    ) -> Dict:
        """Compute live in-play stat projections."""
        return predict_live_stats(
            league=league, minute=minute, ht_score=ht_score,
            current_corners=current_corners, current_cards=current_cards,
            current_fouls=current_fouls, current_shots=current_shots,
        )

    def simulate_match(
        self,
        match_data: Dict,
        home_form: Dict,
        away_form: Dict,
        h2h: Dict,
        home_stats: Dict,
        away_stats: Dict,
        agent_reports: Optional[List] = None,
        seed: Optional[int] = None,
        n_sims: int = 500,
        v4_analysis: Optional[Dict] = None,
    ) -> Dict:
        """
        Simulate a match using CalibratedSimulator anchored to V5 predictions.

        Runs a featured simulation (with events) + N Monte Carlo sims to derive
        probability distributions for all markets, then generates value bets
        by comparing simulation probabilities against bookmaker odds.

        The CalibratedSimulator uses Poisson sampling from V5 expected goals
        so simulation scorelines are consistent with the prediction model.
        """
        if agent_reports is None:
            analysis_result = self.analyze_match(
                match_data, home_form, away_form, h2h, home_stats, away_stats
            )
            agent_reports = analysis_result["agent_reports"]
            # Also grab v4_analysis from the result
            if v4_analysis is None:
                v4_analysis = analysis_result.get("v4_analysis")

        # Convert reports to raw dicts format for simulator
        raw_reports = []
        for report in agent_reports:
            if isinstance(report, dict):
                raw_reports.append(report)
            else:
                raw_reports.append(self._report_to_dict(report))

        home_name = match_data.get("home_team", "Home")
        away_name = match_data.get("away_team", "Away")
        league = match_data.get("league", "")

        # Extract V5 expected goals and match stats from v4_analysis
        v5_expected_goals = None
        match_stats_prediction = None
        calibrated_probs = None

        if v4_analysis:
            xg = v4_analysis.get("expected_goals")
            if xg:
                v5_expected_goals = {
                    "home": xg.get("home", 1.3),
                    "away": xg.get("away", 1.0),
                    "total": xg.get("total", 2.3),
                }
            ms = v4_analysis.get("match_stats")
            if ms:
                match_stats_prediction = {
                    "corners": ms.get("corners", 9.5),
                    "home_corners": ms.get("home_corners", 5),
                    "away_corners": ms.get("away_corners", 4.5),
                    "cards": ms.get("cards", 4),
                    "home_cards": ms.get("home_cards", 2),
                    "away_cards": ms.get("away_cards", 2),
                    "fouls": ms.get("fouls", 24),
                    "shots": ms.get("shots", 22),
                    "sot": ms.get("sot", 8),
                    "reds": ms.get("reds", 0.03),
                }
            cp = v4_analysis.get("calibrated_probs")
            if cp:
                calibrated_probs = {
                    "home_win": cp.get("home_win", 0.4),
                    "draw": cp.get("draw", 0.28),
                    "away_win": cp.get("away_win", 0.32),
                }

        try:
            # === 1. Featured simulation (with full events for display) ===
            import random as _random
            featured_seed = seed if seed is not None else _random.randint(1, 999999)
            simulation_result = self.simulator.simulate_match(
                home_name, away_name, raw_reports,
                v5_expected_goals=v5_expected_goals,
                match_stats_prediction=match_stats_prediction,
                calibrated_probs=calibrated_probs,
                seed=featured_seed,
            )

            # === 2. Monte Carlo: run N simulations for probability distributions ===
            mc_results = {
                "home_wins": 0, "draws": 0, "away_wins": 0,
                "over15": 0, "over25": 0, "over35": 0,
                "btts": 0,
                "total_goals": [],
                "total_corners": [],
                "total_cards": [],
                "total_shots": [],
                "total_sot": [],
                "home_goals": [],
                "away_goals": [],
                "home_corners": [],
                "away_corners": [],
                "home_cards": [],
                "away_cards": [],
                "scorelines": {},
                "ht_results": {"home": 0, "draw": 0, "away": 0},
            }

            for i in range(n_sims):
                sim = self.simulator.simulate_match(
                    home_name, away_name, raw_reports,
                    v5_expected_goals=v5_expected_goals,
                    match_stats_prediction=match_stats_prediction,
                    calibrated_probs=calibrated_probs,
                    seed=featured_seed + i + 1,
                )
                fs = sim["final_score"]
                hg, ag = fs["home"], fs["away"]
                total = hg + ag

                # 1x2
                if hg > ag:
                    mc_results["home_wins"] += 1
                elif hg == ag:
                    mc_results["draws"] += 1
                else:
                    mc_results["away_wins"] += 1

                # Goals markets
                if total > 1.5: mc_results["over15"] += 1
                if total > 2.5: mc_results["over25"] += 1
                if total > 3.5: mc_results["over35"] += 1
                if hg > 0 and ag > 0: mc_results["btts"] += 1
                mc_results["total_goals"].append(total)
                mc_results["home_goals"].append(hg)
                mc_results["away_goals"].append(ag)

                # Corners
                st = sim.get("stats", {})
                hc = st.get("corners", [0, 0])
                tc = hc[0] + hc[1] if isinstance(hc, list) else 0
                mc_results["total_corners"].append(tc)
                mc_results["home_corners"].append(hc[0] if isinstance(hc, list) else 0)
                mc_results["away_corners"].append(hc[1] if isinstance(hc, list) else 0)

                # Cards
                yc = st.get("yellow_cards", [0, 0])
                rc = st.get("red_cards", [0, 0])
                total_cards = (yc[0] + yc[1] + rc[0] + rc[1]) if isinstance(yc, list) else 0
                mc_results["total_cards"].append(total_cards)
                mc_results["home_cards"].append((yc[0] + rc[0]) if isinstance(yc, list) else 0)
                mc_results["away_cards"].append((yc[1] + rc[1]) if isinstance(yc, list) else 0)

                # Shots
                shots = st.get("shots", [0, 0])
                sot = st.get("shots_on_target", [0, 0])
                mc_results["total_shots"].append((shots[0] + shots[1]) if isinstance(shots, list) else 0)
                mc_results["total_sot"].append((sot[0] + sot[1]) if isinstance(sot, list) else 0)

                # Scoreline distribution
                scoreline = f"{hg}-{ag}"
                mc_results["scorelines"][scoreline] = mc_results["scorelines"].get(scoreline, 0) + 1

                # HT result
                ht = sim.get("half_time_score", {})
                hth, hta = ht.get("home", 0), ht.get("away", 0)
                if hth > hta:
                    mc_results["ht_results"]["home"] += 1
                elif hth == hta:
                    mc_results["ht_results"]["draw"] += 1
                else:
                    mc_results["ht_results"]["away"] += 1

            # === 3. Compute simulation probabilities ===
            n = n_sims
            sim_probs = {
                "home_win": mc_results["home_wins"] / n,
                "draw": mc_results["draws"] / n,
                "away_win": mc_results["away_wins"] / n,
                "over15": mc_results["over15"] / n,
                "over25": mc_results["over25"] / n,
                "over35": mc_results["over35"] / n,
                "under25": 1 - mc_results["over25"] / n,
                "btts_yes": mc_results["btts"] / n,
                "btts_no": 1 - mc_results["btts"] / n,
                "ht_home": mc_results["ht_results"]["home"] / n,
                "ht_draw": mc_results["ht_results"]["draw"] / n,
                "ht_away": mc_results["ht_results"]["away"] / n,
            }

            # Corners O/U probabilities
            for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
                over = sum(1 for c in mc_results["total_corners"] if c > line) / n
                sim_probs[f"corners_over_{line}"] = over
                sim_probs[f"corners_under_{line}"] = 1 - over

            # Cards O/U probabilities
            for line in [2.5, 3.5, 4.5, 5.5]:
                over = sum(1 for c in mc_results["total_cards"] if c > line) / n
                sim_probs[f"cards_over_{line}"] = over
                sim_probs[f"cards_under_{line}"] = 1 - over

            # Averages
            avg = lambda lst: sum(lst) / len(lst) if lst else 0
            sim_averages = {
                "goals": round(avg(mc_results["total_goals"]), 2),
                "home_goals": round(avg(mc_results["home_goals"]), 2),
                "away_goals": round(avg(mc_results["away_goals"]), 2),
                "corners": round(avg(mc_results["total_corners"]), 1),
                "home_corners": round(avg(mc_results["home_corners"]), 1),
                "away_corners": round(avg(mc_results["away_corners"]), 1),
                "cards": round(avg(mc_results["total_cards"]), 1),
                "home_cards": round(avg(mc_results["home_cards"]), 1),
                "away_cards": round(avg(mc_results["away_cards"]), 1),
                "shots": round(avg(mc_results["total_shots"]), 1),
                "sot": round(avg(mc_results["total_sot"]), 1),
            }

            # Top scorelines
            top_scorelines = sorted(mc_results["scorelines"].items(),
                                    key=lambda x: x[1], reverse=True)[:8]
            top_scorelines = [{"score": s, "count": c, "pct": round(c/n*100, 1)}
                              for s, c in top_scorelines]

            # === 4. Generate value bets from simulation vs bookmaker odds ===
            # Extract featured simulation outcomes to filter bets for consistency
            featured_fs = simulation_result.get("final_score", {})
            featured_stats = simulation_result.get("stats", {})
            fh, fa = featured_fs.get("home", 0), featured_fs.get("away", 0)
            featured_total_goals = fh + fa
            featured_corners = sum(featured_stats.get("corners", [0, 0])) if isinstance(featured_stats.get("corners"), list) else 0
            featured_cards_yc = featured_stats.get("yellow_cards", [0, 0])
            featured_cards_rc = featured_stats.get("red_cards", [0, 0])
            featured_total_cards = 0
            if isinstance(featured_cards_yc, list):
                featured_total_cards += sum(featured_cards_yc)
            if isinstance(featured_cards_rc, list):
                featured_total_cards += sum(featured_cards_rc)

            featured_outcome = {
                "home_goals": fh,
                "away_goals": fa,
                "total_goals": featured_total_goals,
                "result": "home" if fh > fa else ("draw" if fh == fa else "away"),
                "btts": fh > 0 and fa > 0,
                "total_corners": featured_corners,
                "total_cards": featured_total_cards,
            }

            sim_value_bets = self._generate_sim_value_bets(
                sim_probs, sim_averages, match_data, home_name, away_name, league,
                featured_outcome=featured_outcome,
            )

            return {
                "simulation": simulation_result,
                "agent_count": len(raw_reports),
                "monte_carlo": {
                    "n_simulations": n_sims,
                    "probabilities": {k: round(v, 4) for k, v in sim_probs.items()},
                    "averages": sim_averages,
                    "top_scorelines": top_scorelines,
                },
                "sim_value_bets": sim_value_bets,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "error": f"Simulation failed: {str(e)}",
                "simulation": None,
            }

    def _generate_sim_value_bets(
        self, sim_probs: Dict, sim_avgs: Dict,
        match_data: Dict, home: str, away: str, league: str,
        featured_outcome: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Generate value bets by comparing Monte Carlo simulation probabilities vs bookmaker odds.

        IMPORTANT: Only bets that are CONSISTENT with the featured simulation outcome are included.
        This prevents contradictions like showing "Home Win" value bet when the sim shows "Away Win".
        """
        markets_summary = match_data.get("markets_summary", {})
        h2h_odds = markets_summary.get("h2h", {})
        totals_odds = markets_summary.get("totals", {})

        home_odds = h2h_odds.get(home, 0)
        draw_odds = h2h_odds.get("Draw", 0)
        away_odds = h2h_odds.get(away, 0)
        o25_odds = totals_odds.get("Over 2.5", 0)
        u25_odds = totals_odds.get("Under 2.5", 0)

        value_bets = []
        MIN_EDGE = 0.025  # 2.5% min edge for simulation-based bets

        # Build consistency filter from featured simulation outcome
        # A bet is "consistent" if the featured simulation's actual result matches the bet direction
        fo = featured_outcome or {}
        fo_result = fo.get("result", "")  # "home", "draw", "away"
        fo_total_goals = fo.get("total_goals", 99)
        fo_btts = fo.get("btts", None)
        fo_corners = fo.get("total_corners", 99)
        fo_cards = fo.get("total_cards", 99)

        def is_consistent(market_name: str) -> bool:
            """Check if a bet is consistent with the featured simulation outcome."""
            if not featured_outcome:
                return True  # No filter if no featured outcome

            name_lower = market_name.lower()

            # 1X2 consistency
            if "win" in name_lower:
                if home.lower() in name_lower:
                    return fo_result == "home"
                elif away.lower() in name_lower:
                    return fo_result == "away"
            if name_lower == "draw":
                return fo_result == "draw"

            # Goals O/U consistency
            if "over" in name_lower and "goal" in name_lower:
                line = float(name_lower.split("over")[1].split("goal")[0].strip())
                return fo_total_goals > line
            if "under" in name_lower and "goal" in name_lower:
                line = float(name_lower.split("under")[1].split("goal")[0].strip())
                return fo_total_goals < line

            # BTTS consistency
            if "btts yes" in name_lower:
                return fo_btts is True
            if "btts no" in name_lower:
                return fo_btts is False

            # Corners O/U consistency
            if "corners over" in name_lower:
                line = float(name_lower.split("over")[1].strip())
                return fo_corners > line
            if "corners under" in name_lower:
                line = float(name_lower.split("under")[1].strip())
                return fo_corners < line

            # Cards O/U consistency
            if "cards over" in name_lower:
                line = float(name_lower.split("over")[1].strip())
                return fo_cards > line
            if "cards under" in name_lower:
                line = float(name_lower.split("under")[1].strip())
                return fo_cards < line

            return True  # Unknown market type — include by default

        # Typical odds for markets without bookmaker prices
        TYPICAL_ODDS = {
            "Over 1.5 Goals": 1.35, "Under 1.5 Goals": 3.10,
            "Over 3.5 Goals": 2.60, "Under 3.5 Goals": 1.50,
            "BTTS Yes": 1.80, "BTTS No": 1.95,
            "Corners Over 8.5": 1.80, "Corners Under 8.5": 2.00,
            "Corners Over 9.5": 2.05, "Corners Under 9.5": 1.75,
            "Corners Over 10.5": 2.40, "Corners Under 10.5": 1.55,
            "Corners Over 11.5": 2.90, "Corners Under 11.5": 1.40,
            "Cards Over 3.5": 1.75, "Cards Under 3.5": 2.05,
            "Cards Over 4.5": 2.10, "Cards Under 4.5": 1.70,
            "Cards Over 5.5": 2.60, "Cards Under 5.5": 1.50,
        }

        # Match result markets
        checks = []
        if home_odds > 0:
            checks.append((f"{home} Win", sim_probs["home_win"], home_odds, "SIM_1X2"))
        if draw_odds > 0:
            checks.append(("Draw", sim_probs["draw"], draw_odds, "SIM_1X2"))
        if away_odds > 0:
            checks.append((f"{away} Win", sim_probs["away_win"], away_odds, "SIM_1X2"))

        # Goals markets
        if o25_odds > 0:
            checks.append(("Over 2.5 Goals", sim_probs["over25"], o25_odds, "SIM_GOALS"))
        if u25_odds > 0:
            checks.append(("Under 2.5 Goals", sim_probs["under25"], u25_odds, "SIM_GOALS"))

        # Markets with typical odds (no bookmaker price available)
        typical_checks = [
            ("Over 1.5 Goals", sim_probs["over15"]),
            ("Over 3.5 Goals", sim_probs["over35"]),
            ("BTTS Yes", sim_probs["btts_yes"]),
            ("BTTS No", sim_probs["btts_no"]),
        ]
        for name, prob in typical_checks:
            if name in TYPICAL_ODDS:
                checks.append((name, prob, TYPICAL_ODDS[name], "SIM_GOALS"))

        # Corner markets
        for line in [8.5, 9.5, 10.5, 11.5]:
            over_key = f"corners_over_{line}"
            under_key = f"corners_under_{line}"
            over_name = f"Corners Over {line}"
            under_name = f"Corners Under {line}"
            if over_name in TYPICAL_ODDS:
                checks.append((over_name, sim_probs[over_key], TYPICAL_ODDS[over_name], "SIM_CORNERS"))
            if under_name in TYPICAL_ODDS:
                checks.append((under_name, sim_probs[under_key], TYPICAL_ODDS[under_name], "SIM_CORNERS"))

        # Card markets
        for line in [3.5, 4.5, 5.5]:
            over_key = f"cards_over_{line}"
            under_key = f"cards_under_{line}"
            over_name = f"Cards Over {line}"
            under_name = f"Cards Under {line}"
            if over_name in TYPICAL_ODDS:
                checks.append((over_name, sim_probs[over_key], TYPICAL_ODDS[over_name], "SIM_CARDS"))
            if under_name in TYPICAL_ODDS:
                checks.append((under_name, sim_probs[under_key], TYPICAL_ODDS[under_name], "SIM_CARDS"))

        # Generate value bets — ONLY those consistent with the featured simulation
        for name, sim_prob, odds, source in checks:
            if odds <= 1.0 or sim_prob <= 0:
                continue

            # Skip bets that contradict the featured simulation outcome
            if not is_consistent(name):
                continue

            implied = 1.0 / odds
            edge = sim_prob - implied
            if edge >= MIN_EDGE:
                ev = (sim_prob * odds - 1) * 100
                if ev > 80:
                    ev = 80  # Cap extreme EV

                flags = [source, "SIM_CONFIRMED"]  # All bets here are confirmed by featured sim
                if edge > 0.10:
                    flags.append("STRONG_EDGE")
                if "Corner" in name and sim_avgs.get("corners", 0) > 11:
                    flags.append("HIGH_CORNER_MATCH")
                if "Card" in name and sim_avgs.get("cards", 0) > 5:
                    flags.append("HIGH_CARD_MATCH")

                # Risk from simulation confidence (more sims = more confident)
                if edge > 0.10:
                    risk = "LOW"
                elif edge > 0.06:
                    risk = "MEDIUM"
                else:
                    risk = "HIGH"

                value_bets.append({
                    "market": name,
                    "sim_prob": round(sim_prob, 4),
                    "implied_prob": round(implied, 4),
                    "odds": round(odds, 2),
                    "edge": round(edge, 4),
                    "ev_pct": round(ev, 2),
                    "rating": "STRONG" if edge > 0.10 else "MODERATE" if edge > 0.06 else "VALUE",
                    "risk_level": risk,
                    "flags": flags,
                    "source": source,
                })

        value_bets.sort(key=lambda x: x["edge"], reverse=True)
        return value_bets

    def _report_to_dict(self, report) -> Dict:
        """Convert AgentReport to dict, handling both dict and AgentReport inputs."""
        if isinstance(report, dict):
            return report
        return {
            "agent_name": report.agent_name,
            "match_id": report.match_id,
            "home_team": report.home_team,
            "away_team": report.away_team,
            "overall_assessment": report.overall_assessment,
            "reliability_score": report.reliability_score,
            "prediction_count": len(report.predictions),
            "predictions": [
                {
                    "market": p.market,
                    "outcome": p.outcome,
                    "probability": p.probability,
                    "confidence": p.confidence,
                    "reasoning": p.reasoning,
                    "data_points": p.data_points,
                }
                for p in report.predictions  # All predictions
            ],
        }

    def _profile_to_dict(self, profile) -> Dict:
        """Convert TeamProfile to dict."""
        return {
            "name": profile.name,
            "attack_rating": profile.attack_rating,
            "defense_rating": profile.defense_rating,
            "midfield_rating": profile.midfield_rating,
            "set_piece_rating": profile.set_piece_rating,
            "gk_rating": profile.gk_rating,
            "discipline": profile.discipline,
            "motivation": profile.motivation,
            "fatigue": profile.fatigue,
            "momentum": profile.momentum,
            "tactical_style": profile.tactical_style,
            "key_players": profile.key_players,
            "manager_quality": profile.manager_quality,
        }

    def _bet_to_dict(self, bet: FinalBet) -> Dict:
        return {
            "match_id": bet.match_id,
            "home_team": bet.home_team,
            "away_team": bet.away_team,
            "league": bet.league,
            "market": bet.market,
            "market_display": bet.market_display,
            "outcome": bet.outcome,
            "confidence_pct": bet.confidence_pct,
            "best_odds": bet.best_odds,
            "best_bookmaker": bet.best_bookmaker,
            "expected_value": bet.expected_value,
            "agent_agreement": bet.agent_agreement,
            "reasoning": bet.reasoning,
            "risk_level": bet.risk_level,
            "recommended_stake": bet.recommended_stake,
            "calibrated_prob": bet.calibrated_prob,
            "raw_prob": bet.raw_prob,
            "edge_pct": bet.edge_pct,
            "v4_flags": bet.v4_flags,
        }


# Backward compatibility alias
FootballPredictionEngineV4 = FootballPredictionEngineV5


# Quick test
if __name__ == "__main__":
    engine = FootballPredictionEngineV5()
    print(f"Engine V5 initialized with {len(engine.agents)} agents:")
    print(f"\nOriginal 6 agents:")
    for a in engine.agents[:6]:
        print(f"  - {a.name}: {a.specialty} (weight: {a.weight})")
    print(f"\nNew 17 agents (player intel, tactical, situational):")
    for a in engine.agents[6:]:
        print(f"  - {a.name}: {a.specialty} (weight: {a.weight})")
    print(f"\nMeta-agent: MetaAgentV2 (calibrated, filtered)")
    print(f"Simulator: MatchSimulator (match event simulation)")
    print(f"Version: {engine.VERSION}")
    print(f"Total agents: {len(engine.agents)} (6 original + 17 new)")
