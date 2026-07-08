"""Base classes for reasoning-only specialist agents (M6 Build Phase F)."""
from __future__ import annotations

from agentic.agents.types import JsonObject, JsonValue


class BaseSpecialistAgent:
    """Reasoning-only agent that can propose runtime-safe actions but cannot execute them."""
    name: str = "base_agent"
    capabilities: list[str] = []
    tools: list[str] = []
    skills: list[str] = []
    cost: float = 1.0
    latency_ms: int = 100
    risk: str = "low"
    confidence: float = 0.8
    tenant_restrictions: list[str] = []
    approval_requirements: list[str] = []
    analysis: str = "Specialist reasoning completed."
    proposals: list[JsonObject] = []

    def reason(self, input_context: JsonObject) -> JsonObject:
        safe_proposals: list[JsonObject] = []
        for proposal in self.proposals:
            runtime_inputs: JsonObject = dict(input_context)
            proposal_inputs: JsonValue = proposal.get("inputs")
            if isinstance(proposal_inputs, dict):
                for key, value in proposal_inputs.items():
                    runtime_inputs[key] = value
            safe_proposals.append(
                {
                    "agent": self.name,
                    "action": str(proposal["action"]),
                    "risk_level": str(proposal.get("risk_level", self.risk)),
                    "inputs": runtime_inputs,
                    "confidence": float(proposal.get("confidence", self.confidence)),
                    "approval_required": bool(proposal.get("approval_required", False)),
                }
            )
        return {
            "agent": self.name,
            "analysis": self.analysis,
            "capabilities": self.capabilities,
            "evidence": [f"{self.name} evaluated mission context without tool execution."],
            "proposals": safe_proposals,
        }
