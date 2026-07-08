"""Base Trigger Interface (Phase 3).

Every autonomous trigger inherits from BaseTrigger and maps a specific
pattern of observation events to a generated Goal.
"""

from __future__ import annotations

import abc
from enterprise_intelligence.observation.models import ObservationEvent
from enterprise_intelligence.knowledge.enterprise_graph import EnterpriseGraph
from enterprise_intelligence.goal_generation.models import AutonomousGoal

__all__ = ["BaseTrigger"]


class BaseTrigger(abc.ABC):
    """Abstract base for autonomous goal-generation triggers."""

    trigger_name: str

    @abc.abstractmethod
    def evaluate(
        self, event: ObservationEvent, graph: EnterpriseGraph
    ) -> AutonomousGoal | None:
        """Evaluate if the event matches the trigger criteria.

        Returns a constructed AutonomousGoal if a goal should be pursued,
        otherwise None.
        """
        ...
