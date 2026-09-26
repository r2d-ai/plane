# Proposed Child-Issue Split (for Alex to create)

> Alex said: "Tao sẽ tự tạo child issue triển khai (Coda backend / Pixel UI) từ plan của Anna — tuần tự, không đụng code song song 2 owner."
> So each proposed child here is one owner, scoped tight, blocked-by the previous one.

## Dependency graph

```
RD-477 (Coda, freeze + pin tests)        — Phase A backend slice
   │
RD-478 (Pixel, freeze + i18n banner)     — Phase A frontend slice        [parallel with RD-477]
   │
RD-479 (Coda, extract batch to V2)       — Phase B backend               [after RD-477]
RD-480 (Pixel, extract renderers)        — Phase B frontend              [after RD-478, parallel with RD-479]
   │
RD-481 (Pixel, build v3 dashboard)       — Phase C frontend (main work) [after RD-479 + RD-480]
RD-482 (Coda, /analytics/v2/batch/ parity)— Phase C backend parity      [after RD-479, parallel with RD-481]
   │
RD-483 (Pixel, delete builder UI)        — Phase D                       [after RD-481]
RD-484 (Coda, remove builder APIs+models) — Phase E (incl. migration)   [after RD-481 + RD-482]
   │
RD-485 (Pixel+Coda, docs & tests)        — Phase F                       [after RD-483 + RD-484]
```

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

### RD-479 — Phase B backend: extract batch to Analytics V2  *(owner: Coda)*

- **Title:** "RD-479: Extract batch execution from dashboard to analytics/v2 + parity test (Phase B backend)"
- **Status:** todo
- **Stage:** 2
- **Parent:** RD-476
- **Blocked by:** RD-477
- **Description (paste):**

  > Move `apps/api/plane/utils/dashboard_analytics.py` → `apps/api/plane/analytics/v2/batch.py`. Refactor public surface to take `(queries[], global_scope)` instead of `dashboard_id`. Add parity test.
  >
  > Tasks:
  >
  > - B.4: move + refactor public API; keep `dashboard_analytics.py` as a deprecation shim
  > - B.5: add `apps/api/plane/tests/contract/app/test_analytics_v2_batch_parity.py` with 5 replay cases
  > - B.7: emit `DeprecationWarning` from old module
  >
  > Acceptance: parity test green; old endpoint still works (used by builder until Phase C migrates it); deprecation warning emitted; no test regressions in V2 unit suite.

- **Estimate:** ~2 days.

### RD-480 — Phase B frontend: extract renderers into Analytics V2 namespace  *(owner: Pixel)*

- **Title:** "RD-480: Extract dashboard renderers into analytics/v2/renderers namespace (Phase B frontend)"
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
  > - B.6: refactor `analytics-data.ts` to call `/analytics/v2/batch/`
  >
  > Acceptance: `apps/web/tests/dashboards/dashboard-widgets.render.test.tsx` still green; render-equality test green; bundle split by renderer kind.

- **Estimate:** ~2 days.

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

### RD-482 — Phase C backend parity confirmation  *(owner: Coda)*

- **Title:** "RD-482: Confirm /analytics/v2/batch/ parity for v3 dashboard payload (Phase C backend)"
- **Status:** todo
- **Stage:** 3
- **Parent:** RD-476
- **Blocked by:** RD-479
- **Description (paste):**

  > Verify the v3 dashboard's batch payload (12 cards + global scope + filters) round-trips correctly against `/analytics/v2/batch/`. No new endpoint expected — `/analytics/v2/batch/` already exists at `apps/api/plane/app/urls/analytic.py:60`.
  >
  > Tasks:
  >
  > - C.9: extend `apps/api/plane/tests/contract/app/test_analytics_v2_app.py` with a v3-shape batch case
  > - C.6 contract: confirm with Pixel that `batch-composer.ts` payload matches `AnalyticsQueryV2` schema
  >
  > Acceptance: contract test green; signed off in PR that Pixel can rely on the endpoint as-is.

