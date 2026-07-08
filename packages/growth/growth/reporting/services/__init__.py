"""Reporting services."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from core.results import Err, Ok, Result
from growth.errors import GrowthGenerationError
from growth.reporting.models import BrandingConfig, ReportArtifact, ReportDefinition, ReportFormat
from growth.shared.jobs.job_queue_interface import JobDefinition, JobQueue
from intelligence.ai.provider_interface import AICompletionRequest, AIProvider

if TYPE_CHECKING:
    from growth.reporting.repositories import ReportingRepository

__all__ = ["ReportingService", "ReportRenderer"]


class ReportRenderer(Protocol):
    def render(self, data: dict, branding: BrandingConfig) -> bytes: ...


class PdfReportRenderer:
    def render(self, data: dict, branding: BrandingConfig) -> bytes:
        return ("Website Orchestrator PDF report\n" + str(data)).encode("utf-8")


class CsvReportRenderer:
    def render(self, data: dict, branding: BrandingConfig) -> bytes:
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for key, value in data.items():
            writer.writerow([key, str(value)])
        return output.getvalue().encode("utf-8")


class ExcelReportRenderer:
    def render(self, data: dict, branding: BrandingConfig) -> bytes:
        return ("Worksheet: Website Orchestrator Report\n" + str(data)).encode("utf-8")


class JsonReportRenderer:
    def render(self, data: dict, branding: BrandingConfig) -> bytes:
        import json
        return json.dumps(data, indent=2, default=str).encode("utf-8")


class ReportingService:
    """Synthesize persisted engine outputs into report artifacts."""

    def __init__(
        self,
        repository: "ReportingRepository",
        job_queue: JobQueue,
        ai_provider: AIProvider,
    ) -> None:
        self._repo = repository
        self._job_queue = job_queue
        self._ai = ai_provider
        self._renderers: dict[str, ReportRenderer] = {
            ReportFormat.PDF: PdfReportRenderer(),
            ReportFormat.CSV: CsvReportRenderer(),
            ReportFormat.EXCEL: ExcelReportRenderer(),
            ReportFormat.JSON: JsonReportRenderer(),
        }

    def generate_report(
        self,
        definition: ReportDefinition,
        branding: BrandingConfig,
        *,
        site_id: str = "default",
        organization_id: str | None = None,
        client_id: str | None = None,
    ) -> Result[ReportArtifact, GrowthGenerationError]:
        start_time = datetime.now(timezone.utc)
        data = self._assemble_report_data(definition)
        data["ai_summary"] = self._generate_narrative(definition.report_type, data)

        renderer = self._renderers.get(definition.format)
        if renderer is None:
            return Err(GrowthGenerationError(f"Unsupported format: {definition.format}"))
        content_bytes = renderer.render(data, branding)

        completeness = self._compute_data_completeness(data)
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        artifact = ReportArtifact(
            id=f"artifact-{definition.id}-{int(start_time.timestamp())}",
            report_definition_ref=definition.id,
            format=definition.format,
            storage_ref=f"reports/{definition.id}/{start_time.isoformat()}.{definition.format}",
            generated_at=start_time,
            data_completeness_summary=completeness,
            file_size_bytes=len(content_bytes),
            generation_duration_ms=duration_ms,
        )
        saved = self._repo.save_artifact(
            artifact,
            org_id=organization_id,
            client_id=client_id,
            site_id=site_id,
        )
        if saved.is_err:
            return Err(GrowthGenerationError(str(saved.unwrap_err())))
        return Ok(saved.unwrap())

    def schedule_report(self, definition: ReportDefinition) -> Result[str, GrowthGenerationError]:
        if not definition.schedule:
            return Err(GrowthGenerationError("Report definition has no schedule"))
        job = JobDefinition(
            job_id=f"scheduled-report-{definition.id}",
            job_type="scheduled_report_generation",
            payload={"report_definition_id": definition.id},
        )
        return Ok(self._job_queue.schedule(job, definition.schedule))

    def _assemble_report_data(self, definition: ReportDefinition) -> dict:
        sections = {engine_name: {"status": "referenced"} for engine_name in definition.source_engine_refs}
        return {
            "report_type": definition.report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections,
        }

    def _generate_narrative(self, report_type: str, data: dict) -> str:
        request = AICompletionRequest(
            prompt=f"Generate a concise executive summary for this {report_type} report.\n\nData:\n{data}",
            max_tokens=500,
            temperature=0.2,
            metadata={"capability": "analytics_summary", "prompt_version": "1.0.0"},
        )
        result = self._ai.complete(request)
        if result.is_ok:
            return result.unwrap().raw_text.strip() or "Report summary unavailable."
        return "Report summary unavailable."

    def _compute_data_completeness(self, data: dict) -> dict:
        sections = data.get("sections", {})
        return {
            "overall_completeness": 1.0,
            "data_sources": sorted(sections.keys()),
            "section_count": len(sections),
        }