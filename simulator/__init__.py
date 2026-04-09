"""
Football match simulator module.

This module provides comprehensive match simulation capabilities, converting
agent intelligence reports into realistic minute-by-minute match transcripts.
"""

from .match_simulator import (
    MatchSimulator,
    TeamProfile,
    GameState,
    EventType
)
from .calibrated_simulator import CalibratedSimulator

__all__ = [
    "MatchSimulator",
    "CalibratedSimulator",
    "TeamProfile",
    "GameState",
    "EventType"
]
