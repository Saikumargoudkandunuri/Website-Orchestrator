# Milestone 4 Implementation Map

Generated during the continuation audit on 2026-07-08 and updated after Phase 2
implementation/Phase 3 verification. This map is based on the repository state
and live commands, not on milestone documents alone.

## Phase 1 Discovery Inventory

### Workspace and Packages

- Root workspace: `C:\Users\Admin\Website-Orchestrator`
- `pyproject.toml` uses `uv` workspace members `packages/*` and `apps/*`.
- Active package areas:
  - Milestone 0/1 core flow: `core`, `crawler`, `digital_twin`, `check_engine`,
    `fix_generator`, `publishing_adapter`, `governance`, `api`
  - Milestone 2: `intelligence`
  - Milestone 3: `engines`
  - Milestone 4: `growth`
  - End-to-end tests/app package: `apps/e2e`

### Milestone 3 Engine Inventory

The `packages/engines` package contains all ten named engines:

- `technical_seo`
- `site_architecture`
- `keyword_intelligence`
- `content_intelligence`
- `competitor_intelligence`
- `backlink_intelligence`
- `topical_authority`
- `seo_scoring`
- `opportunity`
- `recommendation`

Supporting M3 infrastructure exists:

- `engines.shared.engine_registry.default_engine_registry()` imports and
  registers all ten engines.
- `engines.shared.engine_orchestrator.EngineOrchestrator` defines the intended
  tiered DAG:
  - Tier 1: `technical_seo`, `site_architecture`, `keyword_intelligence`,
    `content_intelligence`, `competitor_intelligence`, `backlink_intelligence`,
    `topical_authority`
  - Tier 2: `seo_scoring`
  - Tier 3: `opportunity`
  - Tier 4: `recommendation`
- Tier 1 runs through `ThreadPoolExecutor`.
- Failures are isolated and recorded as partial audit output.

M3 gaps found during discovery:

- No direct `packages/engines/tests` test package exists.
- Ten engine `api/__init__.py` files are UTF-16 BOM-only/invalid UTF-8 source
  and fail `compileall`.
- `EngineOrchestrator._is_fresh()` always returns `False`; the comment says the
  full version comparison is a future enhancement.
- SEO provider abstraction has TODOs for competitor and backlink provider
  integration.
- Some model comments still describe placeholder-data semantics.

### Milestone 4 Growth Inventory

The `packages/growth` package contains modules for:

- Content generation
- Content optimization
- Local SEO
- Reputation management
- Rank tracking
- Reporting
- Analytics intelligence
- Outreach
- Automation
- Agency management
- Shared jobs, provider abstraction, automation, and lifecycle support

Growth API wiring exists:

- `growth.api.wiring.GrowthContainer`
- `growth.api.wiring.build_growth_container()`
- `growth.api.wiring.build_default_growth()`
- `growth.api.routes_growth.build_growth_router()`
- `api.app.create_app(..., growth=...)`
- `api.app._mount_growth()`
- `core.config.Settings.growth_engine_enabled`, defaulting to `False`

Direct Growth API smoke check:

- Injected in-memory Growth app booted.
- `POST /growth/local-seo/sites/site-a/analyze` returned `200`.
- OpenAPI exposed 27 `/growth` paths.

Mounted Growth route areas:

- Content generation: generate, fetch, list by site, submit, approve, reject,
  publish, verify
- Content optimization: analyze page, latest report
- Local SEO: analyze site, latest report
- Reputation: analyze site, latest report
- Rank tracking: add keyword, capture, report, schedule
- Reporting: generate, fetch artifact
- Analytics: analyze site
- Outreach: analyze site
- Automation: create/list/disable rules, publish events, execution log

M4 gaps found during initial discovery:

- Agency management existed as package code but was not wired into
  `GrowthContainer` or `routes_growth.py`. Fixed in Phase 2.
- Agency repository did not match the current `growth.db` ORM row shape and
  used `Err(...)` without importing `Err`. Fixed in Phase 2.
- Growth production mount is opt-in, but Milestone 2 Intelligence still
  auto-builds on the pure production path and can create DB tables as a startup
  side effect. Fixed in Phase 2.
- Scheduled jobs are registered in `ScheduledJobRegistry`/`default_scheduled_jobs`
  and use `FakeJobQueue`; there is no production worker lifecycle, broker, or
  durable scheduler integration yet.
- Growth tests initially covered only local SEO, rank tracking, and automation
  API flows. Phase 2 added Agency Management and health API coverage.
