import { useState } from "react";
import {
  X,
  Activity,
  TrendingUp,
  BarChart3,
  History,
  Target,
  Shield,
  Users,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Zap,
} from "lucide-react";
import type { Analysis, Match, AgentReport, FinalBet, TeamForm, H2H, V4Analysis } from "../types";

interface Props {
  match: Match;
  analysis: Analysis | null;
  onClose: () => void;
  onSimulate?: (matchId: string) => void;
  isSimulating?: boolean;
}

const AGENT_ICONS: Record<string, typeof Activity> = {
  FormAgent: TrendingUp,
  HistoricalAgent: History,
  StatsAgent: BarChart3,
  MarketAgent: Target,
  ValueAgent: Shield,
  ContextAgent: Users,
};

const AGENT_COLORS: Record<string, string> = {
  FormAgent: "#10b981",
  HistoricalAgent: "#8b5cf6",
  StatsAgent: "#3b82f6",
  MarketAgent: "#f59e0b",
  ValueAgent: "#ef4444",
  ContextAgent: "#f97316",
};

function FormResult({ char }: { char: string }) {
  const cls =
    char === "W" ? "form-w" : char === "D" ? "form-d" : char === "L" ? "form-l" : "form-unknown";
  return <span className={`form-badge ${cls}`}>{char}</span>;
}

