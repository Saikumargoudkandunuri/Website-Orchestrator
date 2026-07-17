# Website Orchestrator — The AI Digital Marketing Executive

This is the central, permanent architectural philosophy of Website Orchestrator.
Every milestone, engine, feature, endpoint, agent, and UI surface built from this
point onward MUST be evaluated against and serve this vision. It outranks
convenience, feature-count, and "just ship an SEO check" thinking.

If any future change conflicts with this document, this document wins — raise the
conflict explicitly rather than quietly diverging.

---

## 1. Identity — what this product IS

Website Orchestrator is **not an SEO tool** and **not merely an autonomous
maintenance system**. It is an **AI Digital Marketing Executive**: a full-time,
always-on marketing leader for every connected website.

The end state: the owner connects a WordPress site once, provides API keys (LLMs,
Search Console, Analytics, etc.), chooses a governance mode, and the platform then
**thinks, plans, executes, monitors, learns, and grows the business continuously**
— governed, auditable, reversible, and provider-agnostic.

It owns the **complete lifecycle** of a website's marketing, not just issue-fixing.

## 2. The litmus test (apply to every decision)

> **"Would an experienced Digital Marketing Executive think of doing this?"**

- If **yes** → Website Orchestrator should eventually support it, and the work
  should be designed to plug into the continuous reasoning loop (Section 5), not
  as a standalone utility.
- If the feature is a disconnected SEO gadget that a strategic marketing lead would
  never think in terms of → reconsider or reshape it.

Whenever building anything, also ask the questions the AI itself must ask:
what should I improve today; why is traffic/rankings changing; what content is
missing; which pages should be created, updated, merged, or removed; which
opportunities have the highest business impact.

## 3. Core principles (non-negotiable)

1. **Complete-lifecycle ownership.** The AI is responsible for discovering,
   planning, creating, optimizing, growing, monitoring, and reporting — not just
   remediation. Growth of the business is a first-class objective, not a side
   effect.
2. **Continuous reasoning loop, never isolated AI calls.** No feature ships as a
   one-off "call the LLM and return text." Every capability participates in the
   perpetual sense → analyze → prioritize → plan → govern → execute → verify →
   learn loop (Section 5).
3. **Governed autonomy.** Every action honors the site's governance mode
   (Advisory / Approval / Autonomous). Every action is **logged, reversible, and
   auditable**. Destructive or live-site-mutating actions never happen without the
   mode permitting them and (outside Autonomous) explicit human approval.
4. **Provider-agnostic intelligence.** The platform never hard-depends on one
   model or vendor. All LLM access goes through the AI gateway; users bring their
   own keys; the orchestration layer chooses the model per task.
5. **Prioritize by business impact / ROI.** Work is continuously ranked by expected
   business value, not by whatever check happens to be easiest to run.
6. **Explainability.** Every recommendation and action carries its reasoning —
   what, why, expected impact, and the evidence behind it.
7. **Learn from outcomes.** After acting, the AI verifies whether the metric moved
   and feeds the result back into memory/confidence so future decisions improve.
8. **Multi-tenant & multi-site by design.** Everything is scoped per tenant and
   per connected website; nothing assumes a single site.

## 4. Scope of responsibility (the DME capability surface)

The AI must continuously think about and, over time, be able to act on the full
marketing lifecycle. This list is illustrative, not exhaustive — the litmus test
in Section 2 governs additions.

- **Discovery & strategy:** new keyword opportunities; missing service, location,
  category, product, FAQ, comparison, pillar, and cluster pages; topical-authority
  building; content roadmaps and publishing calendars; seasonal and trending
  opportunities.
- **Content:** write and update blogs; create and refresh landing pages; expand
  thin content; refresh outdated pages and statistics; improve readability, EEAT,
  headings, schema, metadata, and internal linking; merge/prune weak pages.
- **Technical & health:** technical SEO, crawl health, broken links, redirects,
  structured data, Core Web Vitals, indexing.
- **Growth & authority:** backlink opportunities and link building; competitor
  monitoring; brand visibility; local SEO and Google Business Profile; reputation.
- **Measurement:** Search Console, Google Analytics, rankings, conversions (CRO),
  ROI tracking, and executive reporting that explains what was done and what's next.