- **Estimate:** ~1 day (mostly coordination + test writing).

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
- **Blocked by:** RD-481, RD-482
- **Description (paste):**

  > Strip the backend builder surface. This is the only step that drops DB tables — needs staging validation before merge.
  >
  > Tasks:
  >
  > - E.1–E.5: trim `apps/api/plane/app/urls/dashboard.py`, views, permissions, serializers; delete `dashboard_analytics.py` (replaced in RD-479); delete `apps/web/core/services/dashboard.service.ts`
  > - E.6: write `apps/api/plane/db/migrations/0135_drop_dashboard_tables.py` (drop 5 tables); include rollback
  > - E.7–E.8: remove the 5 models from `db/models/dashboard.py` and the imports in `db/models/__init__.py`
  > - E.9–E.10: clean up `tests/contract/app/test_dashboard_app.py` (replace with 410-Gone assertions if any URL remains), delete `test_dashboard_model.py` and `test_dashboard_serializer_acl.py`
  >
  > **Hard gate:** Alex/Huy review the 0135 migration script before staging apply.
  >
  > Acceptance: 0135 applies cleanly on staging; rollback script also tested; no Django check errors; V2 test suite still green; Analytics V2 contract tests pass.

- **Estimate:** ~2 days.

### RD-485 — Phase F: docs + tests + feature-flag cleanup  *(owner: Pixel + Coda split, lead by Pixel)*

- **Title:** "RD-485: Finalize v3 dashboard docs + tests + flag polish (Phase F)"
- **Status:** todo
- **Stage:** 6
- **Parent:** RD-476
- **Blocked by:** RD-483, RD-484
- **Description (paste):**

  > Wrap up loose ends: replace stale tests with v3 versions, refresh operator docs, polish flag docs.
  >
  > Tasks (Pixel unless noted):
  >
  > - F.1: drop remaining stale i18n keys (cleanup of D.8 leftovers)
  > - F.2 (Coda): update operator READMEs
  > - F.3 (Coda): refresh `apps/api/.env.example:88-89` comment
  > - F.4–F.5: replace 3 dashboard test files with v3 equivalents under `apps/web/tests/dashboards/v3/`
  > - F.6 (Coda): add v3 batch smoke to analytics v2 contract tests
  > - F.7: refresh `packages/types/src/instance/base.ts:69-70` doc comment
  > - F.8 (Anna): add "Implementation status: Phase X" tag to spec
  > - F.9 (Anna): land `PHASE-F-COMPLETE.md`
  >
  > Acceptance: zero references to deleted builder paths anywhere except git history; Lighthouse CI passes; `pnpm test` and `pytest` green; perf plan 04 acceptance criteria met.

- **Estimate:** ~1 day.

## Order of execution (for Alex to assign)

1. Create RD-477 + RD-478 → assign Coda + Pixel in parallel.
2. After RD-477 lands: create RD-479 → assign Coda.
3. After RD-478 lands: create RD-480 → assign Pixel.
4. After both RD-479 and RD-480 land: create RD-481 + RD-482 → assign Pixel + Coda in parallel.
5. After RD-481: create RD-483 → assign Pixel.
6. After both RD-481 + RD-482: create RD-484 → assign Coda. **Migration review gate before merge.**
7. After RD-483 + RD-484: create RD-485 → assign Pixel (lead) + Coda (backend slices).

## Common fields to set on every child

- `project: 09b1849e-84ec-4b8b-a3a8-e1d800c5f381` (Plane project — same as RD-475)
- `priority: high` (RD-481 may be `urgent` since it's the longest single owner run)
- `labels: ["dashboard-v3-rebuild"]` (suggested)
- Always reference the parent in the body: `Parent: RD-476 → RD-475`
- Always reference the spec: `Spec: docs/workspace-dashboards-analytics-v2-spec.md`
- Always reference this plan folder: `Plan: docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/`
