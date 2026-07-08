# Requirements Document

## Introduction

The Website Orchestrator is a self-hosted, zero-budget, AI-assisted website operations platform. Milestone 0 ("Prove the loop") establishes the foundational, end-to-end operational loop for a single site running a single CMS (WordPress), with every change fully human-approved and using only deterministic checks (no LLM involved).

The governing principle for the entire platform, and enforced strictly in Milestone 0, is that the live website is never modified directly. Every write to the live site passes through a Publishing Adapter and only after a human explicitly approves the change through a Governance/Approval layer. In Milestone 0 there is no autonomous-approval path — the actor for every decision is always a human.

The proof-of-concept code referenced in the platform handbook (crawler, checks, ORM models, database, config) does not yet exist in this workspace. Milestone 0 therefore includes building the full loop from scratch. The milestone is complete when a real WordPress test site can be crawled, issues detected, a fix approved and applied, then rolled back — end to end — with the automated proof exercised against a local fixture site and a mocked WordPress client so tests never depend on a live external network or real credentials. The platform uses PostgreSQL as its datastore from day one, provisioned via Docker Compose, rather than starting on SQLite and migrating later; automated tests run against a local (for example Docker Compose-provisioned) PostgreSQL instance, which is not treated as an external-network dependency.

This document captures the Milestone 0 scope as EARS-format requirements grouped by subsystem, followed by cross-cutting engineering and non-functional requirements. Where a capability is explicitly out of scope for Milestone 0 (for example, meta description and schema writes, LLM involvement, graph databases, embeddings, and JavaScript rendering), the requirements state the boundary so the report-only behavior is verifiable.

## Glossary

- **Website_Orchestrator**: The overall platform. In Milestone 0 it comprises the subsystems defined below operating on a single tenant and a single WordPress site.
- **Crawler**: The subsystem that discovers and retrieves pages within a single domain, honoring politeness and safety constraints.
- **Digital_Twin**: The relational data model that stores a structured, queryable representation of the crawled site (pages, links, metadata, detected issues) with freshness metadata.
- **Check_Engine**: The subsystem that runs deterministic, rule-based checks over the Digital_Twin and emits structured issue candidates.
- **Fix_Generator**: The subsystem that transforms a detected Issue into a SuggestedFix record for human review.
- **Publishing_Adapter**: The WordPress REST API client; the only subsystem with write access to the live site, and only after approval.
- **Governance_Layer**: The subsystem that manages approval, rejection, application, rollback, audit, and status transitions for suggested fixes.
- **API_Surface**: The FastAPI application exposing the crawler, check engine, and approval workflow over HTTP.
- **CrawledPage**: A record produced by the Crawler for a single retrieved URL, including status, redirect chain, metadata, links, and a crawl timestamp.
- **IssueCandidate**: A structured object emitted by the Check_Engine describing one detected issue (issue type, severity, description, detail).
- **Issue**: A persisted issue candidate stored in the Digital_Twin, which may be marked ignored.
- **SuggestedFix**: A persisted record proposing a change to resolve an Issue, carrying an approval status and an auto_applicable flag.
- **Audit_Trail**: The single ordered log of every governance decision and status transition, including actor and rationale fields.
- **Actor**: The identity responsible for a governance decision. In Milestone 0 the actor is always a human.
- **Application_Password**: A WordPress-issued credential used with HTTP Basic authentication, distinct from the account login password.
- **Staleness_Threshold**: A configurable maximum age for Digital_Twin data, beyond which a re-crawl is required before acting.
- **Rate_Limit**: The Crawler's request-pacing constraint that protects client hosting; treated as a correctness constraint that is never relaxed to crawl faster.
- **Redirect_Chain**: The ordered sequence of URLs traversed by HTTP redirects for a single starting URL.
- **Tenant_Id**: The multi-tenancy identifier present on every table from day one.
- **Fixture_Site**: A local set of HTML fixtures used for crawling and end-to-end tests, never a live external site.
- **Report_Only_Fix**: A SuggestedFix with auto_applicable=0 that is recorded and approved for human action but never triggers a WordPress write.
- **Auto_Applicable_Fix**: A SuggestedFix with auto_applicable=1 that the Publishing_Adapter can apply after approval.
- **Datastore**: The PostgreSQL database, provisioned via Docker Compose, that persists all Website_Orchestrator relational data (pages, links, metadata, issues, suggested fixes, audit trail).
- **Core_Package**: The `packages/core` package containing the shared Exceptions, Types, Base Models, Interfaces, Events, Utilities, Constants, and Result Objects that all other subsystems depend on; Core_Package itself depends on no other subsystem.

