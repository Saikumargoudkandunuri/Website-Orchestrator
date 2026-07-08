# Milestone 1 — Real Fix Generation (`update_alt_text`)

Milestone 0 proved the loop end to end (crawl → detect → generate → govern →
publish → verify → rollback) but the generated alt text was a **filename-derived
placeholder heuristic**, and in the live pipeline every alt-text fix was
report-only (see "Why M0 fixes were report-only" below). Milestone 1 delivers
the milestone's core: **real, AI-generated alt text**, produced behind a clean,
injectable, fully-tested abstraction, and layered onto the existing architecture
without regressing any Milestone 0 behavior.

Baseline before this work: `398 passed`. This milestone is purely additive.

---

## What was implemented

### 1. A real AI generation layer (the new subsystem)

New package **`packages/ai_generator`** (`wo-ai-generator`), depending only on
`wo-core`:

- **`AltTextGenerationService`** (contract in `core.interfaces`) — proposes alt
  text for an image, returning a typed `Result[AltTextGenerationOutput,
  GenerationError]`. It never raises for a handled failure, so callers degrade
  gracefully.
- **`LlmAltTextGenerationService`** — the LLM-backed implementation. Builds an
  accessibility-first prompt from the page/image context, calls the model,
  cleans the result (strips wrapping quotes, redundant "image of"/"picture of"
  lead-ins, trailing period), and returns it with model provenance.
- **`DeterministicAltTextGenerationService`** — a network-free, deterministic
  double implementing the same contract, used by tests and as a safe offline
  option. Honors the length budget via word-boundary truncation.
- **`LLMClient`** (contract in `core.interfaces`) — a thin, swappable seam over
  the AI provider so the concrete vendor is injectable and mockable.
- **`HttpLLMClient`** — an OpenAI-compatible (`/chat/completions`) client over
  `httpx`, single-attempt (no retry), Bearer-authenticated, wrapping every
  transport/HTTP failure into a credential-free `LLMUnavailableError`. It accepts
  an injected `httpx.Client`, so its behavior is fully unit-tested via
  `httpx.MockTransport` with no network.
- **`StaticLLMClient`** — a deterministic `LLMClient` double for tests.

### 2. Fix generation now uses the AI layer (with graceful degradation)

`FixGenerator` gained an **optional injected** `AltTextGenerationService`
(`FixGenerator(alt_text_service=...)`):

- **No service injected** → the exact Milestone 0 behavior (filename heuristic).
  This is why every Milestone 0 property/test that constructs a bare
  `FixGenerator()` still passes unchanged.
- **Service injected** → `missing_alt_text` fixes carry real AI-generated alt
  text plus generation provenance. Business rules (§3.6) are enforced:
  - non-empty after trimming;
  - length ≤ 125 chars, via a **truncation-aware retry** (re-ask with a tighter
    budget) and, failing that, **word-boundary truncation** — never a mid-word
    hard cut;
  - **no-op skip**: if the proposal equals the current alt text, no fix is
    created (`None`);
  - a resolvable media id → auto-applicable fix with a write target; an
    unresolvable one → a report-only fix that still records the AI suggestion and
    provenance.
  - a **generation failure degrades gracefully** to a report-only fix whose
    reason records why — a model outage never crashes `POST /crawl`.

### 3. Persisted generation provenance

- `SuggestedFix` gained `generation_model` and `generation_confidence`
  (both optional; `None` for heuristic/report-only fixes and all existing M0
  rows).
- Additive, reversible migration
  `20240102_0002_add_generation_metadata.py` (`0002_generation_metadata`,
  revises `0001_initial`) adds the two nullable columns. Existing
  `fix_type: null` rows remain valid and readable; no data is dropped or retyped.
- `DigitalTwinRepository` persists and reconstructs the new fields.
- `GET /fixes` now returns the fields as part of the typed fix payload
  (verified by the integration test).

### 4. Opt-in wiring in the composition root

`api.container.build_default_subsystems` wires the LLM-backed service into the
`FixGenerator` **only when `ALT_TEXT_AI_ENABLED` is set**; otherwise the
Milestone 0 heuristic is used. New optional settings (all defaulted, so startup
never breaks and production behavior is unchanged until an operator opts in):

| Setting | Default | Purpose |
| --- | --- | --- |
| `ALT_TEXT_AI_ENABLED` | `false` | Turn on AI alt-text generation |
| `LLM_MODEL` | `gpt-4o-mini` | Model identifier (recorded as provenance) |
| `LLM_BASE_URL` | _unset_ | Provider base URL (also fits local servers) |
| `LLM_API_KEY` | _unset_ (secret) | Provider API key; held as `SecretStr`, redacted from logs |
| `LLM_MAX_OUTPUT_TOKENS` | `64` | Soft generation cap |

### 5. Tests (all green)

