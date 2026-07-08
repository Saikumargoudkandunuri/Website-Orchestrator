# Milestone 2 (+ 2.1) — SEO Intelligence Layer

Milestone 2 adds a **persistent, versioned per-page "SEO Knowledge Object"**, a
provider-agnostic AI layer, a reusable prompt/validation pipeline, analyzer
services + orchestrator, an additive REST surface, and Milestone-1-style fix
generators. Milestone 2.1 (Rank Math parity) is folded in additively.

It is **strictly additive**: a new `packages/intelligence` package
(`wo-intelligence`) depends on `wo-core` (and reads Milestone 1 typed records);
nothing in Milestone 0/1 depends on it. Baseline before this work: `431 passed`;
after: the full suite stays green with 157 new intelligence tests added and zero
Milestone 1 test modifications.

---

## Where it lives (monorepo mapping)

The spec's `/app/intelligence/` maps onto this uv monorepo as
`packages/intelligence/intelligence/`:

```
intelligence/
  models/            # 9 sections + KnowledgeObject + AIInvocation (schema-first)
  ai/                # AIProvider interface, 6 providers + fake, factory, parser, prompt_registry
  prompts/           # BasePromptTemplate + 14 capability templates
  validation/        # 8 validators + pipeline + immutability enforcement
  repositories/      # append-only versioned persistence (own SQLAlchemy Base)
  services/          # 8 analyzers + content score + analysis_orchestrator
  fixes/             # meta/title/slug/schema fix generators (reuse M1 SuggestedFix)
  api/               # additive FastAPI router + DTOs + DI wiring
  errors.py, identifiers.py, field_paths.py
tests/               # 157 tests, zero real network/AI calls
```

The intelligence router is mounted additively by `packages/api/api/app.py`
(`create_app(..., intelligence=...)`), alongside — never replacing — Milestone
1's routes.

---

## Observation / Inference / Proposal (§1.3)

Every section makes its category explicit and keeps them separate:

- **Observed** (crawler-measured, deterministic): keyword density & placement,
  content metrics (word count, readability, heading tree, first/last paragraph),
  internal/broken links, technical SEO, EEAT presence signals, current metadata
  values, URL analysis.
- **Inferred** (AI/rules): search intent, topic gaps/coverage scores, trust
  signals, canonical issues, the AI Intelligence Summary.
- **Proposed** (suggested changes): meta/title/slug proposals, alt text,
  internal/external link suggestions, generated JSON-LD, OG social fields.

