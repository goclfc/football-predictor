import { useState, useEffect, useCallback, useRef } from "react";
import { Activity } from "lucide-react";
import MatchTable from "./components/MatchTable";
import AnalysisModal from "./components/AnalysisModal";
import SimulationModal from "./components/SimulationModal";
import { fetchMatches, refreshMatches, startAnalysis, getAnalysis, getLatestAnalysis } from "./api/client";
import type { Match, Analysis, MatchFilter, SimulationResult, FullSimulationResponse, SimValueBet, MonteCarloResult } from "./types";
import "./App.css";

export default function App() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [leagues, setLeagues] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<MatchFilter>("all");
  const [selectedLeague, setSelectedLeague] = useState("");

  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [currentAnalysis, setCurrentAnalysis] = useState<Analysis | null>(null);
  const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(new Set());
  const [analyzedIds, setAnalyzedIds] = useState<Set<string>>(new Set());

  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [monteCarlo, setMonteCarlo] = useState<MonteCarloResult | null>(null);
  const [simValueBets, setSimValueBets] = useState<SimValueBet[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showSimulation, setShowSimulation] = useState(false);

  const pollRef = useRef<number | null>(null);

  const loadMatches = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filter !== "all") params.status = filter;
      if (selectedLeague) params.league = selectedLeague;
      const data = await fetchMatches(params);
      setMatches(data.matches);
      setLeagues(data.leagues);
    } catch (err) {
      console.error("Failed to load matches:", err);
    } finally {
      setLoading(false);
    }
  }, [filter, selectedLeague]);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const data = await refreshMatches();
      setMatches(data.matches);
      setLeagues(data.leagues);
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const pollAnalysis = useCallback((analysisId: string, matchId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    const poll = async () => {
      try {
        const data = await getAnalysis(analysisId);
        setCurrentAnalysis(data);

        if (data.status === "completed" || data.status === "error") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setAnalyzingIds((prev) => {
            const next = new Set(prev);
            next.delete(matchId);
            return next;
          });
          if (data.status === "completed") {
            setAnalyzedIds((prev) => new Set(prev).add(matchId));
          }
        }
      } catch {
        // keep polling
      }
    };

    poll();
    pollRef.current = window.setInterval(poll, 800);
  }, []);

  const handleAnalyze = useCallback(
    async (match: Match) => {
      setSelectedMatch(match);

      // Check if already analyzed
      if (analyzedIds.has(match.id) || match.has_analysis) {
        try {
          const existing = await getLatestAnalysis(match.id);
          if (existing && existing.status !== "none") {
            setCurrentAnalysis(existing);
            return;
          }
        } catch {
          // continue to start new analysis
        }
      }

      // Start new analysis
      setCurrentAnalysis(null);
      setAnalyzingIds((prev) => new Set(prev).add(match.id));

      try {
        const { analysis_id } = await startAnalysis(match.id);
        pollAnalysis(analysis_id, match.id);
      } catch (err) {
        console.error("Analysis failed:", err);
        setAnalyzingIds((prev) => {
          const next = new Set(prev);
          next.delete(match.id);
          return next;
        });
      }
    },
    [analyzedIds, pollAnalysis]
  );

  const handleCloseModal = () => {
    setSelectedMatch(null);
    setCurrentAnalysis(null);
    setShowSimulation(false);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const handleSimulate = useCallback(
    async (matchId: string) => {
      setIsSimulating(true);
      try {
        const response = await fetch(`/api/matches/${matchId}/simulate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        if (!response.ok) throw new Error("Simulation failed");
        const data: FullSimulationResponse = await response.json();
        setSimulationResult(data.simulation);
        setMonteCarlo(data.monte_carlo || null);
        setSimValueBets(data.sim_value_bets || []);
        setShowSimulation(true);
      } catch (err) {
        console.error("Simulation error:", err);
      } finally {
        setIsSimulating(false);
      }
    },
    []
  );

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <Activity size={24} className="logo-icon" />
          <h1>Football Predictor</h1>
          <span className="header-badge">Multi-Agent AI</span>
        </div>
        <div className="header-right">
          <span className="match-count">{matches.length} matches</span>
        </div>
      </header>

      <main>
        <MatchTable
          matches={matches}
          leagues={leagues}
          loading={loading}
          onAnalyze={handleAnalyze}
          onRefresh={handleRefresh}
          analyzingIds={analyzingIds}
          analyzedIds={analyzedIds}
          filter={filter}
          onFilterChange={setFilter}
          selectedLeague={selectedLeague}
          onLeagueChange={setSelectedLeague}
        />
      </main>

      {selectedMatch && (
        <>
          <AnalysisModal
            match={selectedMatch}
            analysis={currentAnalysis}
            onClose={handleCloseModal}
            onSimulate={handleSimulate}
            isSimulating={isSimulating}
          />
          {showSimulation && (
            <SimulationModal
              simulation={simulationResult}
              monteCarlo={monteCarlo}
              simValueBets={simValueBets}
              homeTeam={selectedMatch.home_team}
              awayTeam={selectedMatch.away_team}
              league={selectedMatch.league}
              isOpen={showSimulation}
              onClose={() => setShowSimulation(false)}
              isSimulating={isSimulating}
            />
          )}
        </>
      )}
    </div>
  );
}
