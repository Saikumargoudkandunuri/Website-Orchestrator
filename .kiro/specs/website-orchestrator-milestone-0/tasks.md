# Implementation Plan: Website Orchestrator (Milestone 0 — "Prove the loop")

## Overview

This plan builds the full Observe → Execute → Verify loop from scratch as a Python 3.11 monorepo (FastAPI + SQLAlchemy/PostgreSQL via Docker Compose). Work proceeds inward-out: first the dependency-free `Core_Package` (types, results, exceptions, interfaces, config, logging), then the `Digital_Twin` persistence layer, then the leaf subsystems (`Crawler`, `Check_Engine`, `Fix_Generator`, `Publishing_Adapter`) that depend only on Core, then the `Governance_Layer` (the only live-write path), then the `API_Surface` that wires everything together, and finally the Requirement 11 end-to-end proof against a local fixture site with a mocked WordPress client and local PostgreSQL.

All 59 correctness properties from the design are implemented as individual Hypothesis property-based tests (minimum 100 iterations each, tagged `Feature: website-orchestrator-milestone-0, Property N: ...`). Test sub-tasks are marked optional with `*`; core implementation sub-tasks are never optional. External boundaries (WordPress, clock, robots.txt) are replaced with in-memory fakes/spies so property runs stay network-free.

## Tasks

- [x] 1. Set up monorepo, tooling, and infrastructure
  - [x] 1.1 Create monorepo structure and Python packaging
    - Create `packages/{core,crawler,digital_twin,check_engine,fix_generator,publishing_adapter,governance,api}` and `apps/e2e` package directories with `__init__.py` and per-package `pyproject.toml`
    - Add root `pyproject.toml`/workspace config declaring dependencies (fastapi, sqlalchemy>=2, alembic, httpx, beautifulsoup4, lxml, tldextract, pydantic>=2, pydantic-settings, structlog, pytest, hypothesis) with each subsystem depending only on `packages/core`
    - Configure `pytest` with a Hypothesis profile that sets `max_examples>=100`
    - _Requirements: 15.1, 15.3_

  - [x] 1.2 Provision PostgreSQL via Docker Compose and secrets scaffolding
    - Write `docker-compose.yml` with a PostgreSQL service used by the app and by automated tests
    - Create `.env.example` documenting required settings (`DATABASE_URL`, `TENANT_ID`, `WP_BASE_URL`, `WP_USERNAME`, `WP_APPLICATION_PASSWORD`, threshold overrides) and add `.env` plus any credential-bearing file to `.gitignore`
    - _Requirements: 10.8, 14.1, 14.3_

  - [x] 1.3 Write structural/smoke tests for repository layout
    - Assert `packages/core` exists, `.gitignore` excludes `.env`, and Docker Compose defines a PostgreSQL service
    - _Requirements: 10.8, 14.3, 15.1_

