"""
Base Agent class — all specialized agents inherit from this.
Each agent analyzes data from its perspective and returns confidence-weighted predictions.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class AgentPrediction:
    """A single prediction from an agent for a specific market."""
    market: str          # e.g., "corners_over_under_9.5"
    outcome: str         # e.g., "Over 9.5"
    probability: float   # Agent's estimated true probability (0-1)
    confidence: float    # How confident the agent is in its estimate (0-1)
    reasoning: str       # Why this prediction
    data_points: List[str] = field(default_factory=list)  # Supporting evidence


@dataclass
class AgentReport:
    """Full report from an agent for one match."""
    agent_name: str
    match_id: str
    home_team: str
    away_team: str
    predictions: List[AgentPrediction]
    overall_assessment: str
    reliability_score: float  # Self-assessed reliability (0-1)


class BaseAgent:
    """Base class for all analysis agents."""

    name: str = "BaseAgent"
    specialty: str = "General"
    weight: float = 1.0  # How much weight the meta-agent gives this agent

    def analyze(self, match_data: Dict, home_form: Dict, away_form: Dict,
                h2h: Dict, home_stats: Dict, away_stats: Dict, **kwargs) -> AgentReport:
        """Analyze a match and return predictions. Override in subclasses."""
        raise NotImplementedError

    def _clamp(self, value: float, low: float = 0.01, high: float = 0.99) -> float:
        return max(low, min(high, value))