- No Growth auth/authorization dependency is present.
- No Growth-specific rate limiting, metrics hooks, or structured logging
  coverage was found.
- No Growth-specific health/readiness endpoint was found initially. Fixed in
  Phase 2 with `/growth/health`.

## Boot, Runtime, and Test Results

### Dependency Sync

Command:

```powershell
uv sync --frozen
```

Sandboxed run failed with `Access is denied` under the user uv cache:
`C:\Users\Admin\AppData\Local\uv\cache\sdists-v9\.git`.

Escalated rerun passed:

```text
Checked 61 packages in 26ms
```

### Production API Boot

Command:

```powershell
uv run python -c "from api.app import create_app; app=create_app(); print(...)"
```

Result:

- Boot succeeded.
- App reported 12 primary route objects.
- Initial route list included docs routes plus M1 API routes.

Important side effect:

- The pure production `create_app()` path auto-built Milestone 2 Intelligence.
- That created Intelligence tables in the configured PostgreSQL schema.
- This later polluted the Digital Twin empty-database migration test.

### Growth Injected Boot

Injected SQLite Growth container smoke:

```text
SMOKE_STATUS 200
OPENAPI_GROWTH_COUNT 27
```

### Full Test Suite

Command:

```powershell
uv run pytest -q
```

Initial result after the production boot side effect:

```text
1 failed, 615 passed, 4 warnings
```

Failure:

- `packages/digital_twin/tests/test_migration_sync.py::test_migration_runs_successfully_on_empty_database`

Cause:

- The test expected only Digital Twin tables:
  `pages`, `links`, `page_metadata`, `issues`, `suggested_fixes`, `audit_trail`
- The database also contained Milestone 2 Intelligence tables:
  `page_snapshots`, `knowledge_objects`, `ai_invocations`

Initial conclusion:

- Production boot has a DB mutation side effect that breaks an empty-schema
  migration invariant when tests reuse the same configured PostgreSQL database.

Phase 2 fix:

- Added `core.config.Settings.intelligence_engine_enabled`, defaulting to
  `False`.
- Updated `api.app._mount_intelligence()` to build the default Intelligence
  container only when that flag is enabled, while preserving explicit injected
  Intelligence containers.
- Cleaned the three stray local test DB tables created by the earlier boot:
  `ai_invocations`, `knowledge_objects`, `page_snapshots`.

Phase 3 verification:

```text
DEFAULT_INTELLIGENCE_PATHS 0
DEFAULT_GROWTH_PATHS 0
```

The previously failing migration test now passes.

### Compile Check

Command:

```powershell
uv run python -m compileall -q packages apps
```

Initial result:

- Failed.
- All ten `packages/engines/engines/*/api/__init__.py` files failed with invalid
  UTF-8/SyntaxError.
- Byte probe on `technical_seo/api/__init__.py` returned `FF FE`, confirming
  UTF-16 encoding/BOM-only source.

Affected files:

- `packages/engines/engines/backlink_intelligence/api/__init__.py`
- `packages/engines/engines/competitor_intelligence/api/__init__.py`
- `packages/engines/engines/content_intelligence/api/__init__.py`
- `packages/engines/engines/keyword_intelligence/api/__init__.py`
- `packages/engines/engines/opportunity/api/__init__.py`
- `packages/engines/engines/recommendation/api/__init__.py`
- `packages/engines/engines/seo_scoring/api/__init__.py`
- `packages/engines/engines/site_architecture/api/__init__.py`
- `packages/engines/engines/technical_seo/api/__init__.py`
- `packages/engines/engines/topical_authority/api/__init__.py`

Phase 2 fix:

- Rewrote all ten malformed package marker files as valid UTF-8 Python files.

Phase 3 verification:

```powershell
uv run python -m compileall -q packages apps
```

Result: passed.

## TODO, Stub, Placeholder Sweep

Command:

```powershell
rg -n "TODO|FIXME|XXX|NotImplementedError|raise NotImplementedError|pass\s*#|placeholder|Placeholder|stub|Stub|return \[\]|return None|return \{\}" packages apps -S
```

Actionable M3/M4 hits:

- `packages/engines/engines/shared/provider_abstraction/seo_data_provider_interface.py`
  - TODO for competitor provider integration.
  - TODO for backlink provider integration.
- `packages/engines/engines/shared/engine_orchestrator.py`
  - `_is_fresh()` documented as a stub/future enhancement and always returns
    `False`.
  - Persistence exceptions are swallowed so audit pipelines continue.
- `packages/engines/engines/keyword_intelligence/services/__init__.py`
  - Gap analysis currently returns an empty list in at least one path.