## Requirements

### Requirement 1: Polite Same-Domain Crawling

**User Story:** As an operations engineer, I want the platform to crawl a single site politely and safely, so that discovery never harms client hosting and stays within the intended domain.

#### Acceptance Criteria

1. WHEN `crawl_site(start_url, max_pages)` is invoked with `max_pages` in the range 1 to 10000, THE Crawler SHALL retrieve pages beginning at `start_url` and return a list of CrawledPage records.
2. THE Crawler SHALL restrict retrieval to URLs on the same domain as `start_url`, where the same domain means a host or subdomain that shares the same registrable domain as `start_url`.
3. WHERE a URL is outside the same domain as `start_url`, THE Crawler SHALL exclude that URL from retrieval.
4. WHEN the number of retrieved pages reaches `max_pages`, THE Crawler SHALL stop retrieving additional pages.
5. IF `start_url` is malformed OR `max_pages` is outside the range 1 to 10000, THEN THE Crawler SHALL reject the invocation with a typed error and SHALL NOT retrieve any page.
6. THE Crawler SHALL request and honor the domain's robots.txt directives before retrieving a URL.
7. IF robots.txt cannot be retrieved, THEN THE Crawler SHALL fail closed and SHALL exclude the affected URLs from retrieval.
8. IF robots.txt disallows a URL, THEN THE Crawler SHALL exclude that URL from retrieval.
9. THE Crawler SHALL enforce the configured Rate_Limit between requests to the same host, using a default minimum delay of 1000 milliseconds.
10. THE Crawler SHALL treat the Rate_Limit as a correctness constraint and SHALL NOT reduce the delay below the configured Rate_Limit to increase crawl speed.
11. WHILE observed response times exceed the configured degradation threshold of 2000 milliseconds by default, THE Crawler SHALL increase the delay between requests to at least double the configured Rate_Limit.
12. WHEN a single request does not complete within the configured per-request timeout of 30 seconds by default, THE Crawler SHALL abandon that request.
13. THE Crawler SHALL render pages without executing JavaScript.

### Requirement 2: Redirect Handling and Link Status

**User Story:** As an operations engineer, I want redirects recorded explicitly and bounded, so that redirect problems are visible and the crawler cannot loop indefinitely.

#### Acceptance Criteria

1. WHEN a retrieved URL responds with an HTTP redirect status of 301, 302, 303, 307, or 308, THE Crawler SHALL record the ordered Redirect_Chain rather than silently following it without a record.
2. WHEN the length of a Redirect_Chain reaches the configured hard cap, which defaults to 10 redirects within the bounds 1 to 50, THE Crawler SHALL stop following that Redirect_Chain and record the chain up to the hard cap.
3. WHEN `check_link_status(url)` is invoked, THE Crawler SHALL return the integer HTTP status code observed for `url`, using a default request timeout of 10 seconds.
4. IF `check_link_status(url)` times out or encounters a network failure, THEN THE Crawler SHALL return an unreachable result and SHALL NOT raise an unhandled error.
5. THE Crawler SHALL operate only against local Fixture_Site resources during automated tests and SHALL NOT contact a live external site during automated tests.

### Requirement 3: Digital Twin Relational Model

**User Story:** As a department consuming site data, I want a structured, queryable model of the site with freshness metadata, so that I can act on accurate, sufficiently fresh information.

#### Acceptance Criteria

