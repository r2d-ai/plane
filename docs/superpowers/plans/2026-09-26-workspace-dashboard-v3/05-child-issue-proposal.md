# Proposed Child-Issue Split (for Alex to create)

> Alex said: "Tao sẽ tự tạo child issue triển khai (Coda backend / Pixel UI) từ plan của Anna — tuần tự, không đụng code song song 2 owner."
> So each proposed child here is one owner, scoped tight, blocked-by the previous one.

## Dependency graph

```
RD-477 (Coda, freeze + pin tests)        — Phase A backend slice
   │
RD-478 (Pixel, freeze + i18n banner)     — Phase A frontend slice        [parallel with RD-477]
   │
RD-479 (Pixel, extract renderers)        — Phase B frontend              [after RD-478]
RD-480 (Coda, contract + perf proof)     — Phase B/C backend             [after RD-479, parallel with RD-481]
   │
RD-481 (Pixel, build v3 dashboard)       — Phase C frontend (main work) [after RD-479]
RD-482 (Pixel, cutover route)            — Phase C frontend cutover      [after RD-481]
   │
RD-483 (Pixel, delete builder UI)        — Phase D                       [after RD-482]
RD-484 (Coda, remove builder APIs+models) — Phase E (incl. migration)   [after RD-480 + RD-483]
   │
RD-485 (Doca, docs + env + spec status)  — Phase F                       [after RD-483 + RD-484]
```

Notes on the graph:
- **RD-479 swapped to Pixel frontend**: Phase B is now frontend-only (renderer extraction). Backend batch work is its own issue (RD-480) that runs after.
- **RD-480 spawned**: B/C backend contract + perf proof on the existing `/analytics/v2/batch/` endpoint. No new module, no extract — `/analytics/v2/batch/` (`apps/api/plane/app/urls/analytic.py:60`) and `MAX_BATCH_QUERIES=20` (`apps/api/plane/analytics/v2/query.py:64`) already cover the batch contract.
- **RD-482 is Pixel, not Coda**: cutover is just flipping the route after RD-481 ships and the flag flips. Trivial code change, big user impact — kept separate so the diff is reviewable in isolation.
- **RD-485 is Doca**: only docs + env comment + spec status tag. Pixel + Coda are done by then.

All in flight serial on any single owner; only `RD-477` and `RD-478` run in parallel because they touch disjoint files (Coda's freezes are in `apps/api/plane/`, Pixel's are in `apps/web/`).

## Proposed issues

### RD-477 — Phase A backend freeze + V2 pin tests  *(owner: Coda)*

- **Title:** "RD-477: Freeze builder API + pin V2 behavior with card snapshot tests (Phase A backend)"
- **Status:** todo
- **Stage:** 1
- **Parent:** RD-476
- **Description (paste):**

  > Freeze the old dashboard builder API surface (no new endpoints) and pin current Analytics V2 behavior before any refactor.
  >
  > Tasks (full detail in `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/02-phase-task-breakdown.md` Phase A):
  >
  > - A.2: Add frozen banners to every view in `apps/api/plane/app/views/dashboard/base.py`
  > - A.3: Confirm `WORKSPACE_DASHBOARDS` flag is documented at `apps/api/plane/settings/common.py:634` and `apps/api/.env.example:88-89`; update operator docs in `deployments/{aio,cli,kubernetes}/community/README.md`
  > - A.4: Add `apps/api/plane/tests/unit/analytics_v2/test_card_snapshots.py` with one snapshot per card A–L (spec §7) — proves current V2 engine output is the baseline
  > - A.5: Land `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/PHASE-A-COMPLETE.md` summarizing the freeze
  >
  > Out of scope: no API removals, no model changes.
  >
  > Acceptance: full V2 test suite green; new card snapshot tests pass; PHASE-A-COMPLETE.md exists.

- **Acceptance:** V2 tests green; banner text present; PHASE-A-COMPLETE.md committed.
- **Estimate:** ~1 day.

### RD-478 — Phase A frontend freeze + i18n cleanup pass  *(owner: Pixel)*