- [x] 2. Build the Core_Package foundation
  - [x] 2.1 Implement constants and utilities
    - Add `constants.py` (`DEFAULT_RATE_LIMIT_MS=1000`, `DEGRADATION_THRESHOLD_MS=2000`, `REQUEST_TIMEOUT_S=30`, `LINK_TIMEOUT_S=10`, `REDIRECT_HARD_CAP=10`, `THIN_CONTENT_MIN_WORDS=300`, `REDIRECT_CHAIN_THRESHOLD=3`, `MAX_ALT_TEXT_LEN=125`)
    - Add `utils.py` with `registrable_domain`, `same_registrable_domain`, `normalize_url`, `utc_now`, `redact_secrets`
    - _Requirements: 15.1_

  - [x] 2.2 Implement typed records
    - Add `types.py` Pydantic models: `RedirectChain`, `LinkStatus`, `ImageRef`, `CrawledPage`, `IssueCandidate`, `Issue`, `SuggestedFix`, `AuditEntry`, `CrawlSummary`, plus `IssueType`, `Severity`, `FixType`, `FixStatus`, `IssueDetail`, `TargetRef` enums/models
    - _Requirements: 12.1, 12.5, 15.1_

  - [x] 2.3 Implement Result objects and read sentinels
    - Add `results.py` with `Result[T]` = `Ok[T]` | `Err[E]` and `NotFound`/`Stale` read sentinels
    - _Requirements: 15.1, 15.5_

  - [x] 2.4 Implement the exception hierarchy
    - Add `exceptions.py` with `OrchestratorError` base and per-subsystem bases and leaves per the design (`CrawlerError`/`InvalidCrawlRequest`/`RobotsUnavailableError`, `DigitalTwinError`/`PageNotFound`/`StaleDataError`, `CheckEngineError`, `FixGeneratorError`, `PublishingError`/`WPAuthError`/`WPRateLimitError`/`WPNotFoundError`/`WPClientError`/`MissingCredentialError`, `GovernanceError`/`FixNotFoundError`/`FixAlreadyDecidedError`/`InvalidDecisionError`/`BeforeReadError`/`RollbackNotAllowedError`, `ApiError`, `ConfigError`/`MissingSecretError`)
    - _Requirements: 12.3, 15.1, 15.4_

  - [x] 2.5 Implement interfaces (Protocols) and domain events
    - Add `interfaces.py` with `CrawlerPort`, `DigitalTwinPort`, `CheckEnginePort`, `FixGeneratorPort`, `PublishingAdapterPort`, `GovernancePort` (typed params/returns)
    - Add `events.py` with `FixApproved`, `FixApplied`, `FixRolledBack`
    - _Requirements: 12.1, 12.2, 15.1_

  - [x] 2.6 Implement configuration loading and structured logging
    - Add `config.py` using `pydantic-settings` to load settings/secrets from env/`.env`, failing startup with a `MissingSecretError` that names the missing key but never its value
    - Add `logging.py` using `structlog` JSON renderer emitting single-line entries with timestamp, level, message, and a per-operation trace id, routing all payloads through `redact_secrets`
    - _Requirements: 13.1, 13.2, 13.4, 13.5, 14.1, 14.2_

  - [x] 2.7 Write property test for Core_Package dependency direction
    - **Property 58: Core_Package imports nothing internal**
    - **Validates: Requirements 15.2, 15.6**

  - [x] 2.8 Write property test for missing-secret startup failure
    - **Property 55: Missing required secret fails startup naming the key, not the value**
    - **Validates: Requirements 14.2**

  - [x] 2.9 Write property test for well-formed JSON log entries
    - **Property 51: Every log entry is a single well-formed JSON object**
    - **Validates: Requirements 13.1**

  - [x] 2.10 Write property test for shared trace id
    - **Property 52: All logs within one operation share a trace id**
    - **Validates: Requirements 13.2**

  - [x] 2.11 Write property test for credential redaction in logs
    - **Property 54: Credentials are redacted from logs while other content is retained**
    - **Validates: Requirements 13.4, 13.5**

  - [x] 2.12 Write unit tests for Core_Package utilities
    - Test `registrable_domain`/`same_registrable_domain` (subdomains), `normalize_url`, `utc_now` (UTC), and `redact_secrets` edge cases
    - _Requirements: 15.1_

- [x] 3. Checkpoint — Core foundation
  - Before marking this checkpoint complete, actually rerun the COMPLETE suite from the repository root (`uv run pytest`) and confirm it fully passes — zero failures, zero errors (see the `checkpoint-verification` steering rule). A partial or package-by-package run does not satisfy this gate. Ask the user if questions arise.

