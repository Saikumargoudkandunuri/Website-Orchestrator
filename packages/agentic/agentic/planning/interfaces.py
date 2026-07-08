"""Interfaces for the planning subsystem (M6 Build Phase B)."""
from __future__ import annotations

from typing import Protocol

from agentic.goal.models import Goal
from agentic.planning.models import (
    DecisionAlternative,
    ExecutionGraph,
    Plan,
)
from agentic.tools.selector import ExecutionPolicy


class PlannerService(Protocol):
    """Protocol for the Planner component."""
    
    def plan(self, goal: Goal, policy: ExecutionPolicy | None = None) -> Plan:
        """Create a plan for achieving the given Goal."""
        ...


class ReasonerService(Protocol):
    """Protocol for the Reasoner component."""
    
    def score_plan(self, plan: Plan) -> dict[str, float]:
        """Score a plan across multiple dimensions."""
        ...


class CriticService(Protocol):
    """Protocol for the Critic component."""
    
    def critique_plan(self, plan: Plan) -> list[str]:
        """Examine a plan to identify inefficiencies or conflicts."""
        ...


class RiskAnalyzerService(Protocol):
    """Protocol for the Risk Analyzer component."""
    
    def analyze_risk(self, plan: Plan) -> dict[str, Any]:
        """Estimate execution, SEO, and business risks with explanations."""
        ...


class SimulationEngineService(Protocol):
    """Protocol for the Simulation Engine component."""
    
    def simulate_outcomes(self, plan: Plan) -> dict[str, Any]:
        """Simulate expected traffic, rank gains, and resource timelines."""
        ...
