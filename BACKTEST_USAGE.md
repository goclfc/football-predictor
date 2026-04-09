# Football Prediction System V5 - Backtest Script Usage Guide

## Overview

`backtest_simulation.py` is a comprehensive backtest framework that:
- Fetches recently finished matches from API-Sports v3
- Runs the V5 prediction engine (analyze_match + simulate_match) on each match
- Compares predictions vs actual results across all markets
- Generates detailed accuracy, calibration, and market analysis

## Quick Start

### Run the backtest:
```bash
cd /sessions/intelligent-sleepy-bell/mnt/predictions/football_predictor
python backtest_simulation.py
```

### Expected output:
- Console summary with league-by-league accuracy, market breakdown, calibration curves
- `backtest_results.json` - detailed match-by-match results
- `BACKTEST_REPORT.md` - comprehensive analysis document

## Script Structure

### Configuration (lines 45-64)
```python
API_KEY = "480b0d1da4cd81135649f1a77eb6465c"
LEAGUES = {"La Liga": 140, "Premier League": 39, ...}
SEASON = 2024
MAX_MATCHES_PER_LEAGUE = 10
MAX_TOTAL_MATCHES = 50
```

Adjust these to control which leagues, how many matches, and API credentials.

### Data Flow

1. **Fetch Data** (`get_finished_matches` + `get_match_statistics`)
   - Calls API-Sports to get last N finished matches per league
   - Retrieves match stats (corners, cards, shots, etc.)

2. **Prediction** (`run_prediction_engine`)
   - Calls `engine.analyze_match()` → 27 agents produce predictions
   - Calls `engine.simulate_match()` → Monte Carlo simulation (200 sims)
   - Returns calibrated probabilities, expected goals, value bets

3. **Comparison** (`backtest_match`)
   - Extracts predicted result (highest probability outcome)
   - Extracts actual result from API
   - Records predicted vs actual for analysis

4. **Analysis** (`analyze_results`)
   - Computes overall accuracy and by-league breakdown
   - Generates calibration curves (confidence bands)
   - Evaluates market-level accuracy (O/U 2.5, BTTS, Corners, Cards)
   - Calculates value bet ROI (if applicable)
   - Identifies strengths and weaknesses

5. **Output** (`print_summary` + `save_results`)
   - Prints formatted console summary
   - Saves detailed JSON for further analysis

## Key Classes and Functions

### `Match` Dataclass (lines 107-130)
Represents a single match with predictions and actual results.

**Key fields:**
- `actual_score`: {home: int, away: int}
- `predicted_probs`: {home_win, draw, away_win}
- `expected_goals`: {home, away, total}
- `actual_stats`: {corners, cards, shots, ...}
- `correct_prediction`: bool
- `calibration_band`: "50-60%", "60-70%", etc.

### `BacktestResults` Dataclass (lines 133-157)
Aggregated results across all matches.

**Key fields:**
- `league_accuracy`: {league: {accuracy, correct, total}}
- `calibration`: {band: {predicted%, actual%, count}}
- `market_accuracy`: {market: {accuracy, correct, total}}
- `value_bet_results`: {roi%, win_rate, total_bets}
- `strengths`: [list of positive findings]
- `weaknesses`: [list of negative findings]

### API Functions

**`get_finished_matches(league_id, league_name)`**
- Fetches last 20 finished matches from a league
- Returns list of fixture dicts with scores

**`get_match_statistics(fixture_id)`**
- Fetches detailed match stats (corners, cards, shots)
- Returns dict with aggregated totals

### Prediction Functions

**`run_prediction_engine(match_data, engine)`**
- Calls engine.analyze_match() + simulate_match()
- Returns (analysis_dict, simulation_dict)

**`construct_match_data(fixture)`**
- Converts API-Sports fixture format to engine format
- Extracts team names, league, date, etc.

### Analysis Functions

**`extract_prediction_result(probs)`**
- Returns (predicted_result, confidence)
- predicted_result: "Home", "Draw", or "Away"
- confidence: highest probability value

**`analyze_results(matches)`**
- Main analysis function
- Computes all accuracy, calibration, market metrics
- Returns BacktestResults dataclass

## Customization

### Changing test parameters:

```python
# Test only Ligue 1:
LEAGUES = {"Ligue 1": 61}

# Test more matches:
MAX_MATCHES_PER_LEAGUE = 20
MAX_TOTAL_MATCHES = 100

# Use different season:
SEASON = 2023
```