- `packages/engines/engines/competitor_intelligence/models.py`
  - Comments refer to placeholder data and completeness.
- `packages/engines/engines/seo_scoring/models.py`
  - Data completeness comments describe placeholder scale.
- `packages/growth/growth/shared/automation/automation_rule_engine.py`
  - Default action dispatch path is no-op.
  - Template placeholder text is expected and not a defect by itself.
- `packages/growth/growth/rank_tracking/services/__init__.py`
  - Share-of-voice provider hook returns `None` when unavailable.
- `packages/ai_generator/ai_generator/llm.py`
  - LLM vendor integration TODO. This is not Growth-specific but affects
    production-grade AI generation.

Benign or test-local categories:

- Many `return None`, `return []`, and `pass` hits are in fakes, tests, optional
  interface branches, or defensive error handling. They should be reviewed when
  touching their module but are not automatically blockers.

## Cross-Cutting Checks

### Tenant Isolation

- Growth repositories generally accept tenant IDs and route handlers normalize to
  the configured container tenant.
- There is no request-authenticated tenant resolution yet; current API routes use
  the configured tenant from the container.

### Security and Authorization

- Growth routes do not use `Depends(...)` for auth or permissions.
- No role/permission enforcement was found in Growth API routes.
- Agency Role model exists but is not wired into API authorization.

### Health, Monitoring, Logging

- Growth now exposes `/growth/health` when the Growth router is mounted.
- No Growth-specific metrics instrumentation found.
- Core structured logging exists, but Growth services/routes do not currently
  expose meaningful logging coverage.

### Scheduling

- Scheduled job definitions exist.
- Rank tracking and reporting can enqueue into `FakeJobQueue`.
- No durable production worker/scheduler lifecycle is wired.

### Tests

- Full repo suite now passes after the boot isolation fix and local DB cleanup.
- Growth API tests cover local SEO, rank tracking, automation, agency
  management, and health.
- M3 engine package now has direct registry/orchestrator test coverage.
- Compile coverage now passes after invalid-encoding package markers were fixed.

## Percent Complete Estimates

These are implementation readiness estimates from live code discovery.

- Milestone 3: 80%
  - Strong engine/module inventory, registry, and DAG orchestrator are present.
  - Completed in Phase 2: invalid source files fixed and direct
    registry/orchestrator tests added.
  - Blockers: staleness stub, provider integration TODOs, limited production API
    exposure.
- Milestone 4: 74%
  - Most Growth engines, repositories, services, DI, and API routes are present.
  - Completed in Phase 2: Agency Management repository/API/container wiring,
    Agency API test coverage, Growth health endpoint, compile hygiene, and
    optional Intelligence boot isolation.
  - Remaining blockers: no auth/permissions, no metrics/logging, scheduler is
    fake/in-process, Growth coverage is still not complete across every engine
    flow, and M3 provider/staleness gaps remain.

## Complete and Working

- Root dependency sync works with approved filesystem access.
- M1/M2/M3/M4 packages import sufficiently for most test coverage.
- Full test suite now reaches 620 passing tests.
- Growth injected API boots and serves at least local SEO smoke flow.
- Growth OpenAPI exposes 37 `/growth` paths with Agency and health endpoints
  included.
- Growth DI wires ten major Growth service areas, including Agency Management.
- Growth production mount is opt-in via `growth_engine_enabled=False`.
- Intelligence production mount is opt-in via `intelligence_engine_enabled=False`.
- Rank tracking, automation, local SEO, Agency Management, and Growth health have
  API tests.
- Milestone 3 registry/orchestrator has direct tests.

## Phase 2 Completed Changes

- Added `intelligence_engine_enabled` configuration and gated default
  Intelligence auto-mounting.
- Repaired the local PostgreSQL test schema after the earlier boot side effect.
- Rewrote ten malformed M3 `api/__init__.py` package markers as UTF-8.
- Added direct M3 registry/orchestrator tests.
- Replaced the Agency Management repository with a schema-aligned implementation.
- Wired `AgencyManagementRepository` and `AgencyManagementService` into
  `GrowthContainer`.
- Added Agency Management routes under `/growth/agency/...`.
- Added an Agency API CRUD/status/notification test.
- Added `/growth/health` and health test coverage.

## Phase 3 Verification

Commands and results:

```powershell
uv run python -m compileall -q packages apps
```

Passed.

```powershell
uv run pytest packages\growth\tests\test_growth_api.py packages\engines\tests\test_engine_registry_orchestrator.py -q
```

