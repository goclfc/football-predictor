async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function fetchMatches(params?: {
  status?: string;
  league?: string;
  date_from?: string;
  date_to?: string;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.league) query.set("league", params.league);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  return request<import("../types").MatchesResponse>(
    `/api/matches${qs ? `?${qs}` : ""}`
  );
}

export function refreshMatches() {
  return request<import("../types").MatchesResponse>("/api/matches/refresh", {
    method: "POST",
  });
}

export function startAnalysis(matchId: string) {
  return request<{ analysis_id: string; status: string }>(
    `/api/matches/${matchId}/analyze`,
    { method: "POST" }
  );
}

export function getAnalysis(analysisId: string) {
  return request<import("../types").Analysis>(`/api/analysis/${analysisId}`);
}

export function getLatestAnalysis(matchId: string) {
  return request<import("../types").Analysis>(
    `/api/matches/${matchId}/latest-analysis`
  );
}
