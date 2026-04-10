"""
MAC-ADG System Data Schemas.
Defines core data structures and FSM result classes for the orchestrator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class FSMState(Enum):
    """Finite-state machine stages for the orchestrator."""

    PRE_FLIGHT = "PRE_FLIGHT"
    SCOUTING = "SCOUTING"
    PERCEPTION = "PERCEPTION"
    ARBITRATION = "ARBITRATION"
    EVOLUTION = "EVOLUTION"
    TERMINATION = "TERMINATION"


class DuplicateStrategy(Enum):
    """Duplicate DOI handling strategy (config-driven)."""

    SKIP = "SKIP"
    OVERWRITE = "OVERWRITE"
    PROMPT = "PROMPT"


@dataclass
class AgentResult:
    """Standardized agent execution result payload."""

    success: bool
    confidence: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)
    error_msg: Optional[str] = None
    source: str = "unknown"
