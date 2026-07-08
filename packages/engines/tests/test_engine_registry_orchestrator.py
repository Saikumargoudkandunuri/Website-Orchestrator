from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.results import Ok
from engines.shared.audit_job_repository import AuditJobStatus
from engines.shared.engine_contract import (
    AnalysisTarget,
    EngineAnalysisRequest,
    EngineAnalysisResult,
    PageTarget,
)
from engines.shared.engine_orchestrator import EngineOrchestrator
from engines.shared.engine_registry import default_engine_registry


def test_default_engine_registry_contains_all_milestone_3_engines() -> None:
    registry = default_engine_registry()

    assert registry.names() == [
        "backlink_intelligence",
        "competitor_intelligence",
        "content_intelligence",
        "keyword_intelligence",
        "opportunity",
        "recommendation",
        "seo_scoring",
        "site_architecture",
        "technical_seo",
        "topical_authority",
    ]


def test_orchestrator_threads_tier_outputs_through_dependency_chain() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    registry = _FakeRegistry({
        name: _FakeEngine(name, calls)
        for name in ("technical_seo", "seo_scoring", "opportunity", "recommendation")
    })
    container = _FakeContainer(registry)
    orchestrator = EngineOrchestrator(container, max_workers=1)

    result = orchestrator.run_audit(
        "site-a",
        target=PageTarget(site_id="site-a", page_id="page-a"),
        capabilities=["technical_seo", "seo_scoring", "opportunity", "recommendation"],
    )

    assert result.status == AuditJobStatus.COMPLETED
    assert result.completed == [
        "technical_seo",
        "seo_scoring",
        "opportunity",
        "recommendation",
    ]
    assert [name for name, _ in calls] == result.completed
    assert calls[1][1]["_technical_audit"].engine_name == "technical_seo"
    assert calls[2][1]["_technical_audits"]["page-a"]["engine"] == "technical_seo"
    assert calls[3][1]["_opportunity_report"]["engine"] == "opportunity"


class _FakeEngine:
    engine_version = "test"

    def __init__(self, engine_name: str, calls: list[tuple[str, dict[str, Any]]]) -> None:
        self.engine_name = engine_name
        self._calls = calls

    def supports(self, target: AnalysisTarget) -> bool:
        return True

    def analyze(self, request: EngineAnalysisRequest):
        self._calls.append((self.engine_name, dict(request.options)))
        return Ok(EngineAnalysisResult(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            target=request.target,
            output={"engine": self.engine_name},
        ))


class _FakeRegistry:
    def __init__(self, engines: dict[str, _FakeEngine]) -> None:
        self._engines = engines

    def get(self, name: str) -> _FakeEngine:
        return self._engines[name]


@dataclass
class _FakeJob:
    id: str = "job-a"


class _FakeAuditJobRepository:
    def create(self, tenant_id: str, site_id: str, requested: list[str]) -> _FakeJob:
        return _FakeJob()

    def mark_running(self, tenant_id: str, job_id: str) -> None:
        return None

    def mark_engine_complete(self, tenant_id: str, job_id: str, engine_name: str) -> None:
        return None

    def mark_engine_failed(self, tenant_id: str, job_id: str, engine_name: str) -> None:
        return None

    def mark_finished(self, tenant_id: str, job_id: str, summary: dict[str, Any]) -> None:
        return None


class _RecorderRepo:
    def save(self, *args: Any, **kwargs: Any) -> None:
        return None


@dataclass
class _FakeContainer:
    engine_registry: _FakeRegistry
    tenant_id: str = "tenant-test"
    audit_job_repo: _FakeAuditJobRepository = field(default_factory=_FakeAuditJobRepository)
    technical_seo_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    site_arch_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    keyword_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    content_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    competitor_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    backlink_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    topical_authority_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    seo_score_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    opportunity_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
    recommendation_repo: _RecorderRepo = field(default_factory=_RecorderRepo)
