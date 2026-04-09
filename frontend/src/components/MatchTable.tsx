import { useState } from "react";
import {
  Search,
  RefreshCw,
  Zap,
  Clock,
  Radio,
  ChevronDown,
  Activity,
  CheckCircle2,
} from "lucide-react";
import type { Match, MatchFilter } from "../types";

interface Props {
  matches: Match[];
  leagues: string[];
  loading: boolean;
  onAnalyze: (match: Match) => void;
  onRefresh: () => void;
  analyzingIds: Set<string>;
  analyzedIds: Set<string>;
  filter: MatchFilter;
  onFilterChange: (f: MatchFilter) => void;
  selectedLeague: string;
  onLeagueChange: (l: string) => void;
}

const LEAGUE_FLAGS: Record<string, string> = {
  "Premier League": "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67\uDB40\uDC7F",
  "La Liga": "\uD83C\uDDEA\uD83C\uDDF8",
  Bundesliga: "\uD83C\uDDE9\uD83C\uDDEA",
  "Serie A": "\uD83C\uDDEE\uD83C\uDDF9",
  "Ligue 1": "\uD83C\uDDEB\uD83C\uDDF7",
  Eredivisie: "\uD83C\uDDF3\uD83C\uDDF1",
  "Primeira Liga": "\uD83C\uDDF5\uD83C\uDDF9",
  "Scottish Premiership": "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74\uDB40\uDC7F",
  Championship: "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67\uDB40\uDC7F",
  "Champions League": "\uD83C\uDFC6",
  "Europa League": "\uD83C\uDF1F",
};

function formatDate(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
    });
  } catch {
    return "TBD";
  }
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function isLive(commence_time: string): boolean {
  try {
    const ct = new Date(commence_time).getTime();
    const now = Date.now();
    return ct <= now && now <= ct + 2 * 60 * 60 * 1000;
  } catch {
    return false;
  }
}

function getMatchResultOdds(match: Match) {
  const mr = match.markets_summary?.h2h || match.markets_summary?.match_result;
  if (!mr) return null;
  const entries = Object.entries(mr);
  const home = entries.find(([k]) => k.includes(match.home_team));
  const draw = entries.find(([k]) => k.includes("Draw"));
  const away = entries.find(([k]) => k.includes(match.away_team));
  return {
    home: home ? home[1].toFixed(2) : "-",
    draw: draw ? draw[1].toFixed(2) : "-",
    away: away ? away[1].toFixed(2) : "-",
  };
}

export default function MatchTable({
  matches,
  leagues,
  loading,
  onAnalyze,
  onRefresh,
  analyzingIds,
  analyzedIds,
  filter,
  onFilterChange,
  selectedLeague,
  onLeagueChange,
}: Props) {
  const [search, setSearch] = useState("");

  const filtered = matches.filter((m) => {
    if (search) {
      const q = search.toLowerCase();
      if (
        !m.home_team.toLowerCase().includes(q) &&
        !m.away_team.toLowerCase().includes(q) &&
        !m.league.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  return (
    <div className="match-table-container">
      {/* Toolbar */}
      <div className="toolbar">
        <div className="toolbar-left">
          <div className="filter-tabs">
            <button
              className={`tab ${filter === "all" ? "active" : ""}`}
              onClick={() => onFilterChange("all")}
            >
              <Zap size={14} /> All
            </button>
            <button
              className={`tab ${filter === "live" ? "active" : ""}`}
              onClick={() => onFilterChange("live")}
            >
              <Radio size={14} /> Live
            </button>
            <button
              className={`tab ${filter === "upcoming" ? "active" : ""}`}
              onClick={() => onFilterChange("upcoming")}
            >
              <Clock size={14} /> Upcoming
            </button>
          </div>

          <div className="league-select">
            <select
              value={selectedLeague}
              onChange={(e) => onLeagueChange(e.target.value)}
            >
              <option value="">All Leagues</option>
              {leagues.map((l) => (
                <option key={l} value={l}>
                  {LEAGUE_FLAGS[l] || ""} {l}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="select-icon" />
          </div>
        </div>

        <div className="toolbar-right">
          <div className="search-box">
            <Search size={14} />
            <input
              placeholder="Search teams..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button className="btn-icon" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spinning" : ""} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>League</th>
              <th>Match</th>
              <th className="center">1</th>
              <th className="center">X</th>
              <th className="center">2</th>
              <th className="center">Markets</th>
              <th className="center">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="loading-cell">
                  <RefreshCw size={20} className="spinning" />
                  <span>Loading matches...</span>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-cell">
                  No matches found
                </td>
              </tr>
            ) : (
              filtered.map((m) => {
                const odds = getMatchResultOdds(m);
                const live = isLive(m.commence_time);
                const analyzing = analyzingIds.has(m.id);
                const analyzed = analyzedIds.has(m.id) || m.has_analysis;
                return (
                  <tr key={m.id} className={live ? "live-row" : ""}>
                    <td className="date-cell">
                      <div className="date-primary">{formatDate(m.commence_time)}</div>
                      <div className="date-secondary">
                        {live ? (
                          <span className="live-badge">
                            <Radio size={10} /> LIVE
                          </span>
                        ) : (
                          formatTime(m.commence_time)
                        )}
                      </div>
                    </td>
                    <td className="league-cell">
                      <span className="league-flag">
                        {LEAGUE_FLAGS[m.league] || "\u26BD"}
                      </span>
                      <span className="league-name">{m.league}</span>
                    </td>
                    <td className="match-cell">
                      <span className="team home">{m.home_team}</span>
                      <span className="vs">vs</span>
                      <span className="team away">{m.away_team}</span>
                    </td>
                    <td className="odds-cell">{odds?.home || "-"}</td>
                    <td className="odds-cell">{odds?.draw || "-"}</td>
                    <td className="odds-cell">{odds?.away || "-"}</td>
                    <td className="center markets-cell">{m.market_count}</td>
                    <td className="action-cell">
                      {analyzing ? (
                        <button className="btn-analyze analyzing" disabled>
                          <Activity size={14} className="spinning" />
                          Analyzing...
                        </button>
                      ) : analyzed ? (
                        <button
                          className="btn-analyze analyzed"
                          onClick={() => onAnalyze(m)}
                        >
                          <CheckCircle2 size={14} />
                          View Results
                        </button>
                      ) : (
                        <button
                          className="btn-analyze"
                          onClick={() => onAnalyze(m)}
                        >
                          <Zap size={14} />
                          Analyze
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