- [x] 4. Implement the Digital_Twin persistence layer
  - [x] 4.1 Create SQLAlchemy models and migrations
    - Define `PAGES`, `LINKS`, `PAGE_METADATA`, `ISSUES`, `SUGGESTED_FIXES`, `AUDIT_TRAIL` tables, each with a non-null `tenant_id`; wire Alembic against the Docker Compose PostgreSQL
    - _Requirements: 3.1, 3.7, 14.4_

  - [x] 4.2 Implement the repository operations
    - Implement `DigitalTwinPort`: `upsert_pages` (records UTC `crawled_at`), `get_page` returning `Ok`/`NotFound`/`Stale` via `now - crawled_at` vs `Staleness_Threshold`, `persist_issues`, `list_active_issues` (excludes ignored), `mark_issue_ignored`, `persist_fixes`, and Audit_Trail append/read; stamp configured `Tenant_Id` on every insert and reject inserts with no resolvable tenant
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 4.11, 14.5, 14.6_

  - [x] 4.3 Write property test for page persistence round-trip
    - **Property 10: Page persistence round-trip preserves crawled_at**
    - **Validates: Requirements 3.2, 3.3**

  - [x] 4.4 Write property test for freshness decision
    - **Property 11: Freshness decision matches the staleness threshold**
    - **Validates: Requirements 3.4, 3.5**

  - [x] 4.5 Write property test for unknown-page reads
    - **Property 12: Unknown page reads return not-found**
    - **Validates: Requirements 3.6**

  - [x] 4.6 Write property test for ignored-issue exclusion
    - **Property 19: Ignored issues are excluded from active reporting**
    - **Validates: Requirements 4.11**

  - [x] 4.7 Write property test for tenant_id column presence
    - **Property 56: Every table has a non-null tenant_id**
    - **Validates: Requirements 14.4**

  - [x] 4.8 Write property test for tenant stamping on create
    - **Property 57: Created records carry the configured tenant, or creation is rejected**
    - **Validates: Requirements 14.5, 14.6**

  - [x] 4.9 Write unit tests for repository edge cases
    - Test staleness boundary exactly at threshold and empty upserts
    - _Requirements: 3.4, 3.5_

- [x] 5. Implement the Crawler
  - [x] 5.1 Implement input validation and same-domain retrieval
    - Implement `crawl_site` skeleton: reject malformed `start_url` or `max_pages` outside `[1, 10000]` with `InvalidCrawlRequest` (retrieve nothing); restrict retrieval to the same registrable domain via `same_registrable_domain`; stop at `max_pages`; return `list[CrawledPage]`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 5.2 Implement robots.txt fail-closed gating
    - Consult robots.txt (via `urllib.robotparser`) before fetching; exclude disallowed URLs and exclude URLs whose robots.txt cannot be fetched (`RobotsUnavailableError` fail-closed)
    - _Requirements: 1.6, 1.7, 1.8_

  - [x] 5.3 Implement rate limiting, degradation backoff, and per-request timeout
    - Enforce `Rate_Limit` per host as a hard floor (default 1000 ms) never reduced for speed; double the delay while observed response times exceed the degradation threshold (default 2000 ms); abandon a request exceeding the per-request timeout (default 30 s); use an injectable clock for testability
    - _Requirements: 1.9, 1.10, 1.11, 1.12_

  - [x] 5.4 Implement HTML parsing and redirect-chain recording
    - Parse with BeautifulSoup (lxml) without executing JavaScript; record the ordered `Redirect_Chain` for 301/302/303/307/308 rather than silently following; stop at the redirect hard cap (default 10, bounds 1–50), record up to the cap, and mark truncated
    - _Requirements: 1.13, 2.1, 2.2_

  - [x] 5.5 Implement check_link_status
    - Return the observed integer status with a 10 s default timeout; on timeout/network failure return an unreachable `LinkStatus` without raising; operate only against the local Fixture_Site under automated tests
    - _Requirements: 2.3, 2.4, 2.5_

  - [x] 5.6 Write property test for same-domain retrieval
    - **Property 1: Retrieval stays within the same registrable domain**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 5.7 Write property test for max_pages bound
    - **Property 2: Retrieved page count is bounded by max_pages**
    - **Validates: Requirements 1.1, 1.4**

  - [x] 5.8 Write property test for invalid crawl requests
    - **Property 3: Invalid crawl requests retrieve nothing**
    - **Validates: Requirements 1.5**

  - [x] 5.9 Write property test for robots exclusion
    - **Property 4: Robots-excluded URLs are never retrieved**
    - **Validates: Requirements 1.6, 1.7, 1.8**

  - [x] 5.10 Write property test for the rate-limit floor
    - **Property 5: Rate-limit delay floor is never violated**
    - **Validates: Requirements 1.9, 1.10**

  - [x] 5.11 Write property test for degradation backoff
    - **Property 6: Delay doubles under observed degradation**
    - **Validates: Requirements 1.11**

  - [x] 5.12 Write property test for redirect-chain recording
    - **Property 7: Recorded redirect chain equals the actual traversal**
    - **Validates: Requirements 2.1**

  - [x] 5.13 Write property test for the redirect hard cap
    - **Property 8: Redirect chains are bounded by the hard cap**
    - **Validates: Requirements 2.2**

  - [x] 5.14 Write property test for check_link_status
    - **Property 9: check_link_status reports observed status or unreachable**
    - **Validates: Requirements 2.3, 2.4**