## 5. The continuous reasoning loop (canonical architecture)

Every connected site runs this loop, on cadences, driven by the scheduler and the
orchestration layer:

```
SENSE      collect signals (crawl, GSC, GA4, CWV, rankings, competitors, backlinks, freshness)
ANALYZE    specialist agents reason over signals via the domain engines
PRIORITIZE rank opportunities by business impact / ROI into a living backlog
PLAN       the planner turns the top items into an executable action graph
GOVERN     the per-site mode + policy layer gates each action (Advisory/Approval/Autonomous)
EXECUTE    real tool handlers act (edit, publish, generate) — audited & reversible
VERIFY     did the target metric move?
LEARN      reflection updates memory/confidence so future decisions improve
```

Agents collaborate through a central orchestration layer (supervisor +
coordination + shared blackboard). Specialist agents are **executors bound to real
tools**, not isolated prompt calls.

## 6. Governance model

Three per-site modes, always enforced as the gate on every action:

- **Advisory** — recommendations only; no changes prepared.
- **Approval** — the AI prepares concrete changes; a human approves before they go
  live.
- **Autonomous** — the AI may publish, update, optimize, and maintain automatically
  within user-defined policies (risk thresholds, protected areas, budgets, rate
  limits).

In every mode: complete audit trail, full reversibility (rollback), and a
before/after record. Nothing touches a live site unless the site is connected and
reachable AND the mode permits the specific action.

## 7. Mandatory rules for every new engine / feature

A new capability is only "done" when it satisfies all of the following:

1. **Plugs into the loop** — it emits signals, contributes analysis, proposes
   prioritized actions, and/or executes actions within Section 5. It is not a
   standalone endpoint disconnected from orchestration.
2. **Is an executable tool** (when it can act) — registered with the agent runtime
   with a real handler, not mock output.
3. **Routes intelligence through the AI gateway** — no hard-coded provider/model.
4. **Passes through governance** — respects the site's mode; writes are logged and
   reversible.
5. **Is explainable** — surfaces reasoning, expected impact, and evidence.
6. **Records outcomes** — writes results back for verification and learning.
7. **Is tenant/site-scoped** — no single-site assumptions.

## 8. Anti-patterns (do not build these)

- A new "SEO checker" that returns a report and does nothing else.
- An LLM call wired directly into a page with no path into the loop or governance.
- A capability hard-coded to one AI provider or model.
- Any live-site mutation that bypasses governance, isn't logged, or can't be rolled
  back.
- Agents that only "chat" or "recommend" with no route to real, governed execution.
- Per-site logic that assumes exactly one website or one tenant.

## 9. New-work acceptance checklist

Before considering any feature complete, confirm:

- [ ] It answers "yes" to the DME litmus test (Section 2).
- [ ] It participates in the continuous reasoning loop (Section 5).
- [ ] It respects the three governance modes and is auditable + reversible.
- [ ] It uses the provider-agnostic AI gateway.
- [ ] It prioritizes by business impact and explains its reasoning.
- [ ] It records outcomes so the system can learn.
- [ ] It is multi-tenant / multi-site safe.

## 10. Grounding in the current codebase

This vision is already substantially scaffolded; new work should connect and
activate these rather than reinventing them:

- **Orchestration:** `agentic/agents/` (supervisor, coordination engine,
  blackboard, mission manager/monitor).
- **Plan/execute/reflect:** `agentic/` (goal, planning, runtime, reflection,
  memory) — runtime execution must move from mock to real tool handlers.
- **Continuous cadence:** `brain/scheduler`, `brain/decision`, brain
  automation-rules.
- **Website connection & governance modes:** `onboarding/` (encrypted WP
  credentials, capabilities, per-site `ai_enabled` / `automation_enabled` /
  `approval_mode`) + `governance/` (approve / reject / rollback / audit).
- **Provider-agnostic AI:** `ai/` gateway (multi-provider, cost-aware routing,
  telemetry, cache, rate-limit).
- **Domain capabilities to expose as tools:** `engines/`, `growth/`, `editing/`,
  `knowledge/`, `publishing_adapter/`.

The near-term engineering direction is: consolidate to one canonical stack, replace
mocked execution with real governed tool handlers, and stand up the continuous loop
— then expand the capability surface (Section 4) agent by agent.