1. THE Digital_Twin SHALL store pages, links, metadata, and detected issues in a relational model.
2. THE Digital_Twin SHALL record a `crawled_at` UTC date-time for each stored page.
3. WHEN a read is served from the Digital_Twin, THE Digital_Twin SHALL include the `crawled_at` timestamp with the returned data.
4. WHILE the age of a requested page, measured as the elapsed time since that page's `crawled_at`, is within the configured Staleness_Threshold, THE Digital_Twin SHALL serve the page data for action.
5. IF the age of a requested page, measured as the elapsed time since that page's `crawled_at`, exceeds the configured Staleness_Threshold, THEN THE Digital_Twin SHALL indicate to the caller that the page is stale and SHALL require a re-crawl before the data is used to act.
6. IF a read requests a page not stored in the Digital_Twin, THEN THE Digital_Twin SHALL return a not-found indication and SHALL NOT return page data.
7. THE Digital_Twin SHALL store site representation without a graph database and without embeddings in Milestone 0.

### Requirement 4: Deterministic Technical Check Engine

**User Story:** As a site operator, I want deterministic, rule-based checks that flag issues as structured objects, so that detection is repeatable, explainable, and free of LLM involvement.

#### Acceptance Criteria

1. THE Check_Engine SHALL detect issues using deterministic, rule-based logic and SHALL NOT invoke an LLM.
2. THE Check_Engine SHALL provide page-level checks for missing title, missing meta description, thin content, missing alt text, broken links, redirect chains, and missing schema.
3. WHERE a page's word count is below the configured minimum word count, which defaults to 300, THE Check_Engine SHALL emit a thin-content IssueCandidate.
4. WHEN two or more pages have identical title text, THE Check_Engine SHALL emit a duplicate-title IssueCandidate.
5. WHEN a link has a client or server error status, THE Check_Engine SHALL emit a broken-links IssueCandidate.
6. WHEN a Redirect_Chain length reaches or exceeds the configured redirect-chain threshold, which defaults to 3 hops, THE Check_Engine SHALL emit a redirect-chains IssueCandidate.
7. THE Check_Engine SHALL implement one deterministic function per check and SHALL provide an aggregator that runs all checks.
8. WHEN a check detects an issue, THE Check_Engine SHALL emit an IssueCandidate whose `severity` is one of critical, high, medium, or low, whose `description` is a non-empty human-readable string, and whose `detail` identifies the affected page URL and the triggering element or location.
9. THE Check_Engine SHALL emit detected issues as structured IssueCandidate objects and SHALL NOT emit free-text-only results.
10. THE Check_Engine SHALL treat heuristic check results as flags for human review rather than as final verdicts.
11. WHERE an Issue is marked ignored, THE Check_Engine SHALL exclude that Issue from active issue reporting.

### Requirement 5: Suggested-Fix Generation

**User Story:** As a reviewer, I want detected issues turned into concrete suggested fixes with clear applicability, so that I can approve safe automated fixes and see why others are report-only.

#### Acceptance Criteria

1. WHEN the Fix_Generator receives an Issue and its Page, THE Fix_Generator SHALL perform a pure transformation that returns exactly one SuggestedFix or None and SHALL NOT write to the database.
2. WHERE the Issue is marked ignored or the Issue type has no defined fix mapping, THE Fix_Generator SHALL return None without producing a SuggestedFix.
3. WHERE the Issue type is missing_alt_text and the page HTML contains an image element from which a media identifier and a non-empty image filename can be extracted, THE Fix_Generator SHALL produce a SuggestedFix with `auto_applicable=1`, `fix_type=update_alt_text`, and non-empty heuristic alt text of at most 125 characters derived from the image filename.
4. THE Fix_Generator SHALL treat filename-derived alt text as a placeholder heuristic and SHALL NOT represent it as AI-generated content.
5. IF the Issue type is missing_alt_text and no media identifier can be extracted from the page HTML, THEN THE Fix_Generator SHALL produce a SuggestedFix with `auto_applicable=0` that records a human-readable reason indicating the media identifier could not be resolved, and SHALL retain the Issue reference.
6. WHERE the Issue type is a recognized type other than a resolvable missing_alt_text, THE Fix_Generator SHALL produce a SuggestedFix with `auto_applicable=0` that records a human-readable reason indicating the fix is report-only.
7. THE Fix_Generator SHALL NOT generate a replacement URL for a broken link Issue.

