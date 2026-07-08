"""Collaboration, consensus, arbitration, and load balancing engine (Phase 5).

Provides deterministic conflict resolution rules and routes task proposals
across the 8 domain Intelligences.
"""

from __future__ import annotations

import logging
from typing import Any

from agentic.agents.types import JsonObject
from agentic.agents.specialists.base import BaseSpecialistAgent

__all__ = ["ArbitrationEngine", "ConsensusEngine", "LoadBalancer"]

logger = logging.getLogger(__name__)


class ArbitrationEngine:
    """Deterministic conflict resolution between competing specialist proposals.

    If two Intelligences propose plans that touch the same resource or conflict
    in objective, this engine resolves it using priority, business value,
    and cost, returning the winning proposal accompanied by a clear explanation.
    """

    def arbitrate(
        self, proposals: list[JsonObject], contested_resource: str
    ) -> tuple[JsonObject, str]:
        """Arbitrate between competing proposals for a contested resource.

        Returns (winning_proposal, explanation).
        """
        if not proposals:
            raise ValueError("No proposals to arbitrate.")
        if len(proposals) == 1:
            return proposals[0], "Only one proposal exists; no arbitration needed."

        # Resolution criteria order:
        # 1. Highest priority (e.g. urgent > high > normal)
        # 2. Highest confidence score
        # 3. Lowest cost estimate (most efficient)

        priority_weight = {"urgent": 4, "high": 3, "normal": 2, "low": 1}

        best_proposal = proposals[0]
        explanation = "Defaulted to first proposal."

        for candidate in proposals[1:]:
            # Priority check
            best_p = priority_weight.get(best_proposal.get("risk_level", "normal").lower(), 2)
            cand_p = priority_weight.get(candidate.get("risk_level", "normal").lower(), 2)

            if cand_p > best_p:
                best_proposal = candidate
                explanation = f"Proposal by {candidate.get('agent')} selected due to higher priority level."
                continue
            elif cand_p < best_p:
                continue

            # Confidence check
            best_conf = float(best_proposal.get("confidence", 0.0))
            cand_conf = float(candidate.get("confidence", 0.0))

            if cand_conf > best_conf:
                best_proposal = candidate
                explanation = f"Proposal by {candidate.get('agent')} selected due to higher confidence ({cand_conf} vs {best_conf})."
                continue
            elif cand_conf < best_conf:
                continue

            # Cost check (lower is better)
            best_cost = float(best_proposal.get("cost", 10.0))
            cand_cost = float(candidate.get("cost", 10.0))

            if cand_cost < best_cost:
                best_proposal = candidate
                explanation = f"Proposal by {candidate.get('agent')} selected due to lower execution cost."
                continue

        logger.info(
            "Arbitration completed for resource %s: won by %s. Rationale: %s",
            contested_resource,
            best_proposal.get("agent"),
            explanation,
        )

        return best_proposal, explanation


class ConsensusEngine:
    """Deterministic consensus voting across the Intelligences."""

    def gather_consensus(
        self, intelligences: list[BaseSpecialistAgent], proposal: JsonObject
    ) -> tuple[bool, float]:
        """Ask all intelligences to vote on a proposal.

        Returns (approved, consensus_ratio).
        """
        votes = 0
        for intel in intelligences:
            # Simple voting logic: an intelligence votes yes if its capabilities
            # overlap with the proposal's action, or if confidence is high.
            # Production would query each intelligence's reason method.
            action = proposal.get("action", "")
            if any(cap in action for cap in intel.capabilities) or intel.confidence > 0.85:
                votes += 1

        ratio = votes / len(intelligences) if intelligences else 0.0
        return ratio >= 0.5, ratio


class LoadBalancer:
    """Routes task requests to the most appropriate Intelligence."""

    def route_task(
        self, capability: str, intelligences: list[BaseSpecialistAgent]
    ) -> BaseSpecialistAgent | None:
        """Find the intelligence with matching capability and lowest current load."""
        candidates = [
            intel for intel in intelligences
            if capability in intel.capabilities
        ]

        if not candidates:
            return None

        # Route to candidate with lowest cost/latency combination (highest efficiency)
        return min(candidates, key=lambda c: (c.cost, c.latency_ms))