Keyword **density and placement are computed deterministically from crawled
text** (never AI-estimated) and are used by `keyword_sanity_validator` to
sanity-check AI keyword claims (acceptance #3).

---

## Versioning & immutability model

- **Append-only versioning**: each analysis writes a new `KnowledgeObject`
  version for a `page_id` (`next_version = max + 1`); the "current" object is the
  max-version row. Prior versions are never overwritten, enabling future
  change-over-time reasoning.
- **Stable identifiers**: `page_id_for(tenant, url)` and
  `element_id_for(page_id, type, fingerprint)` give stable, addressable ids for
  pages and sub-entities (images/headings/links/schema) without re-parsing HTML.
- **`immutable_fields`** is a first-class, machine-enforced list on every
  KnowledgeObject (defaults: `identity.canonical_url`, `metadata.canonical`,
  `content_intelligence.first_paragraph`). The validation layer's `is_writable`
  rejects (and logs) any proposal/override targeting a locked path; the PATCH
  endpoint returns `409` for a locked field (acceptance #6).
- **Editor overrides (§13.3)**: `KnowledgeObject.overrides` is a uniform
  registry (`field_path -> FieldOverride`), and every `MetadataField`/`OgImageField`
  carries `override_source`/`overridden_at`/`overridden_by`. Human overrides are
  **carried forward unchanged** on re-analysis unless `force_regenerate_overrides`
  is set.

---

## AI provider layer & configuration

- One interface (`AIProvider`), six adapters (`openai`, `openrouter`, `ollama`,
  `local`, `claude`, `gemini`) + a deterministic `fake`. Business code depends on
  the interface only; `provider_factory.build_provider(ProviderConfig)` resolves
  a concrete provider from configuration — **switching providers is a config
  change, not a code change** (acceptance #4, proven by a test running the same
  orchestration against the fake and a real OpenAI adapter over mocked HTTP).
- Every AI call is wrapped into an **`AIInvocation` audit record** (provider,
  model, prompt version, validation result, **raw pre-validation response
  retained**), retrievable via `GET /intelligence/pages/{page_id}/ai-invocations`
  (acceptance #7).
- **No unvalidated AI output is ever persisted**: the `ValidationPipeline`
  parses → schema-validates → runs capability-specific validators; on failure the
  orchestrator retries (bounded, default 2, error fed back) and otherwise leaves
  the field null (acceptance #5, §7).

### Provider configuration

Set the provider via configuration (defaults to the deterministic `fake` so the
endpoints work with no AI account). `ProviderConfig(name=..., model=...,
api_key=..., base_url=...)` selects the adapter. `build_default_intelligence()`
reads Core settings; point `base_url`/`api_key` at your provider to go live.

---

## API surface (additive, §10, §13.6)

- `POST /intelligence/pages/{page_id}/analyze` (optional `capabilities`,
  `force_regenerate_overrides`)
- `GET /intelligence/pages/{page_id}`
- `GET /intelligence/pages/{page_id}/versions`
- `GET /intelligence/pages/{page_id}/versions/{version}`
- `GET /intelligence/pages/{page_id}/ai-invocations`
- `GET /intelligence/pages/{page_id}/content-score` (§13.6)
- `PATCH /intelligence/pages/{page_id}/fields` (human overrides, §13.6)

All are documented in the existing OpenAPI/Swagger and coexist with Milestone 1
routes.

---

## Fix generators (§8.2, acceptance #8)

`MetaDescriptionFixGenerator`, `TitleFixGenerator`, `SlugFixGenerator`,
`SchemaFixGenerator` read the KnowledgeObject's *proposed* fields and package them
as Milestone 1 `SuggestedFix` records that flow through the existing
Governance/Publisher pipeline **unchanged**. They are produced **report-only**
(`auto_applicable=0`) because Milestone 1's Publisher writes only page `content`
and media `alt_text` — see deferrals. Alt-text proposals continue to flow through
Milestone 1's existing `update_alt_text` generator/pipeline.

---

## Milestone 2.1 — Rank Math parity

All 22 mapped fields are present: primary/secondary keyphrases (validated 4–10),
SEO-friendly slug (`identity.proposed_slug`), meta title/description, social
title/description + OG image (`open_graph.og_title/og_description/og_image`),
canonical, robots, breadcrumbs, schema selection
(`schema_intelligence.selected_schema_type`), pillar content flag, **deterministic
content score** (0–100, transparent factor breakdown, versioned — never a
black-box number), internal + external link suggestions (external URLs downgraded
to null when unverifiable), keyword density, readability, heading analysis, image
alt analysis, URL analysis, and Rank-Math-style per-factor
`ai_summary.seo_recommendations`.

---

## Explicitly deferred (accommodated by the schema, not built)

- **Autonomous agents** (Planner/Executor/Reviewer/Research/SEO/Publishing/
  Content) — interfaces/records anticipate them; no agent is built.
- **RAG / embeddings** — the KnowledgeObject is chunkable/embeddable by design;
  no embedding pipeline is written.
- **Competitor data** — `ai_summary.competitive_positioning` stays null.
- **Live performance signals** (Core Web Vitals) — `performance_signals` nullable.
- **"Lock this field" API** — `immutable_fields` is built and enforced; the
  toggle endpoint is future work (defaults are seeded programmatically).
- **Topic-cluster modeling** — `PillarContentFlag.linked_cluster_pages` uses a
  simple heuristic only.
- **Live external-URL resolvability check** — `external_link_validator` does
  syntactic validation and downgrades unverifiable URLs to null; a HEAD-request
  liveness check is deferred.
- **`media_id` resolution from markup** — like Milestone 1, the crawler leaves
  image `media_id=None`, so image alt proposals become publishable only once a
  `media_id` is resolved (the known Milestone 1 gap).
- **Publishing of meta/title/slug/schema fixes** — Milestone 1's Publisher writes
  only `content`/`alt_text`; these fixes are report-only until a future Publisher
  extension adds those write targets. No change to the Publisher was made.
- **Parsed existing JSON-LD** — Milestone 1's crawler records only schema
  *presence* (`has_schema`), not the parsed blocks, so `existing_schema` stays
  empty; generated JSON-LD is fully validated before storage.

---

## Notable reconciliations with the actual codebase

- **Own persistence Base**: the intelligence tables use a separate SQLAlchemy
  `Base`, so Milestone 1's Alembic migration-model-sync check (which
  autogenerates against the Digital_Twin metadata only) is untouched. Tables are
  provisioned via `create_intelligence_tables(engine)`; a dedicated migration is
  future work.
- **`page_id`**: Milestone 1 does not expose `Page.id` by URL/id lookup or
  persist rich page data, so the intelligence layer derives a stable,
  URL-addressable `page_id` and stores the crawl-time `CrawledPage` snapshot it
  analyzes (so `/analyze` and re-analysis work without re-crawling).
- **Intelligence errors** are defined in-package (rooted at
  `core.exceptions.OrchestratorError`) so `core` stays untouched.