### Requirement 6: WordPress Publishing Adapter Scope and Authentication

**User Story:** As a security-conscious operator, I want the only write path to the live site to be a tightly scoped, authenticated adapter, so that live writes are limited, safe, and never leak credentials.

#### Acceptance Criteria

1. THE Publishing_Adapter SHALL be the only subsystem with write access to the live WordPress site.
2. THE Publishing_Adapter SHALL support writing media alt_text through `update_media_alt_text` and page/post content through `update_page_content`, and SHALL NOT write to any other field.
3. THE Publishing_Adapter SHALL treat meta descriptions and schema/JSON-LD as out of scope for writing and SHALL leave them as report-only in Milestone 0.
4. THE Publishing_Adapter SHALL authenticate every request using a WordPress Application_Password over HTTP Basic authentication.
5. THE Publishing_Adapter SHALL NOT use the WordPress account login password for authentication.
6. IF the Application_Password is missing or not configured, THEN THE Publishing_Adapter SHALL raise a typed error and SHALL NOT attempt a request.
7. THE Publishing_Adapter SHALL NOT include any credential in returned values or raised errors.
8. THE Publishing_Adapter SHALL expose the interfaces `list_pages`, `get_page`, `update_page_content`, `get_media`, and `update_media_alt_text`.

### Requirement 7: WordPress Publishing Adapter Error Handling and Idempotency

**User Story:** As a caller of the adapter, I want typed errors and predictable retries and idempotency, so that I can handle authentication, rate limiting, and network failures distinctly and safely.

#### Acceptance Criteria

1. IF a WordPress request fails authentication, THEN THE Publishing_Adapter SHALL raise a `WPAuthError`.
2. IF a WordPress request is rate limited, THEN THE Publishing_Adapter SHALL raise a `WPRateLimitError`.
3. IF a requested WordPress resource is not found, THEN THE Publishing_Adapter SHALL raise a `WPNotFoundError`.
4. IF a WordPress request fails for a client or network reason not covered by criteria 1 through 3, THEN THE Publishing_Adapter SHALL raise a `WPClientError`.
5. THE Publishing_Adapter SHALL NOT log any credential at any log level.
6. THE Publishing_Adapter SHALL NOT implement retry logic and SHALL leave retries to the caller.
7. WHEN the same write operation is applied more than once with the same target value, THE Publishing_Adapter SHALL leave the resulting live state equal to that target value, SHALL NOT create a duplicate resource, and SHALL NOT raise an error on the repeated application.
8. WHEN a WordPress request does not complete within the configured request timeout, THE Publishing_Adapter SHALL raise a `WPClientError`.
9. WHEN a WordPress request fails, THE Publishing_Adapter SHALL classify the failure as exactly one of `WPAuthError`, `WPRateLimitError`, `WPNotFoundError`, or `WPClientError`.
10. THE Publishing_Adapter SHALL NOT include any credential in the message or attributes of any raised error.

### Requirement 8: Governance Approval Workflow

**User Story:** As a governance owner, I want every fix decision to pass through a controlled workflow, so that changes are deliberately reviewed and status transitions are trustworthy.

#### Acceptance Criteria

