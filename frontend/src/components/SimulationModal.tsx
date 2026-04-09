import { useState, useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { SimulationResult, MonteCarloResult, SimValueBet } from "../types";
import "./SimulationModal.css";

interface SimulationModalProps {
  simulation: SimulationResult | null;
  monteCarlo?: MonteCarloResult | null;
  simValueBets?: SimValueBet[];
  homeTeam: string;
  awayTeam: string;
  league: string;
  isOpen: boolean;
  onClose: () => void;
  isSimulating: boolean;
}

type TabType = "transcript" | "stats" | "montecarlo" | "bets" | "moments" | "summary";

export default function SimulationModal({
  simulation,
  monteCarlo,
  simValueBets,
  homeTeam,
  awayTeam,
  isOpen,
  onClose,
  isSimulating: _isSimulating,
}: SimulationModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("transcript");
  const [visibleEvents, setVisibleEvents] = useState<number>(0);
  const transcriptRef = useRef<HTMLDivElement>(null);

  // Reset visible events when simulation changes
  useEffect(() => {
    if (simulation) {
      setVisibleEvents(0);
    }
  }, [simulation]);

  // Auto-scroll and animate events — batch 3 at a time, 120ms apart
  useEffect(() => {
    if (!simulation) return;

    if (visibleEvents < simulation.events.length) {
      const timer = setTimeout(() => {
        setVisibleEvents((prev) => Math.min(prev + 3, simulation.events.length));
      }, 120);
      return () => clearTimeout(timer);
    }
  }, [simulation, visibleEvents]);

  // Auto-scroll transcript to bottom
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [visibleEvents]);

  if (!isOpen || !simulation) return null;

  const { final_score, half_time_score, events, stats, motm, match_summary, key_moments, xg } =
    simulation;

  const getEventIcon = (type: string): string => {
    switch (type) {
      case "goal":
        return "⚽";
      case "yellow_card":
        return "🟨";
      case "red_card":
        return "🟥";
      case "corner":
        return "📐";
      case "substitution":
        return "🔄";
      case "foul":
        return "⚠️";
      case "offside":
        return "📍";
      case "shot":
        return "🎯";
      default:
        return "•";
    }
  };

  const getStatValue = (statKey: keyof typeof stats, teamIndex: 0 | 1): number => {
    const stat = stats[statKey];
    return stat ? stat[teamIndex] : 0;
  };

  const getStatPercentage = (
    statKey: keyof typeof stats,
    teamIndex: 0 | 1
  ): number => {
    const stat = stats[statKey];
    if (!stat) return 0;
    const [home, away] = stat;
    const total = home + away;
    if (total === 0) return 0;
    return teamIndex === 0 ? (home / total) * 100 : (away / total) * 100;
  };

  const statLabels: Record<keyof typeof stats, string> = {
    possession: "Possession",
    shots: "Shots",
    shots_on_target: "Shots on Target",
    corners: "Corners",
    fouls: "Fouls",
    yellow_cards: "Yellow Cards",
    red_cards: "Red Cards",
    offsides: "Offsides",
    passes: "Passes",
  };

  const statOrder: (keyof typeof stats)[] = [
    "possession",
    "shots",
    "shots_on_target",
    "corners",
    "fouls",
    "yellow_cards",
    "red_cards",
    "passes",
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="simulation-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="sim-header">
          <div className="sim-header-content">
            <div className="sim-match-title">
              <span className="sim-team-name">{homeTeam}</span>
              <div className="sim-score-container">
                <div className="sim-score-display">
                  <span className="sim-final-score">
                    {final_score.home}
                  </span>
                  <span className="sim-score-separator">−</span>
                  <span className="sim-final-score">
                    {final_score.away}
                  </span>
                </div>
                <div className="sim-ht-score">
                  HT: {half_time_score.home} − {half_time_score.away}
                </div>
              </div>
              <span className="sim-team-name">{awayTeam}</span>
            </div>
            <div className="sim-motm-badge">
              <span className="sim-motm-label">MOTM</span>
              <span className="sim-motm-name">{motm}</span>
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="sim-tabs">
          <button
            className={`sim-tab ${activeTab === "transcript" ? "active" : ""}`}
            onClick={() => setActiveTab("transcript")}
          >
            Match Transcript
          </button>
          <button
            className={`sim-tab ${activeTab === "stats" ? "active" : ""}`}
            onClick={() => setActiveTab("stats")}
          >
            Stats
          </button>
          {monteCarlo && (
            <button
              className={`sim-tab ${activeTab === "montecarlo" ? "active" : ""}`}
              onClick={() => setActiveTab("montecarlo")}
            >
              Monte Carlo ({monteCarlo.n_simulations} sims)
            </button>
          )}
          {simValueBets && simValueBets.length > 0 && (
            <button
              className={`sim-tab ${activeTab === "bets" ? "active" : ""}`}
              onClick={() => setActiveTab("bets")}
              style={{ color: "#00e676" }}
            >
              Value Bets ({simValueBets.length})
            </button>
          )}
          <button
            className={`sim-tab ${activeTab === "moments" ? "active" : ""}`}
            onClick={() => setActiveTab("moments")}
          >
            Key Moments
          </button>
          <button
            className={`sim-tab ${activeTab === "summary" ? "active" : ""}`}
            onClick={() => setActiveTab("summary")}
          >
            Summary
          </button>
        </div>

        {/* Content */}
        <div className="sim-content">
          {/* Transcript Tab */}
          {activeTab === "transcript" && (
            <div className="sim-timeline" ref={transcriptRef}>
              {events.map((event, idx) => {
                const isVisible = idx < visibleEvents;
                const isGoal = event.type === "goal";
                const displayClass = isVisible
                  ? isGoal
                    ? "sim-event goal visible"
                    : "sim-event visible"
                  : "sim-event";

                return (
                  <div key={idx} className={displayClass}>
                    <div className="sim-event-minute">
                      <span>{event.minute}'</span>
                    </div>
                    <div className="sim-event-icon">{getEventIcon(event.type)}</div>
                    <div className="sim-event-content">
                      <div className="sim-event-text">{event.commentary}</div>
                      {event.team && (
                        <div className="sim-event-team">{event.team}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Stats Tab */}
          {activeTab === "stats" && (
            <div className="sim-stats">
              <div className="sim-stats-header">
                <span>{homeTeam}</span>
                <span className="sim-stats-center">xG: {xg[0].toFixed(2)}</span>
                <span>{awayTeam}</span>
              </div>

              {statOrder.map((statKey) => {
                const homeVal = getStatValue(statKey, 0);
                const awayVal = getStatValue(statKey, 1);
                const homePercent = getStatPercentage(statKey, 0);
                const awayPercent = getStatPercentage(statKey, 1);

                return (
                  <div key={statKey} className="sim-stat-row">
                    <div className="sim-stat-value home">
                      {typeof homeVal === "number" && homeVal % 1 === 0
                        ? homeVal
                        : homeVal.toFixed(1)}
                    </div>
                    <div className="sim-stat-label">{statLabels[statKey]}</div>
                    <div className="sim-stat-value away">
                      {typeof awayVal === "number" && awayVal % 1 === 0
                        ? awayVal
                        : awayVal.toFixed(1)}
                    </div>
                    <div className="sim-stat-bar">
                      <div className="sim-stat-bar-home" style={{ width: `${homePercent}%` }} />
                      <div className="sim-stat-bar-away" style={{ width: `${awayPercent}%` }} />
                    </div>
                  </div>
                );
              })}

              <div className="sim-stats-footer">
                <div className="sim-xg-stat">
                  <span>xG</span>
                  <span className="sim-xg-value">{xg[0].toFixed(2)}</span>
                  <span className="sim-xg-center">−</span>
                  <span className="sim-xg-value">{xg[1].toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Key Moments Tab */}
          {activeTab === "moments" && (
            <div className="sim-moments">
              {key_moments.map((moment, idx) => (
                <div key={idx} className="sim-moment-card">
                  <div className="sim-moment-number">{idx + 1}</div>
                  <p>{moment}</p>
                </div>
              ))}
            </div>
          )}

          {/* Monte Carlo Tab */}
          {activeTab === "montecarlo" && monteCarlo && (
            <div style={{ padding: "16px", color: "#e0e0e0" }}>
              <div style={{ marginBottom: "20px", padding: "16px", backgroundColor: "#1a1a1a", borderRadius: "8px", border: "1px solid #333" }}>
                <h4 style={{ fontSize: "14px", fontWeight: "600", marginBottom: "12px", color: "#60a5fa" }}>
                  Match Outcome Probabilities ({monteCarlo.n_simulations} simulations)
                </h4>
                <div style={{ display: "flex", height: "40px", borderRadius: "4px", overflow: "hidden", marginBottom: "8px" }}>
                  <div style={{ width: `${(monteCarlo.probabilities.home_win * 100)}%`, backgroundColor: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "12px", color: "#000" }}>
                    {(monteCarlo.probabilities.home_win * 100).toFixed(1)}%
                  </div>
                  <div style={{ width: `${(monteCarlo.probabilities.draw * 100)}%`, backgroundColor: "#fb923c", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "12px", color: "#000" }}>
                    {(monteCarlo.probabilities.draw * 100).toFixed(1)}%
                  </div>
                  <div style={{ width: `${(monteCarlo.probabilities.away_win * 100)}%`, backgroundColor: "#ef4444", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "12px", color: "#000" }}>
                    {(monteCarlo.probabilities.away_win * 100).toFixed(1)}%
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#888" }}>
                  <span>{homeTeam} Win</span>
                  <span>Draw</span>
                  <span>{awayTeam} Win</span>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
                <div style={{ padding: "14px", backgroundColor: "#1a1a1a", borderRadius: "8px", border: "1px solid #333" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: "600", marginBottom: "10px", color: "#60a5fa" }}>Goals Markets</h4>
                  {[
                    { label: "Over 1.5", prob: monteCarlo.probabilities.over15 },
                    { label: "Over 2.5", prob: monteCarlo.probabilities.over25 },
                    { label: "Over 3.5", prob: monteCarlo.probabilities.over35 },
                    { label: "BTTS Yes", prob: monteCarlo.probabilities.btts_yes },
                  ].map((item, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #222" }}>
                      <span style={{ fontSize: "12px", color: "#aaa" }}>{item.label}</span>
                      <span style={{ fontSize: "12px", fontWeight: "600", color: item.prob > 0.6 ? "#22c55e" : item.prob < 0.4 ? "#ef4444" : "#fb923c" }}>
                        {(item.prob * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                  <div style={{ marginTop: "8px", fontSize: "11px", color: "#666" }}>
                    Avg goals: {monteCarlo.averages.goals} ({monteCarlo.averages.home_goals} - {monteCarlo.averages.away_goals})
                  </div>
                </div>

                <div style={{ padding: "14px", backgroundColor: "#1a1a1a", borderRadius: "8px", border: "1px solid #333" }}>
                  <h4 style={{ fontSize: "13px", fontWeight: "600", marginBottom: "10px", color: "#60a5fa" }}>Corners & Cards</h4>
                  {[
                    { label: "Corners O 9.5", prob: monteCarlo.probabilities["corners_over_9.5"] || 0 },
                    { label: "Corners O 10.5", prob: monteCarlo.probabilities["corners_over_10.5"] || 0 },
                    { label: "Cards O 3.5", prob: monteCarlo.probabilities["cards_over_3.5"] || 0 },
                    { label: "Cards O 4.5", prob: monteCarlo.probabilities["cards_over_4.5"] || 0 },
                  ].map((item, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #222" }}>
                      <span style={{ fontSize: "12px", color: "#aaa" }}>{item.label}</span>
                      <span style={{ fontSize: "12px", fontWeight: "600", color: item.prob > 0.6 ? "#22c55e" : item.prob < 0.4 ? "#ef4444" : "#fb923c" }}>
                        {(item.prob * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                  <div style={{ marginTop: "8px", fontSize: "11px", color: "#666" }}>
                    Avg corners: {monteCarlo.averages.corners} | Avg cards: {monteCarlo.averages.cards}
                  </div>
                </div>
              </div>

              <div style={{ padding: "14px", backgroundColor: "#1a1a1a", borderRadius: "8px", border: "1px solid #333" }}>
                <h4 style={{ fontSize: "13px", fontWeight: "600", marginBottom: "10px", color: "#60a5fa" }}>Most Likely Scorelines</h4>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {monteCarlo.top_scorelines.map((s, i) => (
                    <div key={i} style={{
                      padding: "8px 14px",
                      backgroundColor: i === 0 ? "#22c55e15" : "#111",
                      borderRadius: "6px",
                      border: `1px solid ${i === 0 ? "#22c55e40" : "#333"}`,
                      textAlign: "center"
                    }}>
                      <div style={{ fontSize: "16px", fontWeight: "700", color: i === 0 ? "#22c55e" : "#e0e0e0" }}>{s.score}</div>
                      <div style={{ fontSize: "11px", color: "#888" }}>{s.pct}%</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Value Bets Tab */}
          {activeTab === "bets" && simValueBets && (
            <div style={{ padding: "16px", color: "#e0e0e0" }}>
              <div style={{ marginBottom: "12px", fontSize: "12px", color: "#888" }}>
                Value bets confirmed by simulation outcome — backed by {monteCarlo?.n_simulations || 500} Monte Carlo probability estimates
              </div>
              {simValueBets.map((bet, i) => {
                const edgeColor = bet.edge > 0.10 ? "#22c55e" : bet.edge > 0.06 ? "#fb923c" : "#60a5fa";
                const riskColors: Record<string, string> = { LOW: "#22c55e", MEDIUM: "#fb923c", HIGH: "#ef4444" };
                return (
                  <div key={i} style={{
                    padding: "14px",
                    marginBottom: "8px",
                    backgroundColor: "#1a1a1a",
                    borderRadius: "8px",
                    border: `1px solid ${edgeColor}30`,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <div>
                        <span style={{ fontSize: "14px", fontWeight: "600", color: "#e0e0e0" }}>{bet.market}</span>
                        <span style={{
                          marginLeft: "8px",
                          fontSize: "10px",
                          padding: "2px 6px",
                          borderRadius: "3px",
                          backgroundColor: `${riskColors[bet.risk_level] || "#888"}20`,
                          color: riskColors[bet.risk_level] || "#888",
                          border: `1px solid ${riskColors[bet.risk_level] || "#888"}40`,
                        }}>
                          {bet.risk_level}
                        </span>
                      </div>
                      <div style={{ fontSize: "18px", fontWeight: "700", color: edgeColor }}>
                        @{bet.odds.toFixed(2)}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "16px", fontSize: "12px", marginBottom: "6px" }}>
                      <div>
                        <span style={{ color: "#888" }}>Sim prob: </span>
                        <span style={{ color: "#e0e0e0", fontWeight: "600" }}>{(bet.sim_prob * 100).toFixed(1)}%</span>
                      </div>
                      <div>
                        <span style={{ color: "#888" }}>Implied: </span>
                        <span style={{ color: "#888" }}>{(bet.implied_prob * 100).toFixed(1)}%</span>
                      </div>
                      <div>
                        <span style={{ color: "#888" }}>Edge: </span>
                        <span style={{ color: edgeColor, fontWeight: "600" }}>+{(bet.edge * 100).toFixed(1)}%</span>
                      </div>
                      <div>
                        <span style={{ color: "#888" }}>EV: </span>
                        <span style={{ color: "#22c55e", fontWeight: "600" }}>+{bet.ev_pct.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {bet.flags.map((flag, j) => (
                        <span key={j} style={{
                          fontSize: "10px",
                          padding: "2px 6px",
                          borderRadius: "3px",
                          backgroundColor: flag === "STRONG_EDGE" ? "#22c55e15" : flag.startsWith("SIM_") ? "#60a5fa15" : "#fb923c15",
                          color: flag === "STRONG_EDGE" ? "#22c55e" : flag.startsWith("SIM_") ? "#60a5fa" : "#fb923c",
                        }}>
                          {flag}
                        </span>
                      ))}
                    </div>
                    {/* Probability bar */}
                    <div style={{ marginTop: "6px", height: "4px", backgroundColor: "#333", borderRadius: "2px", overflow: "hidden" }}>
                      <div style={{
                        height: "100%",
                        width: `${Math.min(bet.sim_prob * 100, 100)}%`,
                        backgroundColor: edgeColor,
                        borderRadius: "2px",
                      }} />
                    </div>
                  </div>
                );
              })}
              {simValueBets.length > 0 && (
                <div style={{
                  marginTop: "16px",
                  padding: "12px",
                  backgroundColor: "#0d1117",
                  borderRadius: "8px",
                  border: "1px solid #22c55e30",
                  display: "flex",
                  justifyContent: "space-around",
                  fontSize: "12px",
                }}>
                  <div>
                    <span style={{ color: "#888" }}>Total Bets: </span>
                    <span style={{ color: "#e0e0e0", fontWeight: "600" }}>{simValueBets.length}</span>
                  </div>
                  <div>
                    <span style={{ color: "#888" }}>Avg Edge: </span>
                    <span style={{ color: "#22c55e", fontWeight: "600" }}>
                      +{(simValueBets.reduce((s, b) => s + b.edge, 0) / simValueBets.length * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span style={{ color: "#888" }}>Avg EV: </span>
                    <span style={{ color: "#22c55e", fontWeight: "600" }}>
                      +{(simValueBets.reduce((s, b) => s + b.ev_pct, 0) / simValueBets.length).toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Summary Tab */}
          {activeTab === "summary" && (
            <div className="sim-summary">
              <div className="sim-summary-section">
                <h3>Match Summary</h3>
                <p>{match_summary}</p>
              </div>

              <div className="sim-summary-stats">
                <div className="sim-summary-stat">
                  <span className="sim-summary-label">Final Score</span>
                  <span className="sim-summary-value">
                    {final_score.home} − {final_score.away}
                  </span>
                </div>
                <div className="sim-summary-stat">
                  <span className="sim-summary-label">Half-Time</span>
                  <span className="sim-summary-value">
                    {half_time_score.home} − {half_time_score.away}
                  </span>
                </div>
                <div className="sim-summary-stat">
                  <span className="sim-summary-label">xG (Home)</span>
                  <span className="sim-summary-value">{xg[0].toFixed(2)}</span>
                </div>
                <div className="sim-summary-stat">
                  <span className="sim-summary-label">xG (Away)</span>
                  <span className="sim-summary-value">{xg[1].toFixed(2)}</span>
                </div>
                <div className="sim-summary-stat">
                  <span className="sim-summary-label">Man of the Match</span>
                  <span className="sim-summary-value">{motm}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