function FormSection({ form, label }: { form: TeamForm; label: string }) {
  return (
    <div className="form-section">
      <h4>{label}: {form.team}</h4>
      <div className="form-string">
        {form.form_string.split("").map((c, i) => (
          <FormResult key={i} char={c} />
        ))}
      </div>
      <div className="form-stats-grid">
        <div className="form-stat">
          <span className="stat-label">W/D/L</span>
          <span className="stat-value">{form.wins}/{form.draws}/{form.losses}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Pts (last 10)</span>
          <span className="stat-value">{form.points_last_10}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Goals/game</span>
          <span className="stat-value">{form.goals_scored_avg}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Conceded/game</span>
          <span className="stat-value">{form.goals_conceded_avg}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Corners/game</span>
          <span className="stat-value">{form.corners_avg}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Cards/game</span>
          <span className="stat-value">{form.cards_avg}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Shots on target</span>
          <span className="stat-value">{form.shots_on_target_avg}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Fouls/game</span>
          <span className="stat-value">{form.fouls_avg}</span>
        </div>
      </div>
      {form.matches.length > 0 && (
        <div className="recent-matches">
          <table className="mini-table">
            <thead>
              <tr>
                <th>Result</th>
                <th>{form.matches[0]?.opponent ? "Opponent" : "H/A"}</th>
                <th>Score</th>
                <th>Corners</th>
                <th>Cards</th>
              </tr>
            </thead>
            <tbody>
              {form.matches.slice(0, 5).map((m, i) => (
                <tr key={i}>
                  <td><FormResult char={m.result} /></td>
                  <td className="opponent-cell">
                    {m.opponent || (m.home ? "Home" : "Away")}
                  </td>
                  <td>{m.goals_for} - {m.goals_against}</td>
                  <td>{m.corners}</td>
                  <td>{m.cards_yellow}{m.cards_red > 0 ? ` + ${m.cards_red}R` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function H2HSection({ h2h }: { h2h: H2H }) {
  const total = h2h.total_matches || 1;
  const homePct = (h2h.home_wins / total) * 100;
  const drawPct = (h2h.draws / total) * 100;
  const awayPct = (h2h.away_wins / total) * 100;

  return (
    <div className="h2h-section">
      <h4>
        <History size={16} /> Head to Head ({h2h.total_matches} matches)
      </h4>
      <div className="h2h-bar-container">
        <div className="h2h-labels">
          <span>{h2h.home} ({h2h.home_wins})</span>
          <span>Draws ({h2h.draws})</span>
          <span>{h2h.away} ({h2h.away_wins})</span>
        </div>
        <div className="h2h-bar">
          <div className="h2h-home" style={{ width: `${homePct}%` }} />
          <div className="h2h-draw" style={{ width: `${drawPct}%` }} />
          <div className="h2h-away" style={{ width: `${awayPct}%` }} />
        </div>
      </div>
      <div className="h2h-stats-grid">
        <div className="form-stat">
          <span className="stat-label">Avg goals/match</span>
          <span className="stat-value">{h2h.avg_goals_per_match}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Avg corners/match</span>
          <span className="stat-value">{h2h.avg_corners_per_match}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Avg cards/match</span>
          <span className="stat-value">{h2h.avg_cards_per_match}</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">BTTS %</span>
          <span className="stat-value">{h2h.btts_percentage}%</span>
        </div>
        <div className="form-stat">
          <span className="stat-label">Over 2.5 %</span>
          <span className="stat-value">{h2h.over_2_5_percentage}%</span>
        </div>
      </div>
    </div>
  );
}

function AgentReportCard({ report }: { report: AgentReport }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = AGENT_ICONS[report.agent_name] || Activity;
  const color = AGENT_COLORS[report.agent_name] || "#6b7280";

  return (
    <div className="agent-card" style={{ borderLeftColor: color }}>
      <div className="agent-header" onClick={() => setExpanded(!expanded)}>
        <div className="agent-title">
          <Icon size={16} style={{ color }} />
          <span className="agent-name">{report.agent_name}</span>
          <span className="agent-reliability">
            {(report.reliability_score * 100).toFixed(0)}% reliability
          </span>
        </div>
        <div className="agent-meta">
          <span className="prediction-count">
            {report.predictions.length} predictions
          </span>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>
      {report.overall_assessment && (
        <p className="agent-assessment">{report.overall_assessment}</p>
      )}
      {expanded && (
        <div className="agent-predictions">
          <table className="predictions-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Outcome</th>
                <th>Prob</th>
                <th>Conf</th>
                <th>Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {report.predictions.map((p, i) => (
                <tr key={i}>
                  <td className="market-cell">{p.market}</td>
                  <td className="outcome-cell">{p.outcome}</td>
                  <td className="num-cell">{(p.probability * 100).toFixed(1)}%</td>
                  <td className="num-cell">{(p.confidence * 100).toFixed(1)}%</td>
                  <td className="reasoning-cell">{p.reasoning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ValueBetsSection({ bets }: { bets: FinalBet[] }) {
  if (!bets.length) {
    return (
      <div className="value-bets-section" style={{ padding: "30px", textAlign: "center" }}>
        <Target size={32} style={{ color: "#444", marginBottom: "12px" }} />
        <p style={{ color: "#666", fontSize: "14px" }}>No value bets detected for this match.</p>
        <p style={{ color: "#555", fontSize: "12px" }}>The V5 model found no edges above the minimum threshold against current bookmaker odds.</p>
      </div>
    );
  }

  return (
    <div className="value-bets-section">
      <h4>
        <Target size={16} /> Value Bets ({bets.length})
      </h4>
      <table className="bets-table">
        <thead>
          <tr>
            <th>Market</th>
            <th>Bet</th>
            <th className="center">Odds</th>
            <th className="center">Edge</th>
            <th className="center">EV</th>
            <th className="center">Risk</th>
            <th className="center">Stake</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {bets.map((b, i) => (
            <tr key={i} className={`risk-${b.risk_level.toLowerCase()}`}>
              <td>{b.market_display}</td>
              <td className="outcome-cell">{b.outcome}</td>
              <td className="center" style={{ color: "#00ff88", fontWeight: "bold" }}>{b.best_odds.toFixed(2)}</td>
              <td className="center" style={{ color: "#00ff88" }}>+{(b.edge_pct || 0).toFixed(1)}%</td>
              <td className="center ev-cell">+{b.expected_value.toFixed(1)}%</td>
              <td className="center">
                <span className={`risk-badge risk-${b.risk_level.toLowerCase()}`}>
                  {b.risk_level}
                </span>
              </td>
              <td className="center">{b.recommended_stake.toFixed(2)}%</td>
              <td>
                {(b.v4_flags || []).map((flag, j) => (
                  <span key={j} style={{
                    display: "inline-block",
                    fontSize: "8px",
                    padding: "1px 4px",
                    marginRight: "3px",
                    backgroundColor: flag.includes("GOLD") || flag.includes("ZONE") ? "#ffd74020" : "#7b61ff20",
                    borderRadius: "3px",
                    color: flag.includes("GOLD") || flag.includes("ZONE") ? "#ffd740" : "#b388ff",
                    fontWeight: "bold"
                  }}>
                    {flag}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProgressSteps({ progress }: { progress: Analysis["progress"] }) {
  return (
    <div className="progress-steps">
      {progress.map((p, i) => {
        const isDone = p.step.endsWith("_done") || p.step === "completed" || p.step === "data_collected";
        const isError = p.step === "error";
        return (
          <div key={i} className={`progress-step ${isDone ? "done" : ""} ${isError ? "error" : ""}`}>
            {isDone ? (
              <CheckCircle2 size={14} className="step-icon done" />
            ) : isError ? (
              <AlertCircle size={14} className="step-icon error" />
            ) : (
              <Activity size={14} className="step-icon spinning" />
            )}
            <span>{p.message}</span>
          </div>
        );
      })}
    </div>
  );
}

function V4PredictionsTab({ v4 }: { v4: V4Analysis }) {
  const homeWinPct = v4.calibrated_probs.home_win * 100;
  const drawPct = v4.calibrated_probs.draw * 100;
  const awayWinPct = v4.calibrated_probs.away_win * 100;

  const cornerLines = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5];
  const cardLines = [2.5, 3.5, 4.5, 5.5, 6.5];

  return (
    <div className="v4-predictions-tab" style={{ color: "#e0e0e0" }}>
      {/* Probability Bar */}
      <div style={{
        marginBottom: "24px",
        padding: "16px",
        backgroundColor: "#1a1a1a",
        borderRadius: "8px",
        border: "1px solid #222"
      }}>
        <h4 style={{ marginBottom: "12px", fontSize: "14px", fontWeight: "600" }}>Match Outcome Probabilities</h4>
        <div style={{ display: "flex", height: "40px", borderRadius: "4px", overflow: "hidden", marginBottom: "12px" }}>
          <div style={{
            width: `${homeWinPct}%`,
            backgroundColor: "#22c55e",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#000",
            fontWeight: "bold",
            fontSize: "12px"
          }}>
            {homeWinPct > 10 ? `${homeWinPct.toFixed(0)}%` : ""}
          </div>
          <div style={{
            width: `${drawPct}%`,
            backgroundColor: "#fb923c",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#000",
            fontWeight: "bold",
            fontSize: "12px"
          }}>
            {drawPct > 10 ? `${drawPct.toFixed(0)}%` : ""}
          </div>
          <div style={{
            width: `${awayWinPct}%`,
            backgroundColor: "#3b82f6",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontWeight: "bold",
            fontSize: "12px"
          }}>
            {awayWinPct > 10 ? `${awayWinPct.toFixed(0)}%` : ""}
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "12px" }}>
          <div style={{ textAlign: "center", padding: "8px", backgroundColor: "#0a0a0a", borderRadius: "4px" }}>
            <div style={{ fontSize: "12px", color: "#888" }}>Home Win</div>
            <div style={{ fontSize: "16px", fontWeight: "bold", color: "#22c55e" }}>{homeWinPct.toFixed(1)}%</div>
          </div>
          <div style={{ textAlign: "center", padding: "8px", backgroundColor: "#0a0a0a", borderRadius: "4px" }}>
            <div style={{ fontSize: "12px", color: "#888" }}>Draw</div>
            <div style={{ fontSize: "16px", fontWeight: "bold", color: "#fb923c" }}>{drawPct.toFixed(1)}%</div>
          </div>
          <div style={{ textAlign: "center", padding: "8px", backgroundColor: "#0a0a0a", borderRadius: "4px" }}>
            <div style={{ fontSize: "12px", color: "#888" }}>Away Win</div>
            <div style={{ fontSize: "16px", fontWeight: "bold", color: "#3b82f6" }}>{awayWinPct.toFixed(1)}%</div>
          </div>
          <div style={{ textAlign: "center", padding: "8px", backgroundColor: "#0a0a0a", borderRadius: "4px" }}>
            <div style={{ fontSize: "12px", color: "#888" }}>xG Total</div>
            <div style={{ fontSize: "16px", fontWeight: "bold", color: "#00ff88" }}>{v4.expected_goals.total.toFixed(1)}</div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
        {/* xG Card */}
        <div style={{
          padding: "16px",
          backgroundColor: "#1a1a1a",
          borderRadius: "8px",
          border: "1px solid #222"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "12px", fontWeight: "600", color: "#888", textTransform: "uppercase" }}>Expected Goals</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <div style={{ fontSize: "12px", color: "#888" }}>Home xG</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88" }}>{v4.expected_goals.home.toFixed(2)}</div>
            </div>
            <div>
              <div style={{ fontSize: "12px", color: "#888" }}>Away xG</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88" }}>{v4.expected_goals.away.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* Elo Card */}
        <div style={{
          padding: "16px",
          backgroundColor: "#1a1a1a",
          borderRadius: "8px",
          border: "1px solid #222"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "12px", fontWeight: "600", color: "#888", textTransform: "uppercase" }}>Elo Ratings</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <div style={{ fontSize: "12px", color: "#888" }}>Home</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88" }}>{v4.elo_ratings.home.toFixed(0)}</div>
            </div>
            <div>
              <div style={{ fontSize: "12px", color: "#888" }}>Away</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88" }}>{v4.elo_ratings.away.toFixed(0)}</div>
            </div>
          </div>
          <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #222", fontSize: "11px", color: "#888" }}>
            Advantage: {(v4.elo_ratings.home - v4.elo_ratings.away).toFixed(0)}
          </div>
        </div>

        {/* Match Stats Card */}
        <div style={{
          padding: "16px",
          backgroundColor: "#1a1a1a",
          borderRadius: "8px",
          border: "1px solid #222"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "12px", fontWeight: "600", color: "#888", textTransform: "uppercase" }}>Match Stats</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "12px" }}>
            <div><span style={{ color: "#888" }}>Shots:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.shots}</span></div>
            <div><span style={{ color: "#888" }}>SOT:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.sot}</span></div>
            <div><span style={{ color: "#888" }}>Corners:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.corners}</span></div>
            <div><span style={{ color: "#888" }}>Cards:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.cards}</span></div>
            <div><span style={{ color: "#888" }}>Fouls:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.fouls}</span></div>
            <div><span style={{ color: "#888" }}>Reds:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.reds}</span></div>
          </div>
          <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #222", fontSize: "11px" }}>
            <span style={{ color: "#888" }}>Profile:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.match_stats.profile}</span>
          </div>
        </div>

        {/* League Baseline Card */}
        <div style={{
          padding: "16px",
          backgroundColor: "#1a1a1a",
          borderRadius: "8px",
          border: "1px solid #222"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "12px", fontWeight: "600", color: "#888", textTransform: "uppercase" }}>League Baseline</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "8px", fontSize: "12px" }}>
            <div><span style={{ color: "#888" }}>Avg Goals:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.league_baseline.avg_goals.toFixed(2)}</span></div>
            <div><span style={{ color: "#888" }}>Avg Corners:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.league_baseline.avg_corners.toFixed(1)}</span></div>
            <div><span style={{ color: "#888" }}>Avg Cards:</span> <span style={{ color: "#00ff88", fontWeight: "bold" }}>{v4.league_baseline.avg_cards.toFixed(1)}</span></div>
          </div>
          <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #222", fontSize: "11px", color: "#888" }}>
            {v4.calibrated_probs.shrinkage_applied ? "Shrinkage: Applied" : "Shrinkage: Not applied"}
          </div>
        </div>
      </div>

      {/* Corner O/U Section */}
      <div style={{
        marginBottom: "24px",
        padding: "16px",
        backgroundColor: "#1a1a1a",
        borderRadius: "8px",
        border: "1px solid #222"
      }}>
        <h4 style={{ marginBottom: "16px", fontSize: "14px", fontWeight: "600" }}>Corner Over/Under</h4>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "12px" }}>
          {cornerLines.map((line) => {
            const prob = v4.corner_ou[line.toString()] || 0;
            return (
              <div key={line} style={{ textAlign: "center" }}>
                <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>O {line}</div>
                <div style={{
                  height: "60px",
                  backgroundColor: "#0a0a0a",
                  borderRadius: "4px",
                  border: "1px solid #222",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "flex-end",
                  padding: "4px"
                }}>
                  <div style={{
                    height: `${Math.min(prob * 100, 100)}%`,
                    backgroundColor: "#00ff88",
                    borderRadius: "2px",
                    transition: "all 0.3s"
                  }} />
                  <div style={{ fontSize: "10px", color: "#e0e0e0", fontWeight: "bold", marginTop: "2px" }}>
                    {(prob * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Card O/U Section */}
      <div style={{
        marginBottom: "24px",
        padding: "16px",
        backgroundColor: "#1a1a1a",
        borderRadius: "8px",
        border: "1px solid #222"
      }}>
        <h4 style={{ marginBottom: "16px", fontSize: "14px", fontWeight: "600" }}>Card Over/Under</h4>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "12px" }}>
          {cardLines.map((line) => {
            const prob = v4.card_ou[line.toString()] || 0;
            return (
              <div key={line} style={{ textAlign: "center" }}>
                <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>O {line}</div>
                <div style={{
                  height: "60px",
                  backgroundColor: "#0a0a0a",
                  borderRadius: "4px",
                  border: "1px solid #222",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "flex-end",
                  padding: "4px"
                }}>
                  <div style={{
                    height: `${Math.min(prob * 100, 100)}%`,
                    backgroundColor: "#00ff88",
                    borderRadius: "2px",
                    transition: "all 0.3s"
                  }} />
                  <div style={{ fontSize: "10px", color: "#e0e0e0", fontWeight: "bold", marginTop: "2px" }}>
                    {(prob * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* V5 Adjustments Applied */}
      {v4.context?.v5_adjustments && v4.context.v5_adjustments.length > 0 && (
        <div style={{
          marginBottom: "24px",
          padding: "16px",
          backgroundColor: "#0d1117",
          borderRadius: "8px",
          border: "1px solid #7b61ff40"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "14px", fontWeight: "600", color: "#b388ff" }}>
            V5 Data-Mined Adjustments Applied
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {v4.context.v5_adjustments.map((adj: string, i: number) => (
              <span key={i} style={{
                display: "inline-block",
                fontSize: "11px",
                padding: "4px 10px",
                backgroundColor: "#7b61ff20",
                borderRadius: "4px",
                color: "#b388ff",
                border: "1px solid #7b61ff30"
              }}>
                {adj}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Agent Intelligence Signals */}
      {v4.context?.agent_signals && (
        <div style={{
          marginBottom: "24px",
          padding: "16px",
          backgroundColor: "#0d1117",
          borderRadius: "8px",
          border: "1px solid #00e67640"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "14px", fontWeight: "600", color: "#00e676" }}>
            Agent Intelligence (27 agents → prediction adjustments)
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px" }}>
            {(() => {
              const s = v4.context.agent_signals!;
              const items = [
                { label: "Goals Adjustment", value: `${s.goals_adj > 0 ? '+' : ''}${s.goals_adj.toFixed(2)}`, color: s.goals_adj > 0 ? "#22c55e" : s.goals_adj < 0 ? "#ef4444" : "#888" },
                { label: "Corners Adjustment", value: `${s.corners_adj > 0 ? '+' : ''}${s.corners_adj.toFixed(1)}`, color: s.corners_adj > 0 ? "#22c55e" : s.corners_adj < 0 ? "#ef4444" : "#888" },
                { label: "Cards Adjustment", value: `${s.cards_adj > 0 ? '+' : ''}${s.cards_adj.toFixed(1)}`, color: s.cards_adj > 0 ? "#ef4444" : s.cards_adj < 0 ? "#22c55e" : "#888" },
                { label: "Agent xG", value: `${s.xg_home.toFixed(1)} - ${s.xg_away.toFixed(1)}`, color: "#60a5fa" },
                { label: "Referee", value: `${s.referee_yellows.toFixed(1)} yellows (${s.referee_strictness}/10)`, color: s.referee_strictness >= 7 ? "#ef4444" : s.referee_strictness <= 3 ? "#22c55e" : "#888" },
                { label: "Fatigue", value: `H:${(s.fatigue_home*100).toFixed(0)}% A:${(s.fatigue_away*100).toFixed(0)}%`, color: Math.max(s.fatigue_home, s.fatigue_away) > 0.7 ? "#ef4444" : "#888" },
                { label: "Momentum", value: `H:${(s.momentum_home*100).toFixed(0)}% A:${(s.momentum_away*100).toFixed(0)}%`, color: "#60a5fa" },
                { label: "Injuries", value: `H:${s.home_injuries} A:${s.away_injuries}`, color: Math.max(s.home_injuries, s.away_injuries) >= 5 ? "#ef4444" : "#888" },
                { label: "Set Pieces", value: s.set_piece_adv, color: s.set_piece_adv !== "neutral" ? "#22c55e" : "#888" },
                { label: "Tactical Edge", value: `${s.tactical_edge > 0 ? '+' : ''}${s.tactical_edge.toFixed(1)}`, color: s.tactical_edge !== 0 ? "#60a5fa" : "#888" },
              ];
              return items.map((item, i) => (
                <div key={i} style={{
                  padding: "8px 12px",
                  backgroundColor: "#111",
                  borderRadius: "6px",
                  border: `1px solid ${item.color}30`,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center"
                }}>
                  <span style={{ fontSize: "11px", color: "#888" }}>{item.label}</span>
                  <span style={{ fontSize: "13px", fontWeight: "600", color: item.color }}>{item.value}</span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}

      {/* Value Bets Section */}
      <div style={{
        marginBottom: "24px",
        padding: "16px",
        backgroundColor: "#1a1a1a",
        borderRadius: "8px",
        border: v4.value_bets.length > 0 ? "1px solid #00e67640" : "1px solid #222"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h4 style={{ fontSize: "14px", fontWeight: "600", color: v4.value_bets.length > 0 ? "#00e676" : "#888" }}>
            V5 Value Bets {v4.value_bets.length > 0 ? `(${v4.value_bets.length} found)` : "(none)"}
          </h4>
          {v4.value_bets.length > 0 && (
            <span style={{
              fontSize: "10px", padding: "3px 8px", borderRadius: "4px",
              backgroundColor: "#00e67620", color: "#00e676", fontWeight: "bold"
            }}>
              +{(v4.value_bets.reduce((s: number, b: any) => s + b.ev_pct, 0) / v4.value_bets.length).toFixed(1)}% avg EV
            </span>
          )}
        </div>
        {v4.value_bets.length === 0 ? (
          <div style={{ fontSize: "12px", color: "#666", textAlign: "center", padding: "20px" }}>
            No value bets detected — odds are fairly priced for this match.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
            {v4.value_bets.map((bet: any, i: number) => (
              <div key={i} style={{
                padding: "14px",
                backgroundColor: "#0a0a0a",
                borderRadius: "8px",
                border: bet.rating === "STRONG" ? "1px solid #00e67650" : "1px solid #333"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <div style={{ fontSize: "13px", fontWeight: "bold", color: "#e0e0e0" }}>{bet.market}</div>
                  <span style={{
                    fontSize: "10px",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    backgroundColor: bet.rating === "STRONG" ? "#00e67630" : bet.rating === "MODERATE" ? "#42a5f530" : "#fb923c30",
                    color: bet.rating === "STRONG" ? "#00e676" : bet.rating === "MODERATE" ? "#42a5f5" : "#fb923c",
                    fontWeight: "bold"
                  }}>
                    {bet.rating}
                  </span>
                </div>

                {/* Probability comparison bar */}
                <div style={{ marginBottom: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
                    <span style={{ color: "#888" }}>Model</span>
                    <span style={{ color: "#00e676", fontWeight: "bold" }}>{(bet.model_prob * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ height: "6px", backgroundColor: "#222", borderRadius: "3px", overflow: "hidden", position: "relative" as const }}>
                    <div style={{ height: "100%", width: `${Math.min(bet.model_prob * 100, 100)}%`, backgroundColor: "#00e676", borderRadius: "3px" }} />
                    <div style={{
                      position: "absolute" as const, top: 0, left: `${Math.min(bet.implied_prob * 100, 100)}%`,
                      width: "2px", height: "100%", backgroundColor: "#fb923c"
                    }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", marginTop: "2px" }}>
                    <span style={{ color: "#fb923c" }}>Implied: {(bet.implied_prob * 100).toFixed(1)}%</span>
                    <span style={{ color: "#00e676", fontWeight: "bold" }}>Edge: +{(bet.edge * 100).toFixed(1)}%</span>
                  </div>
                </div>

                <div style={{ paddingTop: "8px", borderTop: "1px solid #222", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", fontSize: "11px" }}>
                  <div>
                    <span style={{ color: "#888", fontSize: "10px" }}>Odds</span>
                    <div style={{ color: "#00e676", fontWeight: "bold" }}>{bet.odds.toFixed(2)}</div>
                  </div>
                  <div>
                    <span style={{ color: "#888", fontSize: "10px" }}>EV</span>
                    <div style={{ color: "#00e676", fontWeight: "bold" }}>+{bet.ev_pct.toFixed(1)}%</div>
                  </div>
                  <div>
                    <span style={{ color: "#888", fontSize: "10px" }}>Edge</span>
                    <div style={{ color: "#00e676", fontWeight: "bold" }}>+{(bet.edge * 100).toFixed(1)}%</div>
                  </div>
                </div>
                {bet.flags && bet.flags.length > 0 && (
                  <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #222" }}>
                    {bet.flags.map((flag: string, j: number) => (
                      <span key={j} style={{
                        display: "inline-block",
                        fontSize: "9px",
                        padding: "2px 6px",
                        marginRight: "4px",
                        marginBottom: "2px",
                        backgroundColor: flag.includes("GOLD") || flag.includes("ZONE") ? "#ffd74020" : "#7b61ff20",
                        borderRadius: "3px",
                        color: flag.includes("GOLD") || flag.includes("ZONE") ? "#ffd740" : "#b388ff",
                        fontWeight: "bold"
                      }}>
                        {flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Notes Section */}
      {v4.notes.length > 0 && (
        <div style={{
          padding: "16px",
          backgroundColor: "#1a1a1a",
          borderRadius: "8px",
          border: "1px solid #222"
        }}>
          <h4 style={{ marginBottom: "12px", fontSize: "14px", fontWeight: "600" }}>Analysis Notes</h4>
          <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "13px", lineHeight: "1.6" }}>
            {v4.notes.map((note, i) => (
              <li key={i} style={{ color: "#888", marginBottom: "6px" }}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PlayerIntelTab({ analysis, match }: { analysis: Analysis; match: Match }) {
  // Extract lineup and player news data from agent reports
  const lineupReport = analysis.agent_reports.find(
    (r) => r.agent_name === "lineup_analyst"
  );
  const playerNewsReport = analysis.agent_reports.find(
    (r) => r.agent_name === "player_news_analyst"
  );
  const injuryReport = analysis.agent_reports.find(
    (r) => r.agent_name === "injury_analyst"
  );
  const gkReport = analysis.agent_reports.find(
    (r) => r.agent_name === "goalkeeper_analyst"
  );

  // Helper to extract prediction value from agent report
  const getPred = (report: AgentReport | undefined, market: string): string | undefined => {
    if (!report) return undefined;
    const pred = report.predictions.find((p) => p.market === market);
    return pred?.outcome;
  };

  // Parse player lists from predictions (returns full player objects)
  const parsePlayerObjects = (val: string | undefined): any[] => {
    if (!val || val === "[]") return [];
    try {
      return JSON.parse(val.replace(/'/g, '"'));
    } catch {
      return [];
    }
  };

  const parsePlayerReports = (val: string | undefined): any[] => {
    if (!val || val === "[]") return [];
    try {
      return JSON.parse(val.replace(/'/g, '"'));
    } catch {
      return [];
    }
  };

  const homeXIData = parsePlayerObjects(getPred(lineupReport, "home_predicted_xi"));
  const awayXIData = parsePlayerObjects(getPred(lineupReport, "away_predicted_xi"));
  const homeFormation = getPred(lineupReport, "home_formation") || "4-3-3";
  const awayFormation = getPred(lineupReport, "away_formation") || "4-3-3";
  // lineupSource available via: getPred(lineupReport, "lineup_source")
  const lineupConfirmed = getPred(lineupReport, "lineup_confirmed") === "True";
  const homePlayerReports = parsePlayerReports(getPred(playerNewsReport, "home_player_reports"));
  const awayPlayerReports = parsePlayerReports(getPred(playerNewsReport, "away_player_reports"));
  const homeTopScorers = parsePlayerReports(getPred(playerNewsReport, "home_top_scorers"));
  const awayTopScorers = parsePlayerReports(getPred(playerNewsReport, "away_top_scorers"));

  // Gather all insights from intel agents (deduplicated)
  const insightSet = new Set<string>();
  const allInsights: string[] = [];

  const addInsight = (text: string) => {
    if (!text || insightSet.has(text)) return;
    insightSet.add(text);
    allInsights.push(text);
  };

  for (const report of [lineupReport, playerNewsReport, injuryReport, gkReport]) {
    if (report?.overall_assessment) {
      // Don't add generic "analysis complete" messages
      if (!report.overall_assessment.includes("analysis complete")) {
        // Split pipe-separated assessments into individual insights
        const parts = report.overall_assessment.split(" | ");
        for (const part of parts) {
          addInsight(part.trim());
        }
      }
    }
  }

  // Also gather insights from prediction reasoning that contain useful info
  for (const report of [lineupReport, playerNewsReport, injuryReport]) {
    if (!report) continue;
    for (const pred of report.predictions) {
      if (pred.reasoning && (pred.reasoning.includes("⭐") || pred.reasoning.includes("⚠️") || pred.reasoning.includes("🟨"))) {
        addInsight(pred.reasoning);
      }
    }
  }

  const cardStyle = {
    padding: "16px",
    backgroundColor: "#1a1a1a",
    borderRadius: "8px",
    border: "1px solid #222",
    marginBottom: "16px",
  };

  const headerStyle = {
    marginBottom: "12px",
    fontSize: "12px",
    fontWeight: "600" as const,
    color: "#888",
    textTransform: "uppercase" as const,
  };

  return (
    <div style={{ color: "#e0e0e0" }}>
      {/* Key Insights */}
      {allInsights.length > 0 && (
        <div style={cardStyle}>
          <h4 style={headerStyle}>Key Player Intelligence</h4>
          {allInsights.slice(0, 8).map((insight, i) => (
            <div
              key={i}
              style={{
                padding: "6px 10px",
                marginBottom: "4px",
                fontSize: "12px",
                lineHeight: "1.5",
                backgroundColor: "#0a0a0a",
                borderRadius: "4px",
                borderLeft: insight.includes("⭐")
                  ? "3px solid #22c55e"
                  : insight.includes("⚠️")
                  ? "3px solid #ef4444"
                  : insight.includes("🟨")
                  ? "3px solid #fbbf24"
                  : "3px solid #3b82f6",
              }}
            >
              {insight}
            </div>
          ))}
        </div>
      )}

      {/* Lineup Source Badge */}
      <div style={{ ...cardStyle, padding: "10px 16px", display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{
          display: "inline-block",
          padding: "3px 10px",
          borderRadius: "12px",
          fontSize: "11px",
          fontWeight: "bold",
          backgroundColor: lineupConfirmed ? "#22c55e22" : "#3b82f622",
          color: lineupConfirmed ? "#22c55e" : "#3b82f6",
          border: `1px solid ${lineupConfirmed ? "#22c55e44" : "#3b82f644"}`,
        }}>
          {lineupConfirmed ? "✅ CONFIRMED" : "📋 PREDICTED"}
        </span>
        <span style={{ fontSize: "11px", color: "#888" }}>
          {lineupConfirmed
            ? "Official lineups from the teams"
            : "Based on last match lineups + injury adjustments"}
        </span>
      </div>

      {/* Two-column: Home XI / Away XI */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
        {/* Home Squad */}
        <div style={cardStyle}>
          <h4 style={headerStyle}>{match.home_team} — {homeFormation}</h4>
          {homeXIData.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
              {homeXIData.map((player: any, i: number) => {
                const posColors: Record<string, string> = {
                  Goalkeeper: "#fbbf24",
                  Defender: "#3b82f6",
                  Midfielder: "#22c55e",
                  Attacker: "#ef4444",
                };
                const posColor = posColors[player.position] || "#888";
                const posLabel = (player.position || "?")[0]; // G, D, M, A
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "5px 8px",
                      backgroundColor: "#0a0a0a",
                      borderRadius: "4px",
                      fontSize: "12px",
                      borderLeft: `3px solid ${posColor}`,
                    }}
                  >
                    <span style={{ color: "#666", fontSize: "10px", width: "22px", textAlign: "right" }}>
                      {player.number ? `#${player.number}` : ""}
                    </span>
                    <span style={{ color: posColor, fontSize: "10px", fontWeight: "bold", width: "14px" }}>
                      {posLabel}
                    </span>
                    <span style={{ color: "#e0e0e0", flex: 1 }}>{player.name}</span>
                    {player.replacing && (
                      <span style={{ color: "#ef4444", fontSize: "10px" }}>
                        ↻ {player.replacing}
                      </span>
                    )}
                    {player.status === "doubtful" && (
                      <span style={{ color: "#fbbf24", fontSize: "10px" }}>⚠️</span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ fontSize: "12px", color: "#666" }}>
              No lineup data available
            </div>
          )}
        </div>

        {/* Away Squad */}
        <div style={cardStyle}>
          <h4 style={headerStyle}>{match.away_team} — {awayFormation}</h4>
          {awayXIData.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
              {awayXIData.map((player: any, i: number) => {
                const posColors: Record<string, string> = {
                  Goalkeeper: "#fbbf24",
                  Defender: "#3b82f6",
                  Midfielder: "#22c55e",
                  Attacker: "#ef4444",
                };
                const posColor = posColors[player.position] || "#888";
                const posLabel = (player.position || "?")[0];
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "5px 8px",
                      backgroundColor: "#0a0a0a",
                      borderRadius: "4px",
                      fontSize: "12px",
                      borderLeft: `3px solid ${posColor}`,
                    }}
                  >
                    <span style={{ color: "#666", fontSize: "10px", width: "22px", textAlign: "right" }}>
                      {player.number ? `#${player.number}` : ""}
                    </span>
                    <span style={{ color: posColor, fontSize: "10px", fontWeight: "bold", width: "14px" }}>
                      {posLabel}
                    </span>
                    <span style={{ color: "#e0e0e0", flex: 1 }}>{player.name}</span>
                    {player.replacing && (
                      <span style={{ color: "#ef4444", fontSize: "10px" }}>
                        ↻ {player.replacing}
                      </span>
                    )}
                    {player.status === "doubtful" && (
                      <span style={{ color: "#fbbf24", fontSize: "10px" }}>⚠️</span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ fontSize: "12px", color: "#666" }}>
              No lineup data available
            </div>
          )}
        </div>
      </div>

      {/* Top Scorers Comparison */}
      {(homeTopScorers.length > 0 || awayTopScorers.length > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
          <div style={cardStyle}>
            <h4 style={headerStyle}>{match.home_team} — Top Scorers</h4>
            {homeTopScorers.slice(0, 5).map((p: any, i: number) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "4px 8px",
                  backgroundColor: "#0a0a0a",
                  borderRadius: "4px",
                  marginBottom: "3px",
                  fontSize: "12px",
                }}
              >
                <span style={{ color: "#e0e0e0" }}>{p.name}</span>
                <span>
                  <span style={{ color: "#22c55e", fontWeight: "bold" }}>{p.goals}G</span>
                  {" "}
                  <span style={{ color: "#3b82f6" }}>{p.assists}A</span>
                  {" "}
                  <span style={{ color: "#666", fontSize: "10px" }}>({p.appearances} apps)</span>
                </span>
              </div>
            ))}
            {homeTopScorers.length === 0 && (
              <div style={{ fontSize: "12px", color: "#666" }}>No scoring data available</div>
            )}
          </div>
          <div style={cardStyle}>
            <h4 style={headerStyle}>{match.away_team} — Top Scorers</h4>
            {awayTopScorers.slice(0, 5).map((p: any, i: number) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "4px 8px",
                  backgroundColor: "#0a0a0a",
                  borderRadius: "4px",
                  marginBottom: "3px",
                  fontSize: "12px",
                }}
              >
                <span style={{ color: "#e0e0e0" }}>{p.name}</span>
                <span>
                  <span style={{ color: "#22c55e", fontWeight: "bold" }}>{p.goals}G</span>
                  {" "}
                  <span style={{ color: "#3b82f6" }}>{p.assists}A</span>
                  {" "}
                  <span style={{ color: "#666", fontSize: "10px" }}>({p.appearances} apps)</span>
                </span>
              </div>
            ))}
            {awayTopScorers.length === 0 && (
              <div style={{ fontSize: "12px", color: "#666" }}>No scoring data available</div>
            )}
          </div>
        </div>
      )}

      {/* Player Form Reports */}
      {(homePlayerReports.length > 0 || awayPlayerReports.length > 0) && (
        <div style={cardStyle}>
          <h4 style={headerStyle}>Player Form Reports</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "8px" }}>
            {[...homePlayerReports, ...awayPlayerReports].map((p: any, i: number) => (
              <div
                key={i}
                style={{
                  padding: "10px",
                  backgroundColor: "#0a0a0a",
                  borderRadius: "6px",
                  border: "1px solid #222",
                  borderLeft:
                    p.form === "excellent"
                      ? "3px solid #22c55e"
                      : p.form === "good"
                      ? "3px solid #3b82f6"
                      : p.form === "poor"
                      ? "3px solid #ef4444"
                      : "3px solid #666",
                }}
              >
                <div style={{ fontSize: "13px", fontWeight: "bold", color: "#e0e0e0", marginBottom: "4px" }}>
                  {p.name}
                </div>
                <div style={{ fontSize: "10px", color: "#888", marginBottom: "6px" }}>{p.team}</div>
                {p.stats && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", fontSize: "11px" }}>
                    <div>
                      <span style={{ color: "#888" }}>Goals: </span>
                      <span style={{ color: "#22c55e", fontWeight: "bold" }}>{p.stats.goals || 0}</span>
                    </div>
                    <div>
                      <span style={{ color: "#888" }}>Assists: </span>
                      <span style={{ color: "#3b82f6", fontWeight: "bold" }}>{p.stats.assists || 0}</span>
                    </div>
                    <div>
                      <span style={{ color: "#888" }}>Apps: </span>
                      <span style={{ color: "#e0e0e0" }}>{p.stats.appearances || 0}</span>
                    </div>
                    {p.stats.rating && (
                      <div>
                        <span style={{ color: "#888" }}>Rating: </span>
                        <span
                          style={{
                            color:
                              parseFloat(p.stats.rating) >= 7.5
                                ? "#22c55e"
                                : parseFloat(p.stats.rating) >= 7.0
                                ? "#3b82f6"
                                : "#fb923c",
                            fontWeight: "bold",
                          }}
                        >
                          {p.stats.rating}
                        </span>
                      </div>
                    )}
                  </div>
                )}
                {p.form && (
                  <div
                    style={{
                      marginTop: "6px",
                      paddingTop: "6px",
                      borderTop: "1px solid #222",
                      fontSize: "10px",
                      color:
                        p.form === "excellent"
                          ? "#22c55e"
                          : p.form === "good"
                          ? "#3b82f6"
                          : p.form === "poor"
                          ? "#ef4444"
                          : "#888",
                      fontWeight: "bold",
                      textTransform: "uppercase",
                    }}
                  >
                    Form: {p.form}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GK Comparison */}
      {gkReport && (
        <div style={cardStyle}>
          <h4 style={headerStyle}>Goalkeeper Comparison</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div style={{ padding: "10px", backgroundColor: "#0a0a0a", borderRadius: "6px", textAlign: "center" }}>
              <div style={{ fontSize: "13px", fontWeight: "bold", color: "#22c55e" }}>
                {getPred(gkReport, "home_gk_name") || match.home_team + " GK"}
              </div>
              <div style={{ fontSize: "10px", color: "#888", marginTop: "2px" }}>{match.home_team}</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88", marginTop: "6px" }}>
                {getPred(gkReport, "home_gk_rating") || "80"}
              </div>
            </div>
            <div style={{ padding: "10px", backgroundColor: "#0a0a0a", borderRadius: "6px", textAlign: "center" }}>
              <div style={{ fontSize: "13px", fontWeight: "bold", color: "#3b82f6" }}>
                {getPred(gkReport, "away_gk_name") || match.away_team + " GK"}
              </div>
              <div style={{ fontSize: "10px", color: "#888", marginTop: "2px" }}>{match.away_team}</div>
              <div style={{ fontSize: "18px", fontWeight: "bold", color: "#00ff88", marginTop: "6px" }}>
                {getPred(gkReport, "away_gk_rating") || "80"}
              </div>
            </div>
          </div>
          <div style={{ marginTop: "8px", fontSize: "12px", color: "#888", textAlign: "center" }}>
            {getPred(gkReport, "gk_advantage")}
          </div>
        </div>
      )}

      {/* No data message */}
      {homeXIData.length === 0 && awayXIData.length === 0 && homeTopScorers.length === 0 && allInsights.length === 0 && (
        <div style={{ ...cardStyle, textAlign: "center", padding: "32px" }}>
          <div style={{ fontSize: "14px", color: "#888", marginBottom: "8px" }}>
            Player intelligence requires real API-Sports fixture data
          </div>
          <div style={{ fontSize: "12px", color: "#666" }}>
            Demo matches don't have team IDs. Real matches from API-Sports will show full squad data, injury reports, top scorers, and player form.
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisModal({ match, analysis, onClose, onSimulate, isSimulating }: Props) {
  const hasV4 = analysis?.v4_analysis !== null && analysis?.v4_analysis !== undefined;
  const [activeTab, setActiveTab] = useState<"v4" | "overview" | "players" | "agents" | "bets">(
    hasV4 ? "v4" : "overview"
  );

  const isRunning = analysis?.status === "running";
  const isComplete = analysis?.status === "completed";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title">
            <h2>
              {match.home_team} vs {match.away_team}
            </h2>
            <span className="modal-league">{match.league}</span>
            {isRunning && (
              <span className="status-badge running">
                <Activity size={12} className="spinning" /> Analyzing...
              </span>
            )}
            {isComplete && (
              <span className="status-badge complete">
                <CheckCircle2 size={12} /> Complete
              </span>
            )}
            {isComplete && onSimulate && (
              <button
                className={`btn-simulate ${isSimulating ? "simulating" : ""}`}
                onClick={() => onSimulate(match.id)}
                disabled={isSimulating}
              >
                {isSimulating ? (
                  <>
                    <Activity size={13} className="spinning" /> Simulating...
                  </>
                ) : (
                  <>
                    <Zap size={13} /> Simulate Match
                  </>
                )}
              </button>
            )}
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Progress (shown while running) */}
        {isRunning && analysis && (
          <ProgressSteps progress={analysis.progress} />
        )}

        {/* Tabs */}
        {(isComplete || (analysis && analysis.agent_reports.length > 0)) && (
          <>
            <div className="modal-tabs">
              {hasV4 && (
                <button
                  className={activeTab === "v4" ? "active" : ""}
                  onClick={() => setActiveTab("v4")}
                >
                  <TrendingUp size={14} /> V4 Predictions
                </button>
              )}
              <button
                className={activeTab === "players" ? "active" : ""}
                onClick={() => setActiveTab("players")}
              >
                <Shield size={14} /> Player Intel
              </button>
              <button
                className={activeTab === "overview" ? "active" : ""}
                onClick={() => setActiveTab("overview")}
              >
                <Users size={14} /> Overview & Form
              </button>
              <button
                className={activeTab === "agents" ? "active" : ""}
                onClick={() => setActiveTab("agents")}
              >
                <BarChart3 size={14} /> Agent Reports ({analysis?.agent_reports.length || 0})
              </button>
              <button
                className={activeTab === "bets" ? "active" : ""}
                onClick={() => setActiveTab("bets")}
              >
                <Target size={14} /> Value Bets ({analysis?.final_bets.length || 0})
              </button>
            </div>

            <div className="modal-body">
              {activeTab === "v4" && analysis?.v4_analysis && (
                <V4PredictionsTab v4={analysis.v4_analysis} />
              )}

              {activeTab === "players" && analysis && (
                <PlayerIntelTab analysis={analysis} match={match} />
              )}

              {activeTab === "overview" && (
                <div className="overview-tab">
                  {/* Team Forms */}
                  <div className="forms-grid">
                    {analysis?.home_form && (
                      <FormSection form={analysis.home_form} label="Home" />
                    )}
                    {analysis?.away_form && (
                      <FormSection form={analysis.away_form} label="Away" />
                    )}
                  </div>

                  {/* H2H */}
                  {analysis?.h2h && analysis.h2h.total_matches > 0 && (
                    <H2HSection h2h={analysis.h2h} />
                  )}

                  {/* Quick summary of top bets */}
                  {analysis && analysis.final_bets.length > 0 && (
                    <div className="quick-summary">
                      <h4>Top 5 Value Bets</h4>
                      {analysis.final_bets.slice(0, 5).map((b, i) => (
                        <div key={i} className="quick-bet">
                          <span className={`risk-badge risk-${b.risk_level.toLowerCase()}`}>
                            {b.risk_level}
                          </span>
                          <span className="quick-bet-market">{b.market_display}</span>
                          <span className="quick-bet-outcome">{b.outcome}</span>
                          <span className="quick-bet-odds">@ {b.best_odds.toFixed(2)}</span>
                          <span className="quick-bet-ev">+{b.expected_value.toFixed(1)}% EV</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === "agents" && analysis && (
                <div className="agents-tab">
                  {analysis.agent_reports.map((r, i) => (
                    <AgentReportCard key={i} report={r} />
                  ))}
                </div>
              )}

              {activeTab === "bets" && analysis && (
                <div className="bets-tab">
                  <ValueBetsSection bets={analysis.final_bets} />
                  {analysis.final_bets.length > 0 && (
                    <div className="bets-summary">
                      <div className="summary-stat">
                        <span>Total Value Bets</span>
                        <strong>{analysis.final_bets.length}</strong>
                      </div>
                      <div className="summary-stat">
                        <span>Low Risk</span>
                        <strong>{analysis.final_bets.filter((b) => b.risk_level === "LOW").length}</strong>
                      </div>
                      <div className="summary-stat">
                        <span>Medium Risk</span>
                        <strong>{analysis.final_bets.filter((b) => b.risk_level === "MEDIUM").length}</strong>
                      </div>
                      <div className="summary-stat">
                        <span>High Risk</span>
                        <strong>{analysis.final_bets.filter((b) => b.risk_level === "HIGH").length}</strong>
                      </div>
                      <div className="summary-stat">
                        <span>Avg EV</span>
                        <strong>
                          +{(analysis.final_bets.reduce((s, b) => s + b.expected_value, 0) / analysis.final_bets.length).toFixed(1)}%
                        </strong>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}

        {/* No analysis yet */}
        {!analysis || analysis.status === "none" ? (
          <div className="no-analysis">
            <p>Click "Analyze" to start the multi-agent analysis for this match.</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