### Adding markets to track:

Edit the `analyze_results()` function to add new markets. Example for adding "Over 1.5" goals:

```python
# In analyze_results(), add:
o15_correct = 0
o15_total = 0

for match in matches:
    actual_goals = match.actual_score.get("home", 0) + match.actual_score.get("away", 0)
    pred_o15 = match.mc_probabilities.get("over15", 0.5)
    actual_o15 = 1 if actual_goals > 1.5 else 0
    pred_o15_result = 1 if pred_o15 > 0.5 else 0
    if pred_o15_result == actual_o15:
        o15_correct += 1
    o15_total += 1

results.market_accuracy["over_under_1_5"] = {
    "accuracy": o15_correct / o15_total if o15_total > 0 else 0,
    "correct": o15_correct,
    "total": o15_total,
}
```

### Integrating real form/stats data:

Replace the `make_demo_form()` and `make_demo_stats()` calls in `run_prediction_engine()`:

```python
# Current (demo data):
home_form = make_demo_form(goals_for=1.4, goals_against=0.8)

# Replace with real data:
home_team_id = match_data["home_id"]
home_form = fetch_real_form_from_api(home_team_id, league_id, season)
```

### Adding real bookmaker odds:

To enable value bet detection, pass actual odds to the simulator:

```python
# In run_prediction_engine():
# Get odds from BetFair/Betsson/etc API
odds = {
    "home_win": 2.50,
    "draw": 3.40,
    "away_win": 3.10,
}

simulation = engine.simulate_match(
    ...,
    bookmaker_odds=odds,  # If simulator supports this parameter
)
```

## Output Files

### `backtest_results.json`
Full match-by-match results. Structure:

```json
{
  "timestamp": "2026-04-04T14:13:37...",
  "summary": {
    "total_matches": 50,
    "overall_accuracy": 0.34,
    "league_accuracy": {...},
    "calibration": {...},
    "market_accuracy": {...},
    "value_bet_results": {...}
  },
  "matches": [
    {
      "fixture_id": 1208827,
      "home_team": "Athletic Club",
      "away_team": "Barcelona",
      "predicted_result": "Home",
      "actual_result": "Away",
      "correct": false,
      "confidence": 0.45,
      ...
    }
  ]
}
```

### `BACKTEST_REPORT.md`
Executive summary with:
- Overall performance metrics
- League-by-league breakdown
- Market-level accuracy comparison
- Calibration analysis
- Strengths/weaknesses
- Production recommendations

### `BACKTEST_SUMMARY.txt`
Quick reference guide with key metrics and technical details.

## Troubleshooting

### No matches fetched
- Check API key is valid
- Verify league IDs are correct
- Ensure the season has finished matches

### Engine errors
- Check that all agent modules are imported correctly
- Verify demo form/stats functions return valid dicts
- Check engine_v4.py is not corrupted

### Zero value bets
- Backtest uses demo data, so calibration may be off
- Value bet detection requires real bookmaker odds
- The simulator might be too conservative in filtering

### Poor calibration
- Low sample size (50 matches) is not statistically significant
- Demo data doesn't match real match dynamics
- Integrate real form/xG data for better calibration

## Performance Considerations

- **Execution time:** ~3-5 minutes for 50 matches (depends on API latency)
- **Memory:** Minimal (~100MB for 50 matches)
- **API calls:** ~200-250 per backtest (1 for fixtures, 1-2 per match for stats)

To speed up:
- Reduce `MAX_MATCHES_PER_LEAGUE`
- Cache API responses locally
- Run on multiple machines in parallel

## Next Steps

1. **Validate with real data:** Integrate StatsBomb/Understat xG data
2. **Add bookmaker odds:** Connect to BetFair/Betsson APIs
3. **Extend backtest:** Run on 300+ matches with walk-forward validation
4. **Monitor live:** Implement real-time dashboard with ongoing ROI tracking

## References

- Engine documentation: `engine_v4.py` (v5_analysis, v4_analysis structures)
- Agent system: 27 agents in `agents/` directory
- Match simulator: `simulator/calibrated_simulator.py`
- V5 predictor: `backtester_v5.py` (data-mined pattern detection)

---

For questions or improvements, refer to the main engine documentation and agent implementations.