- `ai_generator`: deterministic service, LLM service (happy/context/cleaning/
  empty/unavailable/wrapped-exception), and `HttpLLMClient` against
  `httpx.MockTransport` (happy/no-retry/auth/timeout/transport/malformed/
  missing-base-url/credential-non-leak).
- `fix_generator`: the AI path (resolvable, unresolvable-with-suggestion,
  graceful failure, no-op skip, over-length retry+truncation, service used only
  for `missing_alt_text`, input non-mutation).
- `digital_twin`: generation-metadata persistence round-trip.
- `api`: end-to-end crawl → `GET /fixes` (typed payload incl. provenance) →
  approve (publishes the AI text) → rollback (restores prior value), plus a
  crawl-survives-AI-failure test.

---

## Why M0 fixes were "report-only" in practice

The prompt states that before Milestone 1 every fix was `fix_type: null` /
`auto_applicable = 0`. That matches the **live** pipeline: the Crawler parses
HTML and cannot know a WordPress `media_id`, so it leaves every image's
`media_id = None`. The Fix_Generator only produces an auto-applicable
(publishable) alt-text fix when a `media_id` is resolvable, so a real crawl
yielded report-only fixes. (Milestone 0 property tests and the e2e harness
inject/resolve a `media_id` explicitly to exercise the auto-applicable branch.)
Milestone 1 makes the *content* real; resolving `media_id`s from live markup
remains a separate follow-up (see below).

---

## Intentional deviations from the prompt (and why)

The prompt's §3 describes a lifecycle with distinct `published` / `verified` /
`closed` states and separate `POST /fixes/{id}/publish` and
`POST /fixes/{id}/verify` endpoints. This codebase already implements a
governed publish/rollback flow with a **different, protected state machine**, and
the prompt itself (§11 "Out of scope") forbids changing that state machine beyond
adding `failed`/`rejected` and forbids redesigning existing subsystems. Those two
instructions conflict, so — per the prompt's own guardrails and its
"do not redesign the architecture / do not replace existing abstractions"
directive — the existing flow was preserved:

- **Publish is the governed approval of an auto-applicable fix.** In this system
  `GovernanceService.approve_fix` reads the live BEFORE value, writes the fix's
  value to WordPress via the Publishing_Adapter, and transitions
  `pending → applied` — this *is* the publish step. There is no separate
  `approved`-but-unpublished state for auto-applicable fixes, so a standalone
  `/publish` endpoint cannot be added without changing `approve` (which would
  break the Milestone 0 governance property tests).
- **Rollback already exists** (`POST /fixes/{id}/rollback`) and restores the
  audited BEFORE value (`applied → rolled_back`).
- **Verify**: the loop's verification is exercised by the rollback/BEFORE-value
  audit rather than a dedicated `/verify` endpoint + `verified`/`closed` states,
  which §11 places out of scope.
- **`auto_applicable` semantics**: here it means "has a concrete machine write
  that Governance applies at approval time," not "auto-publish without approval."
  Approval is still always required — there is **no unattended publish path**,
  which satisfies the prompt's core rule that nothing reaches the site without
  approval.

The authoritative model/migration parity check (`alembic autogenerate` producing
an empty diff) still fully guards the schema; the one Milestone 0 structural test
that hard-coded the single initial-migration file was generalized to validate the
whole migration chain (a strengthening, not a weakening).

---

## Stubbed / pending

- **`TODO(llm-vendor-integration)`** in `ai_generator/llm.py`: `HttpLLMClient`
  targets the generic OpenAI-compatible schema and is verified only against a
  mock transport in this milestone; it has not been validated against a live
  provider account, and no provider credentials are configured in this
  environment. It never fakes success — with no reachable provider it raises
  `LLMUnavailableError`, and the Fix_Generator then degrades to a report-only fix.
- **`media_id` resolution from live markup** is still not implemented in the
  Crawler, so live AI alt-text fixes are report-only (carrying the suggestion)
  until a `media_id` is resolved. This is orthogonal to generation and is the
  natural next step to make live AI fixes auto-applicable.

---

## What the next fix types inherit from this foundation

Adding `update_meta_description`, `update_page_title`, `update_schema`, or
`update_slug` reuses this structure with minimal new surface:

1. Add a sibling generation service contract/impl in `ai_generator` (or a shared
   `ContentGenerationService`) behind the same injectable `LLMClient` seam.
2. Add the fix branch in `FixGenerator` (dispatch already keys on issue type),
   reusing the validation/graceful-degradation/provenance patterns established
   here.
3. Reuse the `generation_model` / `generation_confidence` columns already
   persisted on every fix.
4. Reuse the existing Governance approve/rollback flow and Publishing_Adapter
   write methods (`update_page_content` already exists for content-type fixes).

No changes to the crawl orchestration, the governance state machine, or the core
schema are required beyond adding the new generator and (if needed) a new
additive migration.
