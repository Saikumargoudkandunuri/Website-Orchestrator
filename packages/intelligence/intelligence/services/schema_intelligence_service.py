"""Schema intelligence (§4.9). Observed existing markup + proposed AI JSON-LD.

Generated JSON-LD only reaches ``generated_jsonld`` after passing the
``schema_generator`` validation chain (which includes ``schema_org_validator``),
so invalid structured data is never persisted.
"""

from __future__ import annotations

from intelligence.identifiers import element_id_for
from intelligence.models.schema_intelligence import (
    RecommendedSchema,
    SchemaBlock,
    SchemaIntelligenceSection,
    SchemaValidationStatus,
)
from intelligence.services.base import AnalysisContext, AnalyzerService

__all__ = ["SchemaIntelligenceService"]


class SchemaIntelligenceService(AnalyzerService):
    section = "schema_intelligence"

    def analyze(self, ctx: AnalysisContext) -> None:
        section = SchemaIntelligenceSection()
        # Observed: Milestone 1's crawler records only presence (has_schema); the
        # parsed JSON-LD blocks are not captured, so existing_schema stays empty
        # and presence is reflected via has_schema on the crawl. (Documented gap.)

        if ctx.runner is not None:
            ctx.prompt_context.existing_schema_types = []
            result = ctx.runner.run(
                "schema_generator", ctx.prompt_context, page_id=ctx.page_id
            )
            ctx.warnings.extend(result.warnings)
            payload = result.payload
            if payload:
                schema_type = payload.get("type")
                jsonld = payload.get("jsonld")
                if schema_type and jsonld:
                    section.generated_jsonld = [
                        SchemaBlock(
                            type=schema_type,
                            raw_jsonld=jsonld,
                            element_id=element_id_for(ctx.page_id, "schema", schema_type),
                        )
                    ]
                    section.validation_status = SchemaValidationStatus.VALID
                    section.selected_schema_type = schema_type
                    section.recommended_schema = [
                        RecommendedSchema(
                            type=schema_type,
                            reasoning=payload.get("reasoning"),
                            priority=1,
                        )
                    ]
                    if not ctx.page.has_schema:
                        section.missing_schema_types = [schema_type]

        ctx.ko.schema_intelligence = section