- **Title:** "RD-478: Freeze builder UI + banner dashboard Shutdown notes (Phase A frontend)"
- **Status:** todo
- **Stage:** 1
- **Parent:** RD-476
- **Description (paste):**

  > Freeze the old dashboard builder UI: banner every component file that ships to delete in Phase D; trim i18n where it's obvious dead code (keep `dashboard_shell.title` — v3 needs it).
  >
  > Tasks:
  >
  > - A.1: Add freeze banners to files in `apps/web/core/components/dashboards/{detail,list}/`, `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx`, `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx`
  > - F.1 dry-run: grep `dashboard_shell.*` in 21 locale files, identify keys safe to drop without breaking live UI; do not delete yet (that's Phase D.8)
  >
  > Out of scope: no component deletes, no route changes.
  >
  > Acceptance: grep for the banner comment succeeds on every file listed; CSV of "drop-list i18n keys" attached to the PR.

- **Estimate:** ~1 day.

### RD-479 — Phase B frontend: extract renderers into Analytics V2 namespace  *(owner: Pixel)*

- **Title:** "RD-479: Extract dashboard renderers into analytics/v2/renderers namespace (Phase B frontend)"
- **Status:** todo
- **Stage:** 2
- **Parent:** RD-476
- **Blocked by:** RD-478
- **Description (paste):**

  > Move generic renderer code out of `apps/web/core/components/dashboards/widgets/` into `apps/web/core/components/analytics/v2/renderers/` so the new dashboard can mount them directly. Behavior must be identical.
  >
  > Tasks:
  >
  > - B.1: move `truncation-banner.tsx`; update v2 barrel
  > - B.2: extract 9 renderers (`number`, `gauge`, `bar`, `line`, `pie`, `donut`, `matrix`, `aggregate-table`, `work-item-table`) from `analytics-widget.tsx`; add render-equality test
  > - B.3: move `widget-drilldown-drawer.tsx` next to `insight-drilldown.tsx`
  > - B.4: refactor `analytics-data.ts` to call `/analytics/v2/batch/`
  >
  > Acceptance: `apps/web/tests/dashboards/dashboard-widgets.render.test.tsx` still green; render-equality test green; bundle split by renderer kind.

- **Estimate:** ~2 days.

### RD-480 — Phase B/C backend: contract + perf proof on existing `/analytics/v2/batch/`  *(owner: Coda)*

- **Title:** "RD-480: Verify /analytics/v2/batch/ contract + 12-card perf snapshot (B/C backend)"
- **Status:** backlog
- **Stage:** 2
- **Parent:** RD-476
- **Blocked by:** RD-479
- **Description (paste):**

  > No extract, no new module. Verify the existing `/analytics/v2/batch/` endpoint (`apps/api/plane/app/urls/analytic.py:60`, `AnalyticsV2BatchEndpoint` at `apps/api/plane/app/views/analytic_v2.py:187`, with `MAX_BATCH_QUERIES=20` cap at `apps/api/plane/analytics/v2/query.py:64`) handles the v3 dashboard's 12-card payload + global scope, and capture a perf baseline.
  >
  > Tasks:
  >
  > - Add `apps/api/plane/tests/contract/app/test_analytics_v2_batch_parity.py` that replays 5 saved dashboard payloads through `/dashboards/{id}/data/` and `/analytics/v2/batch/` and asserts shape equality (excluding `request_id`). Confirms §11.1 migration contract before Phase C flips the route.
  > - Extend `apps/api/plane/tests/perf/test_page_analytics_perf.py` with `test_batch_12_card_dashboard[small|medium|large]` that sends all 12 card queries plus a global scope and asserts the P95 targets from `04-perf-plan.md`.
  > - Add `apps/api/plane/management/commands/perf_dashboard_v3.py` that wraps the perf test and writes `apps/api/plane/tests/perf/baselines/v3-batch-<date>.json` for regression tracking.
  > - Coordinate with Pixel on the `batch-composer.ts` payload shape (C.6) so the contract test covers the v3 payload exactly.
  >
  > **Out of scope**: no extraction, no new endpoint, no deprecation shim.
  >
  > Acceptance: parity test green; perf snapshot exists for small/medium/large and meets `04-perf-plan.md` targets; baseline JSON committed.

- **Estimate:** ~2 days (parallel with Pixel RD-481 from C.6 onward).

### RD-481 — Phase C: build v3 workspace dashboard (the heavy lift)  *(owner: Pixel)*

- **Title:** "RD-481: Build fixed v3 workspace dashboard (12 cards, batch call, prefs) — Phase C frontend"
- **Status:** todo
- **Stage:** 3
- **Parent:** RD-476
- **Blocked by:** RD-479, RD-480
- **Description (paste):**

  > Ship the fixed Workspace Dashboard per `docs/workspace-dashboards-analytics-v2-spec.md` §3–§9. Single route, 12 cards, fixed layout, per-user preferences in localStorage.
  >
  > Tasks:
  >
  > - C.1: card-registry.ts (12 cards A–L)
  > - C.2: dashboard-shell.tsx (responsive sections)
  > - C.3: global-controls.tsx
  > - C.4: card-controls.tsx
  > - C.5: dashboard-preferences.store.ts
  > - C.6: batch-composer.ts
  > - C.7: wire `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/page.tsx` to v3 shell
  > - C.8: redirect `/dashboards/:id` → `/dashboards`
  > - C.10: smoke test
  > - C.11: extend route-guard
  >
  > Out of scope: no old-builder UI removal yet (Phase D).
  >
  > Acceptance: v3 route renders all 12 cards; global filter triggers one batch request; preferences survive reload; smoke test green; per-card control updates only that card's slice of the batch.

- **Estimate:** ~5–6 days (this is the largest single issue).

### RD-482 — Phase C frontend: cutover route `/dashboards` after flag  *(owner: Pixel)*

- **Title:** "RD-482: Cutover /dashboards route to v3 fixed dashboard + flip flag (Phase C-2 frontend)"
- **Status:** backlog
- **Stage:** 3
- **Parent:** RD-476
- **Blocked by:** RD-481
- **Description (paste):**

  > Now that v3 dashboard builds locally and the flag is on for staging, flip the route. The actual diff is small — the risk is in the user-visible change, not the code.
  >
  > Tasks:
  >
  > - C.8: redirect `/dashboards/{any-id}` → `/dashboards` (delete directory or client-side redirect)
  > - Wire `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/page.tsx` to v3 shell (already done in RD-481 C.7; verify the prod build now lands the v3 bundle)
  > - Flip `WORKSPACE_DASHBOARDS` default off → on only after Alex/Huy sign off on staging. Confirm in `apps/api/.env.example:88-89` and `packages/types/src/instance/base.ts:69-70` doc
  > - Smoke test on staging workspace, verify kill-switch redirect still works (`workspace-dashboards-kill-switch.render.test.tsx`)
  >
  > Acceptance: v3 dashboard renders as default; legacy `/dashboards/{id}` redirects; flag flip is documented; staging roll-out signed off.

- **Estimate:** ~1 day (mostly staging validation, not code).

### RD-483 — Phase D: remove builder UI  *(owner: Pixel)*

- **Title:** "RD-483: Delete old dashboard builder UI + i18n keys (Phase D)"
- **Status:** todo
- **Stage:** 4
- **Parent:** RD-476
- **Blocked by:** RD-481
- **Description (paste):**

  > Now that v3 ships and the old route is gone, delete every builder UI file and its tests.
  >
  > Tasks:
  >
  > - D.1–D.7: delete files in `apps/web/core/components/dashboards/{list,detail}/`, `widgets/markdown-placeholder.tsx`, `layout.ts`, `constants.ts`; delete `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx`; delete `apps/web/core/store/dashboard.store.ts` and `use-dashboard.ts`; delete `apps/web/core/services/dashboard.service.ts`
  > - D.8: drop builder i18n keys in all 21 locales; keep `dashboard_shell.title` for v3 header
  > - D.9: nav label cleanup
  >
  > Acceptance: no file under `apps/web/core/components/dashboards/` outside `v3/`; `apps/web/tests/dashboards/` references only v3 paths; `pnpm test` green; `pnpm build` green; bundle ≤ 200 KB gzipped (perf plan 04).

- **Estimate:** ~1 day.

### RD-484 — Phase E: remove builder APIs, models, services  *(owner: Coda)*

- **Title:** "RD-484: Delete old dashboard endpoints + models + service (forward migration 0135) — Phase E"
- **Status:** todo
- **Stage:** 5
- **Parent:** RD-476
- **Blocked by:** RD-480, RD-482
- **Description (paste):**

  > Strip the backend builder surface. This is the only step that drops DB tables — needs staging validation before merge.
  >
  > Tasks:
  >
  > - E.1–E.5: trim `apps/api/plane/app/urls/dashboard.py`, views, permissions, serializers; delete `dashboard_analytics.py` (only 2 consumers, both deleted in E.2/E.3); delete `apps/web/core/services/dashboard.service.ts`
  > - E.6: write `apps/api/plane/db/migrations/0135_drop_dashboard_tables.py` (drop 5 tables); include rollback
  > - E.7–E.8: remove the 5 models from `db/models/dashboard.py` and the imports in `db/models/__init__.py`
  > - E.9–E.10: clean up `tests/contract/app/test_dashboard_app.py` (replace with 410-Gone assertions if any URL remains), delete `test_dashboard_model.py` and `test_dashboard_serializer_acl.py`
  >
  > **Hard gate:** Alex/Huy review the 0135 migration script before staging apply.
  >
  > Acceptance: 0135 applies cleanly on staging; rollback script also tested; no Django check errors; V2 test suite still green; Analytics V2 contract tests pass.

- **Estimate:** ~2 days.

### RD-485 — Phase F: docs + env comment + spec status  *(owner: Doca)*

- **Title:** "RD-485: v3 dashboard final docs + env comment refresh + spec status tag (Phase F)"
- **Status:** backlog
- **Stage:** 6
- **Parent:** RD-476
- **Blocked by:** RD-483, RD-484
- **Description (paste):**

  > Pixel and Coda finished their code work. Only loose-end docs and config comments remain. Doca owns this entirely.
  >
  > Tasks:
  >
  > - F.2: update operator READMEs (`deployments/aio/community/README.md`, `deployments/cli/community/README.md`, `deployments/kubernetes/community/README.md`) — one-line flag description in each
  > - F.3: refresh `apps/api/.env.example:88-89` comment to reflect v3 (no longer "kill switch")
  > - F.7: refresh `packages/types/src/instance/base.ts:69-70` doc comment
  > - F.8 (Anna assist): add "Implementation status: Phase X" tag to `docs/workspace-dashboards-analytics-v2-spec.md`
  > - F.9 (Anna assist): land `PHASE-F-COMPLETE.md`
  >
  > **Already done in earlier phases (do NOT redo here):**
  > - F.4 / F.5 (test file replacements) → folded into RD-483 (Pixel) per Phase C/F scope decision
  > - F.6 (batch smoke in v2 contract tests) → folded into RD-480 (Coda)
  > - F.1 (i18n cleanup) → folded into RD-483 (Pixel)
  >
  > Acceptance: zero references to "kill switch" or old builder docs anywhere in `deployments/` or `apps/api/.env.example`; spec status tag in place.

- **Estimate:** ~1 day.

## Order of execution (for Alex to assign)

1. Create RD-477 + RD-478 → assign Coda + Pixel in parallel (stage 1).
2. After RD-478 lands: create RD-479 → assign Pixel (stage 2 frontend).
3. After RD-479 lands: create RD-480 → assign Coda (stage 2 backend, runs in parallel with RD-481).
4. After RD-479 lands: create RD-481 → assign Pixel (stage 3 build).
5. After RD-481 lands: create RD-482 → assign Pixel (stage 3 cutover).
6. After RD-482 lands: create RD-483 → assign Pixel (stage 4).
7. After RD-480 + RD-483 land: create RD-484 → assign Coda. **Migration review gate before merge.**
8. After RD-483 + RD-484 land: create RD-485 → assign Doca (stage 6).

## Common fields to set on every child

- `project: 09b1849e-84ec-4b8b-a3a8-e1d800c5f381` (Plane project — same as RD-475)
- `priority: high` (RD-481 may be `urgent` since it's the longest single owner run)
- `labels: ["dashboard-v3-rebuild"]` (suggested)
- Always reference the parent in the body: `Parent: RD-476 → RD-475`
- Always reference the spec: `Spec: docs/workspace-dashboards-analytics-v2-spec.md`
- Always reference this plan folder: `Plan: docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/`