```text
7 passed, 1 warning
```

```powershell
uv run pytest packages\intelligence\tests\test_api.py packages\growth\tests\test_growth_api.py packages\digital_twin\tests\test_migration_sync.py::test_migration_runs_successfully_on_empty_database -q
```

```text
12 passed, 2 warnings
```

```powershell
uv run pytest -q
```

```text
620 passed, 4 warnings in 135.33s
```

Injected Growth route verification:

```text
GROWTH_OPENAPI_PATHS 37
HAS_HEALTH True
HAS_AGENCY True
GROWTH_CONTAINER_ATTRS content_generation|content_optimization|local_seo|reputation|rank_tracking|reporting|analytics|outreach|automation|agency_management
```

## Prioritized Phase 2 Plan

1. Broaden M4 API coverage.
   - Add tests for content generation lifecycle, content optimization, reporting,
     analytics, outreach, and reputation.
   - Verify tenant scoping on persisted/readback flows.

2. Add Growth observability foundations.
   - Add structured logs around analysis/generation/scheduled job execution.
   - Add lightweight metrics counters or explicit extension points.

3. Harden scheduling.
   - Keep fake queue for tests.
   - Add a production-facing scheduler/worker boundary or clearly injectable
     queue interface with lifecycle hooks.
   - Add idempotency/retry tests for scheduled jobs.

4. Revisit M3 completion gaps.
   - Implement real staleness behavior or narrow acceptance wording if versioned
     KnowledgeObject comparison is intentionally deferred.
   - Remove placeholder comments only after behavior is production-backed.

5. Add Growth auth/authorization.
   - Introduce request-scoped identity/permission dependencies.
   - Connect Agency roles to API authorization.
   - Add unauthorized/forbidden tests.

## 2026-07-08 Production Hardening Phase 1 Re-Verification

This section was added for the "Milestone 4 Production Hardening (Final ~5%)"
pass. It re-verifies the starting state before new hardening code is added.

### Baseline Commands

Dependency sync:

```powershell
uv sync
```

Result:

```text
Resolved 63 packages in 7ms
Checked 61 packages in 306ms
```

Plain production app boot and optional-router isolation:

```text
BOOT_OK 7
DEFAULT_INTELLIGENCE_PATHS 0
DEFAULT_GROWTH_PATHS 0
PATHS /audit-log|/crawl|/fixes|/fixes/{id}/approve|/fixes/{id}/reject|/fixes/{id}/rollback|/issues
```

Compile:

```powershell
uv run python -m compileall -q packages apps
```

Result: passed with zero compile errors.

Full suite:

```powershell
uv run pytest -q
```

Result:

```text
620 passed, 4 warnings in 154.01s
```

No skips were reported.

### Growth OpenAPI Route Inventory

Injected Growth app route count:

```text
GROWTH_OPENAPI_COUNT 37
```

Current `/growth` paths:

- `/growth/agency/notifications`
- `/growth/agency/notifications/{recipient_id}`
- `/growth/agency/organizations`
- `/growth/agency/organizations/{organization_id}`
- `/growth/agency/organizations/{organization_id}/clients`
- `/growth/agency/organizations/{organization_id}/teams`
- `/growth/agency/tasks`
- `/growth/agency/tasks/{task_id}/status`
- `/growth/agency/workspaces`
- `/growth/analytics/sites/{site_id}/analyze`
- `/growth/automation/events`
- `/growth/automation/rules`
- `/growth/automation/rules/{rule_id}`
- `/growth/automation/sites/{site_id}/execution-log`
- `/growth/automation/sites/{site_id}/rules`
- `/growth/content-generation/assets/{asset_id}`
- `/growth/content-generation/assets/{asset_id}/approve`
- `/growth/content-generation/assets/{asset_id}/publish`
- `/growth/content-generation/assets/{asset_id}/reject`
- `/growth/content-generation/assets/{asset_id}/submit`
- `/growth/content-generation/assets/{asset_id}/verify`
- `/growth/content-generation/generate`
- `/growth/content-generation/sites/{site_id}/assets`
- `/growth/content-optimization/pages/{page_id}/analyze`
- `/growth/content-optimization/pages/{page_id}/reports/latest`
- `/growth/health`
- `/growth/local-seo/sites/{site_id}/analyze`
- `/growth/local-seo/sites/{site_id}/reports/latest`
- `/growth/outreach/sites/{site_id}/analyze`
- `/growth/rank-tracking/sites/{site_id}/capture`
- `/growth/rank-tracking/sites/{site_id}/keywords`
- `/growth/rank-tracking/sites/{site_id}/report`
- `/growth/rank-tracking/sites/{site_id}/schedule`
- `/growth/reporting/artifacts/{artifact_id}`
- `/growth/reporting/sites/{site_id}/generate`
- `/growth/reputation/sites/{site_id}/analyze`
- `/growth/reputation/sites/{site_id}/reports/latest`

