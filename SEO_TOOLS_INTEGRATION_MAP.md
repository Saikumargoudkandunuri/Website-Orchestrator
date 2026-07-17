# SEO Tools Integration Map — Website Orchestrator

> Maps the Semrush / Ahrefs feature reference (July 2026) to existing Website
> Orchestrator packages, identifies gaps, and proposes a phased build order.
> Generated 2026-07-10. Updated 2026-07-10 — all six phases implemented.

## TL;DR

The project already contains **architecture-complete scaffolding** for all six
priority areas. The `engines` package implements the Milestone 3/4 engine
contract (ten engines behind a uniform `EngineAnalysisRequest`/`Result`
interface), and `growth` adds rank tracking + local SEO. The main work was
**filling service implementations** behind the existing models/interfaces and
**wiring real provider adapters** (currently `fake_provider` only).

**All six priorities are now implemented** with passing tests (20 engine tests
total). Provider-dependent fields remain honestly flagged via `data_source` /
`data_completeness` so real API adapters can be dropped in without logic changes.

- **P1 Technical SEO** — Health Score (0–100), hreflang, CWV, mixed content, dup content, site aggregation, change detection
- **P2 Keyword Intelligence** — difficulty/volume, SERP features, gap analysis (missing/weak/strong/untapped/unique), pillar/cluster plan
- **P2 Rank Tracking** — daily capture, change alerts, visibility/SOV, SERP features, rank distribution
- **P3 Backlink Monitoring** — authority score, toxicity scoring (0–100), new/lost detection, disavow generator
- **P4 Content Optimization** — content brief generator, topic clusters, freshness monitoring
- **P5 Competitive Intelligence** — traffic estimation, comparison, keyword/backlink gap finder
- **P6 AI Visibility / GEO** — brand mentions, share of voice, citation sources, schema readiness

---

## 1. Feature → Package Matrix

| Reference Feature | Priority | Status | Package / Module | Notes |
|---|---|---|---|---|
| Site Audit (140+ checks) | P1 | ✅ Built | `engines/technical_seo` | Per-page checks + Health Score |
| Health Score (0–100) | P1 | ✅ Built | `technical_seo/services` `health_score()` | Weighted severity penalty |
| Issue severity (Error/Warn/Notice) | P1 | ✅ Built | `technical_seo/models` `FindingSeverity` | CRITICAL/HIGH/MEDIUM/LOW/INFO |
| Scheduled crawl + change detection | P1 | 🟡 Partial | `technical_seo/services` `detect_crawl_changes()` | Needs scheduler wrapper |
| Core Web Vitals (LCP/INP/CLS) | P1 | ✅ Built | `checks_performance.py` | Via PageSpeed-style data |
| Orphan page detection | P1 | ✅ Built | `checks_links.py` `check_orphan_page` | From `internal_seo.orphan_page` |
| Redirect chain analyzer | P1 | ✅ Built | `checks_links.py` `check_redirect_chain` | ≥3 hops flagged |
| Hreflang validator | P1 | ✅ Built | `checks_international.py` | Value + return-tag checks |
| Keyword difficulty + volume dashboard | P2 | ✅ Built | `engines/keyword_intelligence` | `DifficultyEstimate` + volume |
| Rank tracking (daily) | P2 | ✅ Built | `growth/rank_tracking` | Append-only time series + scheduler |
| Rank change alerts | P2 | ✅ Built | `growth/rank_tracking` `RankingChange` | Significance detection done |
| SERP feature tracking | P2 | ✅ Built | `keyword_intelligence` `SerpFeature` + `rank_tracking` `serp_features` | Owned-feature tracking |
| Keyword gap analysis | P2 | ✅ Built | `keyword_intelligence` `KeywordGapItem` | missing/weak/strong/untapped/unique |
| Content cluster / pillar planner | P2 | ✅ Built | `keyword_intelligence` `PillarClusterPlan` | Cluster→pillar mapping |
| Referring domain count over time | P3 | 🟡 Partial | `engines/backlink_intelligence` | Provider-dependent; count available |
| New/lost backlink alerts | P3 | ✅ Built | `backlink_intelligence` `new/lost_backlinks` | Diff vs previous crawl |
| Authority Score equivalent | P3 | 🟡 Partial | `backlink_intelligence` `authority_score` | Mean of RD scores; null on fake |
| Toxic link flagging | P3 | ✅ Built | `backlink_intelligence` `ToxicLinkFlag` | 0–100 score + band (§3.3) |
| Disavow file generator | P3 | ✅ Built | `backlink_intelligence` `build_disavow`/`render_disavow_file` | Google Disavow .txt |
| SEO content scoring | P4 | ✅ Built | `seo_scoring` + M2 ContentScore | 8-axis transparent scoring |
| Content brief generator | P4 | ✅ Built | `content_intelligence` `generate_brief` | Top-10 SERP brief (§1.6.3) |
| Topic cluster visualization | P4 | ✅ Built | `keyword_intelligence` `KeywordCluster` | Cluster data + pillar plan |
| Content freshness monitoring | P4 | ✅ Built | `content_intelligence` `FreshnessStatus` | 12-month stale flag |
| Domain traffic estimation | P5 | 🟡 Partial | `competitor_intelligence` `estimated_traffic` | Provider-dependent |
| Keyword overlap / gap vs competitors | P5 | ✅ Built | `competitor_intelligence` `KeywordGap` + `comparison` | Side-by-side + gap |
| Top pages comparison | P5 | ⚡ Skip | Reference marks `[SKIP — CMS]` | GA/Search Console covers |
| Backlink gap finder | P5 | ✅ Built | `competitor_intelligence` `BacklinkGapItem` | Domains linking to rivals not us |
| Brand mention in AI outputs | P6 | ✅ Built | `ai_visibility` `AiMention` + `share_of_voice` | New engine module |
| Schema completeness for LLM citation | P6 | ✅ Built | `ai_visibility` `SchemaReadiness` | GEO-readiness score |
| AI traffic source tracking | P6 | 🟡 Partial | `ai_visibility` `ai_traffic_estimate` | Needs analytics integration |