1. THE Governance_Layer SHALL expose the interfaces `list_pending_fixes`, `approve_fix`, `reject_fix`, and `rollback_fix`.
2. THE Governance_Layer SHALL be the only path through which a SuggestedFix status transition occurs.
3. WHEN `approve_fix` is invoked for a Report_Only_Fix with an actor identity and a non-empty rationale, THE Governance_Layer SHALL set status to `approved`, write an Audit_Trail entry recording the actor and rationale, and stop without calling the Publishing_Adapter.
4. WHEN `approve_fix` is invoked for an Auto_Applicable_Fix, THE Governance_Layer SHALL read the live BEFORE value from WordPress immediately before writing and SHALL persist that freshly-read BEFORE value to the Audit_Trail before performing the write.
5. WHEN the Publishing_Adapter write for an approved Auto_Applicable_Fix succeeds, THE Governance_Layer SHALL set status to `applied` only after the write succeeds and SHALL write an Audit_Trail entry recording the actor and rationale.
6. IF the Publishing_Adapter write for an approved Auto_Applicable_Fix fails, THEN THE Governance_Layer SHALL keep status at `approved`, log the failure, and re-raise the error.
7. WHEN `reject_fix` is invoked with an actor identity and a non-empty rationale, THE Governance_Layer SHALL set status to `rejected` and write an Audit_Trail entry recording the actor and rationale.
8. IF `approve_fix` or `reject_fix` is invoked for a SuggestedFix whose status is already one of `approved`, `applied`, `rejected`, or `rolled_back`, THEN THE Governance_Layer SHALL raise a `FixAlreadyDecidedError` and SHALL NOT change the status.
9. IF `approve_fix`, `reject_fix`, or `rollback_fix` is invoked with an unknown SuggestedFix id, THEN THE Governance_Layer SHALL raise a `FixNotFoundError` and SHALL NOT write to WordPress.
10. IF the live BEFORE-read fails for an approved Auto_Applicable_Fix, THEN THE Governance_Layer SHALL fail closed, skip the write, keep status at `approved`, log the failure, and re-raise the error.
11. IF `approve_fix` or `reject_fix` is invoked with a missing actor or an empty rationale, THEN THE Governance_Layer SHALL fail closed, perform no status transition, and raise a validation error.
12. IF any governance policy error occurs during a decision, THEN THE Governance_Layer SHALL deny the operation (fail-closed) and SHALL NOT transition the SuggestedFix to `applied`.

### Requirement 9: Governance Rollback and Audit Trail

**User Story:** As a governance owner, I want reliable rollback and a complete, explainable audit trail, so that applied changes can be reversed and every decision is accountable.

#### Acceptance Criteria

1. IF `rollback_fix` is invoked for a SuggestedFix whose status is not `applied`, THEN THE Governance_Layer SHALL raise a typed governance error, SHALL NOT write to WordPress, and SHALL leave the status unchanged.
2. WHEN `rollback_fix` is invoked for a SuggestedFix whose status is `applied` and an audited `before_value` is available, THE Governance_Layer SHALL write the audited `before_value` back through the Publishing_Adapter, and only after that write succeeds SHALL set status to `rolled_back` and write an Audit_Trail entry.
3. THE Governance_Layer SHALL maintain a single Audit_Trail for all governance decisions and status transitions.
4. THE Audit_Trail SHALL record on every entry a non-empty `actor` field, a non-empty `rationale` field, the SuggestedFix identifier, and the resulting status transition.
5. WHEN a governance decision or status transition succeeds, THE Governance_Layer SHALL write exactly one Audit_Trail entry for that decision or transition.
6. IF the rollback Publishing_Adapter write fails, THEN THE Governance_Layer SHALL keep status at `applied`, log the failure, re-raise the error, and SHALL NOT write a `rolled_back` Audit_Trail entry.
7. IF the audited `before_value` is missing at rollback time, THEN THE Governance_Layer SHALL reject the rollback with a typed error, perform no write, and leave status at `applied`.
8. THE Governance_Layer SHALL record the Actor of every decision as a human in Milestone 0.

### Requirement 10: FastAPI Surface

**User Story:** As an operator, I want HTTP endpoints and documentation for the loop, so that I can drive crawling, review, approval, and rollback through a thin, documented API.

#### Acceptance Criteria

