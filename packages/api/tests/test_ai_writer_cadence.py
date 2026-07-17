"""Milestone 5 — Automatic Blog Writer weekly cadence.

The blog cadence gate lives on ``AiWriterAgent`` and reads the real, governed
``published_blogs`` history from CMO memory (no new/duplicate scheduler state).
These tests drive the gate directly against constructed memory documents, and
the full ``analyze()`` path against a fake tool registry/context to prove a
due-but-already-satisfied cadence proposes no new blog action.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.agent_specialists import AiWriterAgent
from api.agent_tools import AgentContext, ToolRegistry, ToolSpec


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_blog_is_due_true_when_never_published() -> None:
    agent = AiWriterAgent()
    due, next_due_at, last_at = agent._blog_is_due({"published_blogs": []})
    assert due is True
    assert last_at is None


def test_blog_is_due_false_within_default_cadence_window() -> None:
    agent = AiWriterAgent()
    recent = _iso(datetime.now(timezone.utc) - timedelta(days=2))
    due, next_due_at, last_at = agent._blog_is_due({"published_blogs": [{"published_at": recent}]})
    assert due is False
    assert last_at == recent


def test_blog_is_due_true_after_default_cadence_window() -> None:
    agent = AiWriterAgent()
    old = _iso(datetime.now(timezone.utc) - timedelta(days=8))
    due, next_due_at, last_at = agent._blog_is_due({"published_blogs": [{"published_at": old}]})
    assert due is True


def test_blog_is_due_respects_configured_cadence_days() -> None:
    agent = AiWriterAgent()
    recent = _iso(datetime.now(timezone.utc) - timedelta(days=3))
    memory = {
        "published_blogs": [{"published_at": recent}],
        "executive_cmo_schedule": {"weekly_blog_cadence_days": 2},
    }
    due, _, _ = agent._blog_is_due(memory)
    assert due is True  # 3 days elapsed > configured 2-day cadence


def test_analyze_skips_generation_when_cadence_not_due(monkeypatch) -> None:
    agent = AiWriterAgent()
    recent = _iso(datetime.now(timezone.utc) - timedelta(days=1))

    class _FakeCtx:
        domain = "example.com"

        def cmo_memory(self) -> dict:
            return {"published_blogs": [{"published_at": recent}]}

    called = {"generate": False}

    def _handler(ctx, **kwargs):
        called["generate"] = True
        return {"generated": True}

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="ai_writer_generate", capability="content.ai_writer.generate",
        description="", handler=_handler,
    ))

    report = agent.analyze(_FakeCtx(), registry)

    assert called["generate"] is False
    assert report["actions"] == []
    assert report["meta"]["cadence_gated"] is True


def test_analyze_generates_when_cadence_due() -> None:
    agent = AiWriterAgent()

    class _FakeCtx:
        domain = "example.com"

        def cmo_memory(self) -> dict:
            return {"published_blogs": []}

    def _handler(ctx, **kwargs):
        return {
            "generated": True, "title": "Best Practices", "meta_title": "Best Practices 2026",
            "focus_keyphrase": "best practices", "page_url": "https://example.com/",
            "html": "<h1>Best Practices</h1>", "warnings": [], "seo_meta": {},
        }

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="ai_writer_generate", capability="content.ai_writer.generate",
        description="", handler=_handler,
    ))

    report = agent.analyze(_FakeCtx(), registry)

    assert report["meta"]["generated"] is True
    action_types = {a["type"] for a in report["actions"]}
    assert "publish_ai_draft" in action_types
    assert "publish_ai_draft_seo_meta" in action_types
    blog_action = next(a for a in report["actions"] if a["type"] == "publish_ai_draft")
    assert blog_action["asset_type"] == "blog_post"