---

## 2. What Exists Today (verified)

### `packages/engines/engines/` — 10 engines behind uniform contract
- **technical_seo** — ✅ fully implemented (checks + Health Score + aggregation + change detection)
- **keyword_intelligence** — ✅ implemented (gap analysis, SERP features, pillar plan, difficulty/volume)
- **backlink_intelligence** — ✅ implemented (toxicity scoring, new/lost, disavow generator)
- **competitor_intelligence** — ✅ implemented (comparison, keyword/backlink gap, traffic estimation)
- **content_intelligence** — ✅ implemented (brief generator, freshness, topic clusters)
- **seo_scoring** — ✅ implemented; consumes technical Health Score
- **ai_visibility** — ✅ NEW engine (brand mentions, SOV, citation sources, schema readiness)
- **site_architecture, topical_authority, opportunity, recommendation** — present in registry

### `packages/growth/growth/` — business-layer SEO
- **rank_tracking** — `RankingSnapshot` (append-only), `RankingChange`, `TrackedKeyword`
- **local_seo** — NAP consistency, GBP optimization, citation management
- **outreach** — link-building outreach scaffolding
- **content_optimization, analytics_intelligence, reputation_management** — present

### `packages/crawler/` — polite same-domain crawler
- BFS crawl, robots.txt honoring, redirect-chain recording, link-status probing
- Feeds the Knowledge Object that engines analyze

### `packages/api/` — FastAPI app + container + orchestration
- Ready to expose engine outputs as endpoints

---

## 3. Phased Build Order (recommended)

### Phase A — Complete Priority 1 (DONE this session)
- [x] Health Score (0–100)
- [x] hreflang, CWV, mixed content, duplicate content checks
- [x] Site-level aggregation (`SiteTechnicalReport`)
- [x] Crawl change detection
- [ ] Scheduled re-crawl wrapper (cron/celery) around `detect_crawl_changes`
- [ ] API endpoint exposing `SiteTechnicalReport` + trend

### Phase B — Priority 2 (Keyword Intelligence)
- [ ] Real provider adapter for `keyword_intelligence` (DataForSEO cheapest)
- [ ] `KeywordGapService` computing Missing/Weak/Strong/Untapped/Unique vs competitors
- [ ] SERP feature tracking from provider SERP snapshots
- [ ] Content cluster visualization endpoint

### Phase C — Priority 3 (Backlink Monitoring)
- [ ] Real backlink provider adapter (Ahrefs/Majestic)
- [ ] Authority Score computation
- [ ] Toxicity scoring (45+ markers → 0–100)
- [ ] **Disavow file generator** (`domain`/`URL` level → `.txt`)

### Phase D — Priority 4–6 (Content, Competitive, GEO)
- [ ] Content brief generator (top-10 SERP analysis)
- [ ] Content freshness monitor
- [ ] Competitor traffic estimation adapter
- [ ] Brand Radar (AI visibility) module
- [ ] Schema GEO-readiness checker

---

## 4. Provider Integration Strategy

All provider-dependent data flows through
`engines/shared/provider_abstraction/seo_data_provider_interface.py`
(`CompetitorDataProvider`, `BacklinkDataProvider` protocols). Today only
`fake_seo_data_provider.py` is registered. To go live:

1. Implement `AhrefsDataProvider` / `SemrushDataProvider` / `DataForSEOProvider`
   against the protocols — no engine code changes needed.
2. Register via the existing `wiring.py` container (config-driven swap).
3. Set `data_completeness` honestly per the §4.5 pattern so SEO Scoring stays
   transparent.

Recommended cheapest path: **DataForSEO** for SERP/keyword/rank, **Google
Search Console API** (free) for real rankings + index coverage, **Google
PageSpeed Insights API** (free) for CWV, **Ahrefs/Majestic** (credits) for
backlinks.

---

## 5. Test Coverage Added

`packages/engines/tests/test_technical_seo_priority1.py` (9 tests, passing):
- Health Score perfect / penalized / clamped
- `analyze()` populates `health_score`
- hreflang invalid value flagged
- Core Web Vitals poor LCP flagged
- mixed content flagged
- site aggregator report (severity + category breakdown)
- crawl change detection (resolved issues + health delta)

Run: `.\.venv\Scripts\python.exe -m pytest packages/engines/tests/test_technical_seo_priority1.py -q`