- [x] 6. Checkpoint — Observe layer (Crawler + Digital_Twin)
  - Before marking this checkpoint complete, actually rerun the COMPLETE suite from the repository root (`uv run pytest`) and confirm it fully passes — zero failures, zero errors (see the `checkpoint-verification` steering rule). A partial or package-by-package run does not satisfy this gate. Ask the user if questions arise.

- [x] 7. Implement the Check_Engine
  - [x] 7.1 Implement page-level deterministic checks
    - Implement `check_missing_title`, `check_missing_meta_description`, `check_thin_content` (word count < 300), `check_missing_alt_text`, `check_broken_links` (client/server error status), `check_redirect_chains` (chain length ≥ 3), `check_missing_schema`; each emits well-formed `IssueCandidate`s (`severity` in {critical,high,medium,low}, non-empty `description`, `detail` with page URL + triggering element); no LLM
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.8, 4.9, 4.10_

  - [x] 7.2 Implement duplicate-title check and the aggregator
    - Implement `check_duplicate_titles` (candidate when ≥2 pages share identical title) and `run_all_checks` running every individual check
    - _Requirements: 4.2, 4.4, 4.7_

  - [x] 7.3 Write property test for check determinism
    - **Property 13: Checks are deterministic**
    - **Validates: Requirements 4.1**

  - [x] 7.4 Write property test for thin-content detection
    - **Property 14: Thin-content detection matches the word-count threshold**
    - **Validates: Requirements 4.3**

  - [x] 7.5 Write property test for duplicate-title detection
    - **Property 15: Duplicate-title detection matches repeated titles**
    - **Validates: Requirements 4.4**

  - [x] 7.6 Write property test for broken-links detection
    - **Property 16: Broken-links detection matches error statuses**
    - **Validates: Requirements 4.5**

  - [x] 7.7 Write property test for redirect-chain detection
    - **Property 17: Redirect-chain detection matches the hop threshold**
    - **Validates: Requirements 4.6**

  - [x] 7.8 Write property test for well-formed issue candidates
    - **Property 18: Every emitted issue candidate is well-formed and structured**
    - **Validates: Requirements 4.8, 4.9**

- [x] 8. Implement the Fix_Generator
  - [x] 8.1 Implement generate_fix as a pure transform
    - Return exactly one `SuggestedFix` or `None`, never writing to the DB; `None` for ignored/unmapped issues; resolvable `missing_alt_text` → `auto_applicable=1`, `fix_type="update_alt_text"`, non-empty filename-derived alt text ≤125 chars labeled a placeholder heuristic; unresolvable `missing_alt_text` → `auto_applicable=0` with a reason and retained Issue reference; other recognized types → `auto_applicable=0` report-only reason; never generate a broken-link replacement URL
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 8.2 Write property test for the pure transform contract
    - **Property 20: generate_fix is a pure transform returning at most one fix**
    - **Validates: Requirements 5.1**

  - [x] 8.3 Write property test for ignored/unmapped issues
    - **Property 21: Ignored or unmapped issues yield no fix**
    - **Validates: Requirements 5.2**

  - [x] 8.4 Write property test for resolvable missing-alt-text
    - **Property 22: Resolvable missing-alt-text yields a valid auto-applicable fix**
    - **Validates: Requirements 5.3, 5.4**

  - [x] 8.5 Write property test for unresolvable missing-alt-text
    - **Property 23: Unresolvable missing-alt-text yields a report-only fix retaining the issue**
    - **Validates: Requirements 5.5**

  - [x] 8.6 Write property test for other recognized types
    - **Property 24: Other recognized issue types yield report-only fixes**
    - **Validates: Requirements 5.6**

  - [x] 8.7 Write property test for broken-link fixes
    - **Property 25: Broken-link fixes never propose a replacement URL**
    - **Validates: Requirements 5.7**

- [x] 9. Checkpoint — Detection and fix generation
  - Before marking this checkpoint complete, actually rerun the COMPLETE suite from the repository root (`uv run pytest`) and confirm it fully passes — zero failures, zero errors (see the `checkpoint-verification` steering rule). A partial or package-by-package run does not satisfy this gate. Ask the user if questions arise.

