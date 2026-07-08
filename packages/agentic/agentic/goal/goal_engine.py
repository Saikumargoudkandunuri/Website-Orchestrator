"""Goal Engine (M6 Build Phase A)."""
from __future__ import annotations

import json
from typing import Any

from agentic.goal.models import (
    Goal,
    GoalContext,
    StructuredObjective,
)
from core.results import Err, Ok, Result

# We rely on Intelligence's provider interface for the LLM call.
from intelligence.ai.provider_interface import (
    AICompletionRequest,
    AIProvider,
)


class GoalEngine:
    """Parses raw text objectives into structured Goal models using AI."""
    
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider
        
    def parse(self, raw_objective: str, context: GoalContext) -> Result[Goal, str]:
        """Parse a free-text objective into a typed Goal."""
        
        system_prompt = (
            "You are an expert SEO and Growth strategy AI. Your job is to convert "
            "a free-text human objective into a strictly typed JSON object "
            "representing a structured objective. Do NOT guess if it is entirely ambiguous."
        )
        
        user_prompt = f"""
        Objective: {raw_objective}
        Context: tenant={context.tenant_id}
        
        Output JSON matching this schema:
        {{
            "target_metric": "string (e.g. organic_traffic, conversions)",
            "magnitude": "number or string (e.g. 25, 'double')",
            "timeframe_days": "integer or null",
            "target_site_id": "string or null",
            "target_page_set": ["list of strings"]
        }}
        """
        
        request = AICompletionRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=True,
            metadata={"capability": "goal_parsing"},
        )
        
        provider_result = self._provider.complete(request)
        if isinstance(provider_result, Err):
            return Err(f"AI provider failed: {provider_result.error}")
            
        try:
            parsed = json.loads(provider_result.value.raw_text)
            structured = StructuredObjective(**parsed)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return Err(f"Failed to parse or validate structured objective: {e}")
            
        goal = Goal(
            raw_objective=raw_objective,
            structured_objective=structured,
            context=context,
        )
        return Ok(goal)