1. WHEN `POST /crawl` is invoked with a start URL and a maximum page count, THE API_Surface SHALL crawl the site beginning at the start URL up to the maximum page count, persist pages, run all checks, persist issues, generate suggested fixes, and return a summary containing the count of pages crawled, the count of issues grouped by issue type, and the count of Auto_Applicable_Fix records versus the count of Report_Only_Fix records.
2. WHEN `GET /issues` is invoked, THE API_Surface SHALL return the persisted issues.
3. WHEN `GET /fixes` is invoked, THE API_Surface SHALL return the persisted suggested fixes.
4. WHEN `POST /fixes/{id}/approve` is invoked, THE API_Surface SHALL invoke the Governance_Layer approve operation for the identified fix.
5. WHEN `POST /fixes/{id}/reject` is invoked, THE API_Surface SHALL invoke the Governance_Layer reject operation for the identified fix.
6. WHEN `POST /fixes/{id}/rollback` is invoked, THE API_Surface SHALL invoke the Governance_Layer rollback operation for the identified fix.
7. WHEN `GET /audit-log` is invoked, THE API_Surface SHALL return Audit_Trail entries ordered most recent first.
8. THE API_Surface SHALL use PostgreSQL as its datastore, provisioned via Docker Compose.
9. THE API_Surface SHALL publish automatic OpenAPI documentation at `/docs`.
10. THE API_Surface SHALL delegate crawling, check execution, fix generation, and governance operations to their respective subsystems and SHALL NOT implement that business logic within the route handlers.
11. IF `POST /crawl` is invoked without a valid start URL or without a positive integer maximum page count, THEN THE API_Surface SHALL reject the request, return a response indicating the invalid input, and SHALL NOT crawl or persist any data.
12. IF `POST /fixes/{id}/approve`, `POST /fixes/{id}/reject`, or `POST /fixes/{id}/rollback` is invoked with an `id` that does not identify a persisted SuggestedFix, THEN THE API_Surface SHALL return a response indicating the fix was not found and SHALL NOT invoke the Governance_Layer.
13. IF the Governance_Layer raises an error while processing an approve, reject, or rollback request, THEN THE API_Surface SHALL return a response indicating the failure and its reason and SHALL NOT report the operation as successful.

### Requirement 11: End-to-End Proof of the Loop

**User Story:** As a stakeholder, I want an automated end-to-end proof against local fixtures, so that the full Observe → Execute → Verify loop is demonstrated without touching a live site.

#### Acceptance Criteria

1. WHEN the end-to-end test runs, THE end-to-end test SHALL run against a local Fixture_Site and a local PostgreSQL Datastore such that no request leaves localhost and no real WordPress credential is used, where a local or containerized PostgreSQL instance is not considered an external-network dependency.
2. THE end-to-end test SHALL use a mocked WordPress client in place of the live Publishing_Adapter target.
3. WHEN the end-to-end test crawls the Fixture_Site, THE Check_Engine SHALL detect at least one Issue for each seeded issue type of missing title, missing meta description, missing alt text, broken link, and redirect chain.
4. THE end-to-end test SHALL assert that exactly one Auto_Applicable_Fix is produced.
5. WHEN the Auto_Applicable_Fix is approved through the mocked WordPress client, THE Governance_Layer SHALL set its status to `applied`, and the end-to-end test SHALL assert that exactly one mocked-client write occurs and that an Audit_Trail entry is written.
6. WHEN the applied fix has been applied, THE end-to-end test SHALL read the mocked client and SHALL assert that the read returns the written value.
7. WHEN a Report_Only_Fix is approved, THE end-to-end test SHALL assert that no mocked-client write occurs.
8. IF the applied fix is rolled back, THEN THE Governance_Layer SHALL write the `before_value` back through the mocked client, write an Audit_Trail entry, and set status to `rolled_back`.

### Requirement 12: Typed Contracts and Subsystem Boundaries

**User Story:** As a maintainer, I want subsystems to interact only through typed interfaces, so that the system stays modular and internals stay encapsulated.

#### Acceptance Criteria

1. THE Website_Orchestrator SHALL define, for each subsystem listed in the Glossary, a typed contract that specifies the typed input parameters and the typed return value for every operation that subsystem exposes to other subsystems, and SHALL exchange inter-subsystem data as the typed records defined in the Glossary (for example CrawledPage, IssueCandidate, Issue, SuggestedFix) rather than as untyped structures.
2. WHEN one subsystem calls another, THE calling subsystem SHALL invoke the target subsystem only through the operations enumerated in the target subsystem's published interface, and SHALL NOT import or reference the target subsystem's internal implementation modules.
3. THE Website_Orchestrator SHALL define at least one custom exception type for each subsystem listed in the Glossary, and for every handled error condition (an anticipated failure the subsystem detects and reports to its caller) THE subsystem SHALL raise its own custom exception type and SHALL NOT raise a bare `Exception`.
4. IF a call that a subsystem makes to a resource outside its own process (such as an HTTP request or the WordPress REST API) fails, THEN THE subsystem SHALL wrap that failure as its own subsystem's custom exception type and SHALL NOT propagate the raw underlying exception to the caller.
5. THE Website_Orchestrator SHALL define the shared typed records and the base/custom exception types referenced in this requirement within Core_Package, and each subsystem SHALL consume those shared types from Core_Package rather than duplicating them locally.