- [x] 10. Implement the Publishing_Adapter
  - [x] 10.1 Implement the WordPress REST client with scoped writes and auth
    - Implement `list_pages`, `get_page`, `update_page_content`, `get_media`, `update_media_alt_text` over `httpx`; write only page/post `content` and media `alt_text` (never meta/schema); authenticate every request via HTTP Basic using the `Application_Password` (never the login password); raise `MissingCredentialError` before any request when the Application_Password is unconfigured; never include credentials in returns/errors/logs
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 7.5, 7.10_

  - [x] 10.2 Implement failure classification, idempotency, and no-retry
    - Perform exactly one HTTP attempt per call (no retry); make repeated same-target writes idempotent (no duplicate, no error); classify every failure as exactly one of `WPAuthError`/`WPRateLimitError`/`WPNotFoundError`/`WPClientError` (timeouts → `WPClientError`), wrapping underlying HTTP exceptions rather than propagating them raw
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6, 7.7, 7.8, 7.9, 12.4_

  - [x] 10.3 Write property test for allowed-field writes
    - **Property 26: Writes touch only allowed fields**
    - **Validates: Requirements 6.2, 6.3**

  - [x] 10.4 Write property test for Application_Password authentication
    - **Property 27: Every request is authenticated with the Application_Password**
    - **Validates: Requirements 6.4, 6.5**

  - [x] 10.5 Write property test for missing-credential guard
    - **Property 28: Missing Application_Password prevents any request**
    - **Validates: Requirements 6.6**

  - [x] 10.6 Write property test for credential non-leakage
    - **Property 29: Credentials never leak through returns or errors**
    - **Validates: Requirements 6.7, 7.10**

  - [x] 10.7 Write property test for no-retry
    - **Property 30: No retry — a failed request is attempted exactly once**
    - **Validates: Requirements 7.6**

  - [x] 10.8 Write property test for idempotent writes
    - **Property 31: Repeated writes are idempotent**
    - **Validates: Requirements 7.7**

  - [x] 10.9 Write property test for failure classification
    - **Property 32: Every failure is classified as exactly one typed error**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.8, 7.9, 12.4**

- [x] 11. Implement the Governance_Layer
  - [x] 11.1 Implement approve_fix for report-only and auto-applicable fixes
    - `list_pending_fixes` and `approve_fix`: for a Report_Only_Fix set `approved` and write one Audit_Trail entry with actor+rationale, calling no Publishing_Adapter; for an Auto_Applicable_Fix read the live BEFORE value and persist it to the Audit_Trail strictly before the write, then set `applied` only after the write succeeds and write an Audit_Trail entry; emit a governance decision log (outcome, fix id, actor, rationale)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 13.3_

  - [x] 11.2 Implement decision guards and reject_fix
    - Enforce validation (missing actor / empty rationale → `InvalidDecisionError`, no transition), unknown id → `FixNotFoundError` (no WP write), already-decided → `FixAlreadyDecidedError`; on approve write failure keep `approved`, log and re-raise; on BEFORE-read failure fail closed, skip write, keep `approved`, log and re-raise; implement `reject_fix` (set `rejected` with an Audit_Trail entry); never reach `applied` on any policy error
    - _Requirements: 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12_

  - [x] 11.3 Implement rollback_fix and audit trail invariants
    - `rollback_fix` valid only from `applied` with an audited `before_value`: write `before_value` back through the Publishing_Adapter, then set `rolled_back` and write an Audit_Trail entry only after the write succeeds; non-applied or missing before_value → typed error, no write, unchanged; rollback write failure → keep `applied`, log, re-raise, write no `rolled_back` entry; guarantee exactly one well-formed Audit_Trail entry (non-empty actor+rationale, fix id, transition; actor always human) per successful transition
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 11.4 Write property test for report-only approval
    - **Property 33: Approving a report-only fix never calls the Publishing_Adapter**
    - **Validates: Requirements 8.3**

  - [x] 11.5 Write property test for auto-applicable approval ordering
    - **Property 34: Approving an auto-applicable fix reads and persists BEFORE prior to writing, then applies**
    - **Validates: Requirements 8.4, 8.5**

  - [x] 11.6 Write property test for fail-closed approval
    - **Property 35: Approval failures preserve the approved status and never reach applied**
    - **Validates: Requirements 8.6, 8.10, 8.12**

  - [x] 11.7 Write property test for rejection
    - **Property 36: Rejecting a pending fix sets rejected with an audit entry**
    - **Validates: Requirements 8.7**

  - [x] 11.8 Write property test for already-decided guard
    - **Property 37: Already-decided fixes cannot be re-decided**
    - **Validates: Requirements 8.8**

  - [x] 11.9 Write property test for unknown-id guard
    - **Property 38: Unknown fix ids raise not-found without writing to WordPress**
    - **Validates: Requirements 8.9**

  - [x] 11.10 Write property test for actor/rationale validation
    - **Property 39: Missing actor or empty rationale is rejected with no transition**
    - **Validates: Requirements 8.11**

  - [x] 11.11 Write property test for rollback preconditions
    - **Property 40: Rollback is valid only from applied with an audited before_value**
    - **Validates: Requirements 9.1, 9.7**

  - [x] 11.12 Write property test for successful rollback ordering
    - **Property 41: Successful rollback writes before_value first, then transitions**
    - **Validates: Requirements 9.2**

  - [x] 11.13 Write property test for rollback write failure
    - **Property 42: Rollback write failure preserves applied status and writes no rolled_back audit**
    - **Validates: Requirements 9.6**

  - [x] 11.14 Write property test for well-formed audit entries
    - **Property 43: Every audit entry is well-formed**
    - **Validates: Requirements 9.4, 9.8**

  - [x] 11.15 Write property test for one-audit-entry-per-transition
    - **Property 44: Exactly one audit entry per successful decision or transition**
    - **Validates: Requirements 9.5**

  - [x] 11.16 Write property test for governance decision logging
    - **Property 53: Governance decision logs carry outcome, fix id, actor, and rationale**
    - **Validates: Requirements 13.3**