### Existing Auth, Authorization, Rate Limit, and Middleware Findings

Production code currently has no Growth authentication dependency, no
`HTTPBearer`, no JWT/OAuth implementation, no `Authorization` header parsing,
and no rate limiter or middleware enforcing Growth access.

Existing `Depends(...)` usage is the older M1 API dependency pattern in
`packages/api/api/dependencies.py` and `packages/api/api/app.py`, focused on
subsystems and the configured `tenant_id`. Growth routes currently use
`Request` and `_container(request)` directly rather than FastAPI dependencies.

Existing role/permission modeling is minimal:

- `packages/growth/growth/agency_management/models.py` has a `Role` dataclass
  with `role_name: str` and `permissions: list[str]`.
- The role docstring mentions only `owner`, `admin`, `editor`, `viewer`, and
  `client_readonly`.
- No enum, permission matrix, or enforcement dependency is wired.
- `growth.errors.GrowthPermissionError` exists but is not used for route
  enforcement.

Tenant IDs are widely present as persistence scoping fields, but not yet as an
authenticated request boundary.

### Existing Scheduler and Queue Findings

Current scheduler/queue code:

- `growth.shared.jobs.job_queue_interface.JobQueue` protocol exposes
  `enqueue`, `schedule`, `status`, and `cancel`.
- `JobDefinition` and `JobResult` exist with basic job status fields.
- `growth.shared.jobs.fake_job_queue.FakeJobQueue` is the only queue
  implementation currently wired into `GrowthContainer`.
- `growth.shared.jobs.scheduled_job_registry.default_scheduled_jobs()` registers
  daily/weekly/monthly rank tracking, analytics snapshot capture, and weekly
  scheduled report generation cron expressions.
- No production queue library was found in `pyproject.toml` files or `uv.lock`
  for Celery, RQ, Redis, APScheduler, Dramatiq, Huey, ARQ, RabbitMQ, Kafka, or
  similar.
- No durable worker, retry policy, backoff, dead-letter queue, persisted job
  status/history, or scheduler worker lifecycle is implemented yet.

### Existing Observability Findings

Core has structured logging in `packages/core/core/logging.py`:

- `configure_logging`
- `get_logger`
- `operation_trace`
- trace ID binding/redaction support

Growth services/routes do not yet emit structured logs for request IDs,
correlation IDs, job duration, queue duration, engine operation summaries, or
failure reasons. No Growth metrics provider, OpenTelemetry hooks, counters, or
histograms were found.

### Existing Health Endpoint Shape

Current `/growth/health` implementation is in
`packages/growth/growth/api/routes_growth.py` and returns:

```python
{
    "status": "ok",
    "tenant_id": c.tenant_id,
    "services": {name: hasattr(c, name) for name in services},
}
```

The service list is:

- `content_generation`
- `content_optimization`
- `local_seo`
- `reputation`
- `rank_tracking`
- `reporting`
- `analytics`
- `outreach`
- `automation`
- `agency_management`

It does not yet report database connectivity, queue/scheduler connectivity,
worker liveness, storage connectivity, external provider reachability, version,
uptime, CPU/memory indicators, or separate readiness/liveness states.

### Existing Provider Framework Findings

Growth provider abstractions currently exist for five categories under
`growth.shared.provider_abstraction`:

- `analytics_data_provider_interface.py`
- `local_seo_data_provider_interface.py`
- `outreach_data_provider_interface.py`
- `rank_tracking_provider_interface.py`
- `reputation_data_provider_interface.py`

`fake_providers.py` contains deterministic fake providers for those five
categories. There is no unified provider health/capability/cache/circuit-breaker
framework yet, and no interfaces were found for email providers, webhook
providers, citation providers as a standalone category, Google Business Profile
as a standalone adapter, or SERP provider fail-loud production adapters.

### Phase 1 Conclusion

The prior session's baseline still holds: 37 Growth routes, clean compile, plain
boot isolation, and 620 passing tests. The production-hardening gaps in this
prompt are real in the current tree: Growth endpoints are open, roles are data
only, the scheduler is fake/in-process only, observability is core-level but not
threaded through Growth, rate limiting is absent, health is shallow, and the
provider framework needs production hardening.