### Requirement 13: Observability and Logging

**User Story:** As an operator, I want structured, traceable logs of every decision, so that I can audit and debug the loop without leaking secrets.

#### Acceptance Criteria

1. THE Website_Orchestrator SHALL emit each log entry as a single structured JSON object containing at minimum a timestamp, a severity level, a message, and a trace identifier.
2. THE Website_Orchestrator SHALL assign the same trace identifier to every log entry produced during a single orchestration operation so that all entries for that operation can be correlated.
3. WHEN a governance decision completes, whether it succeeds or fails, THE Website_Orchestrator SHALL emit a log entry recording the decision outcome, the affected SuggestedFix identifier, the Actor, and the rationale.
4. THE Website_Orchestrator SHALL NOT write any credential value, including the Application_Password, to logs at any severity level.
5. IF a log entry's content would otherwise include a credential value, THEN THE Website_Orchestrator SHALL redact that value before the entry is written and SHALL retain the remaining non-credential content.

### Requirement 14: Secrets and Multi-Tenancy

**User Story:** As a platform owner, I want secrets kept out of source control and tenancy designed in from day one, so that the platform is secure and ready to scale to multiple tenants.

#### Acceptance Criteria

1. WHEN the Website_Orchestrator starts, THE Website_Orchestrator SHALL load secrets from environment variables or a `.env` file.
2. IF a required secret is not available from environment variables or a `.env` file when the Website_Orchestrator starts, THEN THE Website_Orchestrator SHALL fail to start and SHALL raise an error indicating which required secret is missing without exposing any secret value.
3. THE Website_Orchestrator SHALL exclude every file that contains credentials, including any `.env` file, from source control and SHALL NOT commit any credential value to source control.
4. THE Website_Orchestrator SHALL define every database table with a non-null `tenant_id` column.
5. WHEN a record is created in any database table, THE Website_Orchestrator SHALL set its `tenant_id` to the configured Tenant_Id.
6. IF a record is created in any database table and the Tenant_Id cannot be determined, THEN THE Website_Orchestrator SHALL reject the record creation and SHALL NOT persist a record with a missing `tenant_id`.

### Requirement 15: Core Package and Dependency Direction

**User Story:** As a maintainer, I want a single dependency-free core package that every subsystem builds on, so that shared contracts live in one place and dependencies always point inward.

#### Acceptance Criteria

1. THE Website_Orchestrator SHALL provide a `packages/core` package (Core_Package) containing shared Exceptions, Types, Base Models, Interfaces, Events, Utilities, Constants, and Result Objects.
2. Core_Package SHALL NOT import or depend on any other subsystem or package in the Website_Orchestrator.
3. THE Crawler, Digital_Twin, Check_Engine, Fix_Generator, Publishing_Adapter, Governance_Layer, and API_Surface SHALL each depend on Core_Package for shared exceptions, types, base models, interfaces, events, utilities, constants, and result objects rather than redefining them locally.
4. WHEN a subsystem raises a shared or base exception type, THE subsystem SHALL use an exception type defined in Core_Package, and any subsystem-specific exception SHALL subclass a Core_Package base exception.
5. WHEN a subsystem returns an operation result that represents success or a typed failure, THE subsystem SHALL use a Result Object defined in Core_Package.
6. IF a dependency would point from Core_Package to any other subsystem, THEN THE Website_Orchestrator SHALL treat that as an invalid dependency direction, since dependencies point inward toward Core_Package and never outward from it.