- [x] 12. Checkpoint — Execute/Verify layer (Publishing + Governance)
  - Before marking this checkpoint complete, actually rerun the COMPLETE suite from the repository root (`uv run pytest`) and confirm it fully passes — zero failures, zero errors (see the `checkpoint-verification` steering rule). A partial or package-by-package run does not satisfy this gate. Ask the user if questions arise.

- [x] 13. Implement the API_Surface and wire the full loop
  - [x] 13.1 Implement the FastAPI app and POST /crawl orchestration
    - Create the FastAPI app (automatic `/docs`), wire dependency injection for all subsystems, and implement `POST /crawl` as a thin handler that delegates Crawler → Digital_Twin persist → Check_Engine → persist issues → Fix_Generator → persist fixes and returns a summary (pages crawled, issues grouped by type, auto-applicable vs report-only counts); reject invalid input (no valid start URL / non-positive max pages) with no crawl and no persistence
    - _Requirements: 10.1, 10.9, 10.10, 10.11_

  - [x] 13.2 Implement read endpoints
    - Implement `GET /issues`, `GET /fixes`, and `GET /audit-log` (entries most-recent first) delegating to the Digital_Twin/Governance
    - _Requirements: 10.2, 10.3, 10.7_

  - [x] 13.3 Implement decision endpoints and error mapping
    - Implement `POST /fixes/{id}/approve|reject|rollback` delegating to the Governance_Layer; return not-found and skip Governance when the id identifies no persisted fix; map Governance/Publishing exceptions to explicit HTTP failure responses reporting the reason and never signaling success
    - _Requirements: 10.4, 10.5, 10.6, 10.12, 10.13_

  - [x] 13.4 Write property test for crawl-summary counts
    - **Property 45: Crawl summary counts match persisted data**
    - **Validates: Requirements 10.1**

  - [x] 13.5 Write property test for issue/fix reads
    - **Property 46: Issue and fix reads return exactly what was persisted**
    - **Validates: Requirements 10.2, 10.3**

  - [x] 13.6 Write property test for audit-log ordering
    - **Property 47: Audit log is ordered most-recent first**
    - **Validates: Requirements 10.7**

  - [x] 13.7 Write property test for invalid crawl input
    - **Property 48: Invalid crawl input is rejected without side effects**
    - **Validates: Requirements 10.11**

  - [x] 13.8 Write property test for unknown-id decision endpoints
    - **Property 49: Unknown fix ids on decision endpoints return not-found without invoking Governance**
    - **Validates: Requirements 10.12**

  - [x] 13.9 Write property test for governance-error surfacing
    - **Property 50: Governance errors surface as failures, never as success**
    - **Validates: Requirements 10.13**

  - [x] 13.10 Write smoke/interface tests for the API surface
    - Assert `GET /docs` returns 200 and that decision handlers delegate exactly once to the Governance_Layer without embedding business logic
    - _Requirements: 10.9, 10.10_

