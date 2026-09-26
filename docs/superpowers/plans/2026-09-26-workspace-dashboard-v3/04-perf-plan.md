# Performance Plan — v3 Workspace Dashboard

> Goal: ship the fixed dashboard at parity with or better than the legacy builder for typical workspaces, with measurable ceilings.
> Reference: `apps/api/plane/tests/perf/test_page_analytics_perf.py` (302 lines) is the existing benchmark harness — extend it, do not replace.

## Targets

P50 / P95 / P99 latency on `/analytics/v2/batch/` when sending a single batch with **all 12 cards (A–L)** plus their global scope:

| Workspace size | P50 | P95 | P99 | Notes |
|----------------|-----|-----|-----|-------|
| Small: ≤ 1k work items across ≤ 5 projects | ≤ 200 ms | ≤ 400 ms | ≤ 800 ms | One DB transaction |
| Medium: ≤ 50k work items across ≤ 25 projects | ≤ 600 ms | ≤ 1.2 s | ≤ 2.0 s | Partial aggregation per metric |
| Large: ≤ 500k work items across ≤ 100 projects | ≤ 2.0 s | ≤ 4.0 s | ≤ 6.0 s | Cap-enforced, may include truncation warnings |

**Card-budget check (Phase C acceptance gate):** no single card may exceed **3 s P95** on the medium dataset. If it does, that card is broken by spec (must use a lighter dimension or roll up).

**Frontend TTI (Time to Interactive) on `/dashboards`:**
- Cold load: ≤ 2.0 s on a 4× CPU-throttled Lighthouse run
- Initial card render: ≤ 500 ms after batch response
- Preference restore: ≤ 100 ms (localStorage read)

## Backend — measurement & optimization

### Measurement

1. **Extend `apps/api/plane/tests/perf/test_page_analytics_perf.py`** with a new test `test_batch_12_card_dashboard[small|medium|large]` that sends all 12 card queries plus a global scope in a single batch and asserts the P95 targets above. Use the existing fixtures in the file (don't duplicate data generation logic).
2. **Add a CLI script** at `apps/api/plane/management/commands/perf_dashboard_v3.py` that wraps the perf test and writes results to `apps/api/plane/tests/perf/baselines/v3-batch-<date>.json` so we can track regressions over time.
3. **Existing batch cap:** `apps/api/plane/analytics/v2/query.py:MAX_BATCH_QUERIES` (already imported in `test_dashboard_app.py`). Phase B.4 keeps this cap; Phase C.6 enforces it from the v3 composer.

### Optimization opportunities (no premature optimization — only what the perf test points to)

| Bottleneck candidate | Where | Mitigation |
|----------------------|-------|------------|
| Repeated ACL subquery per card | `apps/api/plane/analytics/v2/acl.py` | Hoist ACL CTE to outer query; pass scoped queryset into the batch composer (`B.4`) |
| Date group recomputed per metric | `apps/api/plane/analytics/v2/metrics.py` | Materialize a per-card date-bucket CTE shared across metrics |
| Workload allocation matrix (cards H, I) | `apps/api/plane/analytics/v2/allocation.py` | Pre-aggregate per-assignee base set once, then split |
| Truncation warnings recompute count | `apps/api/plane/analytics/v2/normalization.py` | Cache total count per `(scope, dimension)` for the batch lifetime |
| 12 cards × N filters | `apps/api/plane/analytics/v2/filters.py` | Reuse the SQL builder across cards; only re-bind filter values |

### Caching (deferred, not in P0)

- Per-user preference store is localStorage only (§15.1). No server-side caching of dashboard state.
- Analytics V2 query result cache **only if** perf test on large workspace fails the P99 target. Not on the P0 path.

## Frontend — measurement & optimization

### Measurement

1. **Add a render-perf test** at `apps/web/tests/dashboards/v3/perf.render.test.tsx` that mocks the batch endpoint and asserts:
   - First paint of the route under 500 ms (jsdom + fake timers; assert that all 12 cards mount within 2 RAFs after batch resolves)
   - Re-render on global-filter change under 200 ms
   - No layout thrash (no more than 1 forced reflow per filter change — use a `PerformanceObserver` mock)
2. **Lighthouse CI config** at `apps/web/.lighthouserc.json` (new) that runs the dashboard route on a built bundle. Track the same metrics across PRs.
3. **Bundle size budget**: the dashboard v3 JS chunk must be ≤ 200 KB gzipped (extract renderers in B.2 enables code-splitting per renderer kind).

### Optimization opportunities

| Bottleneck candidate | Where | Mitigation |
|----------------------|-------|------------|
| 12 cards × 12 fetch hooks in detail root | `apps/web/core/components/dashboards/detail/dashboard-detail-root.tsx` (old) | Replace with **single** batch call from C.6 |
| Re-render cascade on filter change | `analytics-widget.tsx:572` after extraction (B.2) | Wrap each card body in `React.memo` keyed on `(queryHash, responseSlice)` |
| SVG chart inline | renderers (post B.2) | Lazy-import renderer chunks so each `<Renderer kind>` loads on demand |
| Date-group switch | global controls (C.3) | Throttle to 150 ms; debounce on the user input |
| Truncation banner flicker | renderers (B.1) | Show banner only when `truncated === true`, never on first paint |

## Data-budget observability

- **Backend:** every `/analytics/v2/batch/` response already carries a `warnings` array. Make sure the v3 composer surfaces these in the UI (the existing `truncation-banner.tsx` already does this once extracted).
- **Server log:** add a counter `analytics_v2_batch_card_count_total` (cardinality ≤ 12) so we can see distribution in dashboards.
- **Client log:** when a card returns `truncated: true`, log `console.warn` with card id so QA can grep production logs.

## Load testing (post-Phase C, before Phase E)

- Spin up staging with `WORKSPACE_DASHBOARDS=1` and seed 3 workspaces (small/medium/large).
- Drive 10 RPS of `/analytics/v2/batch/` payloads via `apps/api/plane/tests/perf/loadtest_locustfile.py` (new file, mirror existing locustfile pattern if any).
- Capture DB query counts via `django.test.utils.CaptureQueriesContext`; assert no card pulls more than 20 queries.

## Acceptance criteria summary

A v3 ship is "perf-ready" when:
- Backend: P95 ≤ targets above on all three workspace sizes.
- Backend: zero `QuerySet.extra(...)` calls remain in the request path (per V2 §14 audit).
- Frontend: TTI ≤ 2.0 s on Lighthouse mobile profile.
- Frontend: bundle ≤ 200 KB gzipped.
- Frontend: re-render budget holds on a 5× throttled CPU profile.
- Logs show truncation warnings when expected, no warnings when not.

## What this perf plan is NOT

- Not a server-side render plan. v3 is client-rendered with React Router 7, same as the rest of the workspace app.
- Not a CDN plan. The bundle lives on the existing plane web app's static pipeline.
- Not a multi-dashboard plan. Single workspace dashboard per §3.1; multi-dashboard is out of scope.
