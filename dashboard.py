"""
Dashboard Generator — Creates a beautiful interactive HTML dashboard
showing all value bets with filtering and sorting.
"""
from typing import List, Dict
from agents.meta_agent import FinalBet
from datetime import datetime


def generate_dashboard(results: Dict, output_path: str) -> str:
    """Generate the HTML dashboard and save to file."""
    all_bets: List[FinalBet] = results["all_bets"]
    summary = results["summary"]
    matches = results["matches"]

    # Prepare bet data as JSON for the frontend
    bets_json = []
    for bet in all_bets:
        bets_json.append({
            "match": f"{bet.home_team} vs {bet.away_team}",
            "home": bet.home_team,
            "away": bet.away_team,
            "league": bet.league,
            "matchDate": bet.match_date,
            "market": bet.market_display,
            "marketKey": bet.market,
            "outcome": bet.outcome,
            "confidence": bet.confidence_pct,
            "odds": bet.best_odds,
            "bookmaker": bet.best_bookmaker,
            "ev": bet.expected_value,
            "agreement": bet.agent_agreement,
            "risk": bet.risk_level,
            "stake": bet.recommended_stake,
            "reasoning": bet.reasoning,
        })

    # Match summaries for the match cards
    match_summaries = []
    for m in matches:
        match = m["match"]
        bets = m["final_bets"]
        home_form = m["home_form"]
        away_form = m["away_form"]
        match_summaries.append({
            "home": match["home_team"],
            "away": match["away_team"],
            "league": match.get("league", ""),
            "time": match.get("commence_time", ""),
            "homeForm": home_form["form_string"],
            "awayForm": away_form["form_string"],
            "valueBets": len(bets),
            "topEV": max([b.expected_value for b in bets]) if bets else 0,
        })

    import json
    bets_data = json.dumps(bets_json)
    matches_data = json.dumps(match_summaries)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Football Betting Intelligence</title>
