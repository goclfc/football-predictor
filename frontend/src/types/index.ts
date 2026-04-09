export interface Match {
  id: string;
  home_team: string;
  away_team: string;
  league: string;
  commence_time: string;
  market_count: number;
  bookmaker_count: number;
  markets_summary: Record<string, Record<string, number>>;
  has_analysis: boolean;
}

export interface MatchesResponse {
  matches: Match[];
  total: number;
  leagues: string[];
}

export interface AnalysisProgress {
  step: string;
  message: string;
  timestamp: string;
}

export interface AgentPrediction {
  market: string;
  outcome: string;
  probability: number;
  confidence: number;
  reasoning: string;
  data_points: string[];
}

export interface AgentReport {
  agent_name: string;
  match_id: string;
  home_team: string;
  away_team: string;
  overall_assessment: string;
  reliability_score: number;
  predictions: AgentPrediction[];
}

export interface FinalBet {
  match_id: string;
  home_team: string;
  away_team: string;
  league: string;
  match_date: string;
  market: string;
  market_display: string;
  outcome: string;
  confidence_pct: number;
  best_odds: number;
  best_bookmaker: string;
  expected_value: number;
  agent_agreement: number;
  reasoning: string[];
  risk_level: string;
  recommended_stake: number;
  calibrated_prob?: number;
  raw_prob?: number;
  edge_pct?: number;
  v4_flags?: string[];
}

export interface TeamForm {
  team: string;
  form_string: string;
  wins: number;
  draws: number;
  losses: number;
  points_last_10: number;
  goals_scored_avg: number;
  goals_conceded_avg: number;
  corners_avg: number;
  cards_avg: number;
  shots_on_target_avg: number;
  throw_ins_avg: number;
  fouls_avg: number;
  matches: {
    goals_for: number;
    goals_against: number;
    corners: number;
    cards_yellow: number;
    cards_red: number;
    shots_on_target: number;
    result: string;
    home: boolean;
    date?: string;
    opponent?: string;
  }[];
}

export interface H2H {
  home: string;
  away: string;
  total_matches: number;
  home_wins: number;
  away_wins: number;
  draws: number;
  avg_goals_per_match: number;
  avg_corners_per_match: number;
  avg_cards_per_match: number;
  btts_percentage: number;
  over_2_5_percentage: number;
}

export interface V4Analysis {
  version: string;
  league: string;
  raw_probs: { home_win: number; draw: number; away_win: number };
  calibrated_probs: { home_win: number; draw: number; away_win: number; shrinkage_applied: boolean };
  expected_goals: { home: number; away: number; total: number };
  match_stats: {
    corners: number; home_corners: number; away_corners: number;
    cards: number; home_cards: number; away_cards: number;
    fouls: number; shots: number; sot: number; reds: number;
    profile: string;
  };
  corner_ou: Record<string, number>;
  card_ou: Record<string, number>;
  value_bets: Array<{
    market: string; model_prob: number; implied_prob: number;
    odds: number; edge: number; ev_pct: number; rating: string;
    flags?: string[];
  }>;
  elo_ratings: { home: number; away: number };
  league_baseline: { avg_goals: number; avg_corners: number; avg_cards: number };
  context: {
    is_derby: boolean;
    home_position: number | null;
    away_position: number | null;
    v5_adjustments?: string[];
    agent_signals?: {
      goals_adj: number;
      corners_adj: number;
      cards_adj: number;
      shots_adj: number;
      xg_home: number;
      xg_away: number;
      referee_yellows: number;
      referee_strictness: number;
      rivalry_score: number;
      fatigue_home: number;
      fatigue_away: number;
      momentum_home: number;
      momentum_away: number;
      home_injuries: number;
      away_injuries: number;
      set_piece_adv: string;
      tactical_edge: number;
    };
  };
  notes: string[];
}

export interface Analysis {
  id: string;
  match_id: string;
  status: "running" | "completed" | "error" | "none";
  progress: AnalysisProgress[];
  home_form: TeamForm | null;
  away_form: TeamForm | null;
  h2h: H2H | null;
  home_stats: Record<string, unknown> | null;
  away_stats: Record<string, unknown> | null;
  agent_reports: AgentReport[];
  final_bets: FinalBet[];
  started_at: string;
  completed_at: string | null;
  v4_analysis: V4Analysis | null;
}

export type MatchFilter = "all" | "live" | "upcoming";

export interface SimulationEvent {
  minute: number;
  type: string;
  team?: string | null;
  player?: string;
  commentary: string;
}

export interface SimulationStats {
  possession: [number, number];
  shots: [number, number];
  shots_on_target: [number, number];
  corners: [number, number];
  fouls: [number, number];
  yellow_cards: [number, number];
  red_cards: [number, number];
  offsides: [number, number];
  passes: [number, number];
}

export interface SimValueBet {
  market: string;
  sim_prob: number;
  implied_prob: number;
  odds: number;
  edge: number;
  ev_pct: number;
  rating: string;
  risk_level: string;
  flags: string[];
  source: string;
}

export interface MonteCarloResult {
  n_simulations: number;
  probabilities: Record<string, number>;
  averages: Record<string, number>;
  top_scorelines: { score: string; count: number; pct: number }[];
}

export interface SimulationResult {
  match: string;
  final_score: { home: number; away: number };
  half_time_score: { home: number; away: number };
  events: SimulationEvent[];
  stats: SimulationStats;
  motm: string;
  match_summary: string;
  key_moments: string[];
  xg: [number, number];
}

export interface FullSimulationResponse {
  simulation: SimulationResult;
  agent_count: number;
  monte_carlo?: MonteCarloResult;
  sim_value_bets?: SimValueBet[];
}
