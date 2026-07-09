"""Central AIManager: single entrypoint for all engines."""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Any, Optional

from .router import select_provider
from .registry import get_registry
from .schemas import ChatRequest, ChatResponse, GenerateRequest, GenerateResponse, EmbedRequest, EmbedResponse, TokenUsage
from .telemetry import build_log, emit_log
from .usage import get_usage
from . import config
from fastapi import APIRouter, HTTPException


# FastAPI router to expose provider settings/health endpoints. Engines may mount this
# router into their application if desired.
router = APIRouter(prefix="/ai", tags=["ai"])


def _mask_key(k: str | None) -> str:
	if not k:
		return ""
	if len(k) < 10:
		return "****"
	return k[:4] + "..." + k[-4:]


@router.get("/providers")
async def list_providers():
	registry = get_registry()
	providers = []
	# report all known provider keys
	for name in list(config.PROVIDER_KEYS.keys()) + ["ollama", "lmstudio"]:
		enabled = config.is_provider_enabled(name)
		inst = registry.get(name) if registry else None
		status = "disabled"
		if inst is not None:
			try:
				status = await inst.health()
			except Exception:
				status = "unavailable"
		providers.append(
			{
				"name": name,
				"status": status,
				"enabled": enabled,
				"api_key": _mask_key(config.PROVIDER_KEYS.get(name)),
				"usage": get_usage(name).snapshot() if inst is not None else {},
			}
		)
	return {"providers": providers}


@router.post("/providers/{provider}/test")
async def test_provider(provider: str):
	registry = get_registry()
	inst = registry.get(provider.lower())
	if inst is None:
		raise HTTPException(status_code=404, detail="Provider not found or disabled")
	try:
		status = await inst.health()
	except Exception as exc:
		raise HTTPException(status_code=500, detail=str(exc))
	return {"provider": provider, "status": status}


class AIManager:
	def __init__(self) -> None:
		# lazy registry
		self._registry = get_registry()

	async def _call_provider(self, method: str, *args, **kwargs):
		attempts = 0
		last_exc: Exception | None = None
		while attempts < config.AI_MAX_RETRIES:
			attempts += 1
			try:
				name, provider = await select_provider()
				start = time.time()
				coro = getattr(provider, method)(*args, **kwargs)
				result = await asyncio.wait_for(coro, timeout=config.AI_REQUEST_TIMEOUT_SECONDS)
				elapsed_ms = int((time.time() - start) * 1000)
				# record usage (best-effort)
				try:
					usage = get_usage(name)
					# approximate tokens
					usage.record(0, 0, Decimal("0"), elapsed_ms, error=False)
				except Exception:
					pass
				# telemetry
				emit_log(build_log(provider=name, method=method, latency_ms=elapsed_ms, status="success", retries=attempts - 1))
				return result
			except Exception as exc:
				last_exc = exc
				emit_log(build_log(provider="unknown", method=method, status="error", error=str(exc), retries=attempts))
				# fallback to next provider if enabled
				if not config.AI_FALLBACK_ENABLED:
					raise
				await asyncio.sleep(0.1)
				continue
		# all retries exhausted
		if last_exc:
			raise last_exc
		raise RuntimeError("AI call failed")

	async def generate(self, prompt: str, model: Optional[str] = None) -> GenerateResponse:
		req = GenerateRequest(prompt=prompt, model=model or config.AI_DEFAULT_MODEL)
		return await self._call_provider("generate", req)

	async def chat(self, messages: list[dict], model: Optional[str] = None) -> ChatResponse:
		req = ChatRequest(messages=messages, model=model or config.AI_DEFAULT_MODEL)
		return await self._call_provider("chat", req)

	async def embed(self, texts: list[str], model: Optional[str] = None) -> EmbedResponse:
		req = EmbedRequest(input=texts, model=model or config.AI_DEFAULT_MODEL)
		return await self._call_provider("embedding", req)

	async def classify(self, text: str, labels: list[str]) -> Any:
		# lightweight classification via chat/generation
		prompt = f"Classify the following labels {labels} for text: {text}"
		gen = await self.generate(prompt)
		return gen

	async def summarize(self, text: str, max_tokens: int = 200) -> Any:
		prompt = f"Summarize: {text}\n\nTl;dr:" 
		gen = await self.generate(prompt)
		return gen