<style>
  :root {{
    --bg: #0a0e17;
    --surface: #121929;
    --surface2: #1a2236;
    --border: #2a3452;
    --text: #e4e8f1;
    --text2: #8892a8;
    --green: #22c55e;
    --green-bg: rgba(34,197,94,0.12);
    --red: #ef4444;
    --red-bg: rgba(239,68,68,0.1);
    --yellow: #eab308;
    --yellow-bg: rgba(234,179,8,0.1);
    --blue: #3b82f6;
    --blue-bg: rgba(59,130,246,0.12);
    --purple: #a855f7;
    --accent: #06b6d4;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

  /* Header */
  .header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 0 32px; border-bottom: 1px solid var(--border); margin-bottom: 28px;
  }}
  .header h1 {{ font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
  .header h1 span {{ color: var(--accent); }}
  .header-meta {{ text-align: right; color: var(--text2); font-size: 13px; }}

  /* Summary Cards */
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; transition: transform 0.15s;
  }}
  .card:hover {{ transform: translateY(-2px); }}
  .card-label {{ font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
  .card-value {{ font-size: 32px; font-weight: 700; }}
  .card-value.green {{ color: var(--green); }}
  .card-value.yellow {{ color: var(--yellow); }}
  .card-value.red {{ color: var(--red); }}
  .card-value.blue {{ color: var(--blue); }}

  /* Filters */
  .filters {{
    display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
    padding: 16px; background: var(--surface); border-radius: 12px; border: 1px solid var(--border);
  }}
  .filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
  .filter-group label {{ font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; }}
  .filter-group select, .filter-group input {{
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    padding: 8px 12px; border-radius: 8px; font-size: 13px; min-width: 140px;
  }}
  .filter-group select:focus, .filter-group input:focus {{ outline: none; border-color: var(--accent); }}

  /* Match Ribbon */
  .match-ribbon {{
    display: flex; gap: 12px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 24px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .match-chip {{
    flex-shrink: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 12px 16px; cursor: pointer; transition: all 0.15s; min-width: 220px;
  }}
  .match-chip:hover, .match-chip.active {{ border-color: var(--accent); background: var(--surface2); }}
  .match-chip .teams {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
  .match-chip .league {{ font-size: 11px; color: var(--text2); }}
  .match-chip .meta {{ display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; }}
  .match-chip .bets-count {{ color: var(--green); font-weight: 600; }}
  .form-dots {{ display: inline-flex; gap: 3px; }}
  .form-dot {{
    width: 16px; height: 16px; border-radius: 3px; display: inline-flex;
    align-items: center; justify-content: center; font-size: 9px; font-weight: 700;
  }}
  .form-dot.W {{ background: var(--green-bg); color: var(--green); }}
  .form-dot.D {{ background: var(--yellow-bg); color: var(--yellow); }}
  .form-dot.L {{ background: var(--red-bg); color: var(--red); }}

  /* Table */
  .table-wrap {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
    padding: 14px 16px; text-align: left; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text2); background: var(--surface2);
    border-bottom: 1px solid var(--border); cursor: pointer; user-select: none;
    white-space: nowrap;
  }}
  thead th:hover {{ color: var(--accent); }}
  thead th.sorted {{ color: var(--accent); }}
  thead th .arrow {{ margin-left: 4px; font-size: 10px; }}
  tbody tr {{
    border-bottom: 1px solid var(--border); transition: background 0.1s; cursor: pointer;
  }}
  tbody tr:hover {{ background: var(--surface2); }}
  tbody tr:last-child {{ border-bottom: none; }}
  td {{ padding: 14px 16px; font-size: 13px; white-space: nowrap; }}

  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 6px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
  }}
  .badge-low {{ background: var(--green-bg); color: var(--green); }}
  .badge-medium {{ background: var(--yellow-bg); color: var(--yellow); }}
  .badge-high {{ background: var(--red-bg); color: var(--red); }}

  .ev-cell {{ font-weight: 700; }}
  .ev-cell.positive {{ color: var(--green); }}
  .confidence-bar {{
    width: 60px; height: 6px; background: var(--surface2); border-radius: 3px;
    display: inline-block; vertical-align: middle; margin-right: 8px;
  }}
  .confidence-fill {{ height: 100%; border-radius: 3px; }}

  .odds-cell {{ font-weight: 600; color: var(--accent); }}
  .bookmaker {{ color: var(--text2); font-size: 11px; }}
  .stake-cell {{ color: var(--purple); font-weight: 600; }}

  /* Reasoning tooltip */
  .reasoning-row {{ display: none; }}
  .reasoning-row.visible {{ display: table-row; }}
  .reasoning-row td {{
    padding: 12px 16px 16px 48px; background: var(--surface2);
    font-size: 12px; color: var(--text2); line-height: 1.6;
  }}
  .reasoning-row td ul {{ list-style: none; padding: 0; }}
  .reasoning-row td li {{ padding: 4px 0; }}
  .reasoning-row td li::before {{ content: "\\2192 "; color: var(--accent); }}

  /* Footer */
  .footer {{
    margin-top: 32px; padding: 16px 0; border-top: 1px solid var(--border);
    color: var(--text2); font-size: 12px; text-align: center;
  }}

  /* Responsive */
  @media (max-width: 768px) {{
    .filters {{ flex-direction: column; }}
    .summary {{ grid-template-columns: repeat(2, 1fr); }}
    td, th {{ padding: 10px 8px; font-size: 12px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <div>
      <h1><span>&#9917;</span> Football Betting <span>Intelligence</span></h1>
      <p style="color:var(--text2);font-size:13px;margin-top:4px;">Multi-Agent Value Bet Detection System</p>
    </div>
    <div class="header-meta">
      <div>Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}</div>
      <div style="margin-top:4px;">{summary['total_matches']} matches analyzed</div>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="summary">
    <div class="card">
      <div class="card-label">Total Value Bets</div>
      <div class="card-value green">{summary['total_value_bets']}</div>
    </div>
    <div class="card">
      <div class="card-label">Low Risk</div>
      <div class="card-value green">{summary['low_risk']}</div>
    </div>
    <div class="card">
      <div class="card-label">Medium Risk</div>
      <div class="card-value yellow">{summary['medium_risk']}</div>
    </div>
    <div class="card">
      <div class="card-label">High Risk</div>
      <div class="card-value red">{summary['high_risk']}</div>
    </div>
    <div class="card">
      <div class="card-label">Matches Scanned</div>
      <div class="card-value blue">{summary['total_matches']}</div>
    </div>
  </div>

  <!-- Match Ribbon -->
  <div class="match-ribbon" id="matchRibbon"></div>

  <!-- Filters -->
  <div class="filters">
    <div class="filter-group">
      <label>Market Type</label>
      <select id="filterMarket" onchange="applyFilters()">
        <option value="all">All Markets</option>
        <option value="goals">Goals</option>
        <option value="corners">Corners</option>
        <option value="cards">Cards</option>
        <option value="throwins">Throw-ins</option>
        <option value="shots">Shots on Target</option>
        <option value="btts">BTTS</option>
        <option value="match_result">Match Result</option>
        <option value="first_half">1st Half</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Risk Level</label>
      <select id="filterRisk" onchange="applyFilters()">
        <option value="all">All Risks</option>
        <option value="LOW">Low Only</option>
        <option value="MEDIUM">Medium Only</option>
        <option value="HIGH">High Only</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Min Confidence %</label>
      <input type="number" id="filterConfidence" value="0" min="0" max="100" onchange="applyFilters()">
    </div>
    <div class="filter-group">
      <label>Min EV %</label>
      <input type="number" id="filterEV" value="0" step="0.5" onchange="applyFilters()">
    </div>
    <div class="filter-group">
      <label>League</label>
      <select id="filterLeague" onchange="applyFilters()">
        <option value="all">All Leagues</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Match</label>
      <select id="filterMatch" onchange="applyFilters()">
        <option value="all">All Matches</option>
      </select>
    </div>
  </div>

  <!-- Bets Table -->
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th onclick="sortTable('matchDate')">Date <span class="arrow"></span></th>
          <th onclick="sortTable('match')">Match <span class="arrow"></span></th>
          <th onclick="sortTable('league')">League <span class="arrow"></span></th>
          <th onclick="sortTable('market')">Market <span class="arrow"></span></th>
          <th onclick="sortTable('outcome')">Bet <span class="arrow"></span></th>
          <th onclick="sortTable('odds')">Odds <span class="arrow"></span></th>
          <th onclick="sortTable('confidence')">Confidence <span class="arrow"></span></th>
          <th onclick="sortTable('ev')">EV% <span class="arrow"></span></th>
          <th onclick="sortTable('agreement')">Agents <span class="arrow"></span></th>
          <th onclick="sortTable('risk')">Risk <span class="arrow"></span></th>
          <th onclick="sortTable('stake')">Stake <span class="arrow"></span></th>
          <th>Book</th>
        </tr>
      </thead>
      <tbody id="betsBody"></tbody>
    </table>
  </div>

  <div class="footer">
    Football Betting Intelligence Engine &mdash; Multi-Agent System &mdash;
    5 Agents: Form | Historical | Stats | Market | Value &rarr; Meta-Agent Synthesis
    <br>Data is simulated for demo. Connect API keys for live odds &amp; stats.
  </div>

</div>

<script>
const ALL_BETS = {bets_data};
const ALL_MATCHES = {matches_data};
let currentSort = {{ key: 'ev', asc: false }};
let filteredBets = [...ALL_BETS];

// Init
function formatDate(isoStr) {{
  if (!isoStr || isoStr === 'TBD') return 'TBD';
  try {{
    const d = new Date(isoStr);
    const day = d.getDate().toString().padStart(2, '0');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const mon = months[d.getMonth()];
    const h = d.getHours().toString().padStart(2, '0');
    const m = d.getMinutes().toString().padStart(2, '0');
    return day + ' ' + mon + ', ' + h + ':' + m;
  }} catch(e) {{ return isoStr; }}
}}

function init() {{
  // Populate league filter
  const leagues = [...new Set(ALL_BETS.map(b => b.league))];
  const leagueSel = document.getElementById('filterLeague');
  leagues.forEach(l => {{
    const opt = document.createElement('option');
    opt.value = l; opt.textContent = l;
    leagueSel.appendChild(opt);
  }});

  // Populate match filter
  const matches = [...new Set(ALL_BETS.map(b => b.match))];
  const matchSel = document.getElementById('filterMatch');
  matches.forEach(m => {{
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    matchSel.appendChild(opt);
  }});

  // Build match ribbon
  buildMatchRibbon();

  // Render
  applyFilters();
}}

function buildMatchRibbon() {{
  const ribbon = document.getElementById('matchRibbon');
  ribbon.innerHTML = '';
  ALL_MATCHES.forEach(m => {{
    const chip = document.createElement('div');
    chip.className = 'match-chip';
    chip.onclick = () => {{
      document.getElementById('filterMatch').value = m.home + ' vs ' + m.away;
      applyFilters();
      document.querySelectorAll('.match-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
    }};

    const formDots = (str) => str.slice(-5).split('').map(c =>
      '<span class="form-dot ' + c + '">' + c + '</span>'
    ).join('');

    const matchTime = m.time ? formatDate(m.time) : 'TBD';
    chip.innerHTML =
      '<div class="teams">' + m.home + ' vs ' + m.away + '</div>' +
      '<div class="league">' + m.league + ' &middot; <span style="color:var(--accent)">' + matchTime + '</span></div>' +
      '<div class="meta">' +
        '<div class="bets-count">' + m.valueBets + ' value bets</div>' +
        '<div>Top EV: +' + m.topEV.toFixed(1) + '%</div>' +
      '</div>' +
      '<div style="margin-top:8px;display:flex;justify-content:space-between">' +
        '<div>' + formDots(m.homeForm) + '</div>' +
        '<div>' + formDots(m.awayForm) + '</div>' +
      '</div>';
    ribbon.appendChild(chip);
  }});
}}

function applyFilters() {{
  const market = document.getElementById('filterMarket').value;
  const risk = document.getElementById('filterRisk').value;
  const minConf = parseFloat(document.getElementById('filterConfidence').value) || 0;
  const minEV = parseFloat(document.getElementById('filterEV').value) || 0;
  const league = document.getElementById('filterLeague').value;
  const match = document.getElementById('filterMatch').value;

  filteredBets = ALL_BETS.filter(b => {{
    if (market !== 'all') {{
      const mk = b.marketKey.toLowerCase();
      if (market === 'goals' && !mk.includes('goals_over')) return false;
      if (market === 'corners' && !mk.includes('corners')) return false;
      if (market === 'cards' && !mk.includes('cards')) return false;
      if (market === 'throwins' && !mk.includes('throwins')) return false;
      if (market === 'shots' && !mk.includes('shots')) return false;
      if (market === 'btts' && mk !== 'btts') return false;
      if (market === 'match_result' && mk !== 'match_result') return false;
      if (market === 'first_half' && !mk.includes('first_half')) return false;
    }}
    if (risk !== 'all' && b.risk !== risk) return false;
    if (b.confidence < minConf) return false;
    if (b.ev < minEV) return false;
    if (league !== 'all' && b.league !== league) return false;
    if (match !== 'all' && b.match !== match) return false;
    return true;
  }});

  sortAndRender();
}}

function sortTable(key) {{
  if (currentSort.key === key) {{
    currentSort.asc = !currentSort.asc;
  }} else {{
    currentSort.key = key;
    currentSort.asc = false;
  }}
  sortAndRender();
}}

function sortAndRender() {{
  const key = currentSort.key;
  filteredBets.sort((a, b) => {{
    let va = a[key], vb = b[key];
    if (typeof va === 'string') {{ va = va.toLowerCase(); vb = vb.toLowerCase(); }}
    if (va < vb) return currentSort.asc ? -1 : 1;
    if (va > vb) return currentSort.asc ? 1 : -1;
    return 0;
  }});
  renderTable();
}}

function renderTable() {{
  const tbody = document.getElementById('betsBody');
  tbody.innerHTML = '';

  filteredBets.forEach((bet, idx) => {{
    // Confidence bar color
    let confColor = bet.confidence > 70 ? 'var(--green)' : bet.confidence > 50 ? 'var(--yellow)' : 'var(--red)';
    let riskClass = bet.risk === 'LOW' ? 'badge-low' : bet.risk === 'MEDIUM' ? 'badge-medium' : 'badge-high';

    const tr = document.createElement('tr');
    tr.onclick = () => {{
      const rr = document.getElementById('reason-' + idx);
      if (rr) rr.classList.toggle('visible');
    }};

    tr.innerHTML =
      '<td style="color:var(--accent);font-size:12px;white-space:nowrap">' + formatDate(bet.matchDate) + '</td>' +
      '<td><strong>' + bet.match + '</strong></td>' +
      '<td style="color:var(--text2)">' + bet.league + '</td>' +
      '<td>' + bet.market + '</td>' +
      '<td><strong>' + bet.outcome + '</strong></td>' +
      '<td class="odds-cell">' + bet.odds.toFixed(2) + '</td>' +
      '<td>' +
        '<span class="confidence-bar"><span class="confidence-fill" style="width:' + bet.confidence + '%;background:' + confColor + '"></span></span>' +
        '<strong>' + bet.confidence.toFixed(1) + '%</strong>' +
      '</td>' +
      '<td class="ev-cell positive">+' + bet.ev.toFixed(1) + '%</td>' +
      '<td>' + bet.agreement.toFixed(0) + '%</td>' +
      '<td><span class="badge ' + riskClass + '">' + bet.risk + '</span></td>' +
      '<td class="stake-cell">' + bet.stake.toFixed(2) + '%</td>' +
      '<td class="bookmaker">' + bet.bookmaker + '</td>';
    tbody.appendChild(tr);

    // Reasoning row
    const reasonTr = document.createElement('tr');
    reasonTr.className = 'reasoning-row';
    reasonTr.id = 'reason-' + idx;
    reasonTr.innerHTML = '<td colspan="12"><ul>' +
      bet.reasoning.map(r => '<li>' + r + '</li>').join('') +
      '</ul></td>';
    tbody.appendChild(reasonTr);
  }});
}}

init();
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path
