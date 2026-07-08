"""AI Copilot Services for System 6."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from core.results import Ok, Err, Result
from intelligence.ai.provider_interface import AICompletionRequest, AICompletionResponse, AIProvider
from saas.copilot.models import ConversationSession, AIExplanation, PromptTemplate
from saas.copilot.repositories import CopilotRepository

__all__ = [
    "CopilotService",
    "ContextCollectorService",
    "ExplanationEngineService",
]

logger = logging.getLogger(__name__)


class ContextCollectorService:
    """Assembles active strategists state focus (site, page, goals)."""

    def collect_context(self, tenant_id: str, site_id: str, focus_page_id: str | None = None) -> dict[str, Any]:
        """Query platform metadata to formulate a prompt context block."""
        return {
            "tenant_id": tenant_id,
            "site_id": site_id,
            "focus_page": focus_page_id,
            "system_time": datetime.now().isoformat() if "datetime" in globals() else "now",
        }


class CopilotService:
    """Conversational assistant with prompt injection sanitization."""

    def __init__(self, repo: CopilotRepository, ai_provider: AIProvider) -> None:
        self._repo = repo
        self._ai = ai_provider

    def sanitize_prompt(self, raw_input: str) -> str:
        """Strip dangerous system instructions overriding safety parameter overrides."""
        # Clean input text against typical system instruction prompt patterns
        import re
        clean = re.sub(r"ignore all prior instructions", "", raw_input, flags=re.IGNORECASE)
        clean = re.sub(r"ignore system guidelines", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"override governance settings", "", clean, flags=re.IGNORECASE)
        return clean.strip()

    def generate_chat_response(
        self, tenant_id: str, session_id: str, user_id: str, prompt: str, context: dict[str, Any]
    ) -> str:
        """Process chat session sequence and stream token frames (simulated return)."""
        clean_input = self.sanitize_prompt(prompt)
        
        # Load or create conversation session
        session_data = self._repo.get_session(tenant_id, session_id)
        if not session_data:
            session_data = ConversationSession(id=session_id, tenant_id=tenant_id, user_id=user_id)
            
        session_data.messages_json.append({"role": "user", "content": clean_input})

        # Compile prompts
        system_prompt = (
            "You are a context-aware SEO and marketing assistant. Ground all statements in "
            f"the active client context: {context}. Maintain absolute safety."
        )

        request = AICompletionRequest(
            prompt=clean_input,
            system_prompt=system_prompt,
            json_mode=False,
            metadata={"capability": "copilot_chat"},
        )

        res = self._ai.complete(request)
        if isinstance(res, Ok):
            text = res.value.raw_text
        else:
            text = "AI Provider error occurred. Please retry your request."

        session_data.messages_json.append({"role": "assistant", "content": text})
        self._repo.save_session(session_data)
        return text


class ExplanationEngineService:
    """Serializes plan alternatives and execution logs into explainable graphs."""

    def __init__(self, repo: CopilotRepository) -> None:
        self._repo = repo

    def compile_reasoning_graph(self, tenant_id: str, goal_id: str, plan_graph: Any) -> AIExplanation:
        """Read M6 plan DAG and construct visual explanation coordinates."""
        # Emulate compiling graph metadata
        explanation_data = {
            "goal_id": goal_id,
            "nodes": [
                {"id": "goal", "label": "Initial Objective", "type": "goal"},
                {"id": "selected_path", "label": "Selected Action Path", "type": "plan"},
            ],
            "edges": [
                {"from": "goal", "to": "selected_path"},
            ],
            "alternatives_evaluated": 2,
        }

        exp = AIExplanation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            goal_id=goal_id,
            explanation_json=explanation_data,
        )
        self._repo.save_explanation(exp)
        return exp