- [x] 14. Verify architecture invariants across subsystems
  - [x] 14.1 Write property test for subsystem exception subclassing
    - **Property 59: Subsystem exceptions subclass a Core_Package base exception**
    - **Validates: Requirements 15.4, 12.3**

  - [x] 14.2 Write structural/smoke tests for boundaries and dependency direction
    - Assert the Publishing_Adapter is the sole write path, each subsystem imports shared symbols from Core (not each other's internals), and storage is relational-only (no graph DB/embeddings)
    - _Requirements: 3.7, 6.1, 12.2, 15.3_

- [x] 15. Build the end-to-end proof of the loop (Requirement 11)
  - [x] 15.1 Build the Fixture_Site and mocked WordPress client
    - Create local HTML fixtures seeding at least one of each issue type (missing title, missing meta description, missing alt text, broken link, redirect chain) plus exactly one resolvable missing-alt-text image (the single Auto_Applicable_Fix); implement an in-memory mocked WordPress client (spy on writes/reads) wired in place of the live Publishing_Adapter target against a local PostgreSQL datastore
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 15.2 Implement the end-to-end loop test
    - Drive the full Observe → Execute → Verify loop via the API against the Fixture_Site + local PostgreSQL: assert no request leaves localhost and no real credential is used; at least one Issue per seeded type; exactly one Auto_Applicable_Fix; approving it sets `applied` with exactly one mocked write and an Audit_Trail entry; reading the mocked client returns the written value; approving a Report_Only_Fix causes no mocked write; rollback writes `before_value`, writes an Audit_Trail entry, and sets `rolled_back`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

- [x] 16. Final checkpoint — full loop
  - Before marking this checkpoint complete, actually rerun the COMPLETE suite from the repository root (`uv run pytest`) and confirm it fully passes — zero failures, zero errors (see the `checkpoint-verification` steering rule). A partial or package-by-package run does not satisfy this gate. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP, but each corresponds to a design correctness property or a required structural/smoke check.
- Each of the 59 correctness properties is a single Hypothesis property-based test with a minimum of 100 iterations, tagged `Feature: website-orchestrator-milestone-0, Property N: ...`.
- External boundaries (WordPress client, wall clock for rate-limit timing, robots.txt, spy repositories) are replaced with in-memory fakes so property runs stay deterministic and network-free.
- Every task references specific requirement sub-clauses for traceability, and checkpoints ensure incremental validation between subsystems.
- The Requirement 11 E2E proof (tasks 15.1–15.2) is a concrete single-run instantiation of the general properties (e.g., 11.5 → Properties 34/44, 11.6 → Property 31, 11.7 → Property 33, 11.8 → Property 41).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.6"] },
    { "id": 3, "tasks": ["2.5"] },
    { "id": 4, "tasks": ["1.3", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "4.1", "5.1", "7.1", "8.1", "10.1"] },
    { "id": 5, "tasks": ["4.2", "5.2", "7.2", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "10.2"] },
    { "id": 6, "tasks": ["4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.3", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8", "10.9", "11.1"] },
    { "id": 7, "tasks": ["5.4", "11.2"] },
    { "id": 8, "tasks": ["5.5", "11.3"] },
    { "id": 9, "tasks": ["5.6", "5.7", "5.8", "5.9", "5.10", "5.11", "5.12", "5.13", "5.14", "11.4", "11.5", "11.6", "11.7", "11.8", "11.9", "11.10", "11.11", "11.12", "11.13", "11.14", "11.15", "11.16", "13.1"] },
    { "id": 10, "tasks": ["13.2"] },
    { "id": 11, "tasks": ["13.3"] },
    { "id": 12, "tasks": ["13.4", "13.5", "13.6", "13.7", "13.8", "13.9", "13.10", "14.1", "14.2", "15.1"] },
    { "id": 13, "tasks": ["15.2"] }
  ]
}
```
