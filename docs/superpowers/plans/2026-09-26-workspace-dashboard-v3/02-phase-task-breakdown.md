# Phase A–F Task Breakdown

> Each task has a real file path. Owner column is Coda (backend) or Pixel (frontend).
> Migrations are only touched in Phase E, and only as new forward migrations.
> Spec reference in parentheses. Tests are mandatory acceptance gates.

## Phase A — Freeze the old builder product

**Goal:** No new code on the old builder surface; pin current V2 behavior with tests before refactoring.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| A.1 | Add a top-of-file banner to every REMOVE-file declaring it is frozen (no new features) | Pixel | All files in `apps/web/core/components/dashboards/{detail,list}/`, `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx`, `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx` | Banner present; CI grep finds banner on each |
| A.2 | Add a top-of-file banner to builder-only view methods declaring "frozen, do not extend" | Coda | All view classes in `apps/api/plane/app/views/dashboard/base.py` | Banner present; no new endpoints added in this phase |
| A.3 | Confirm `WORKSPACE_DASHBOARDS` env flag is documented in operator docs and the README points to `apps/api/.env.example:88-89` | Coda | `apps/api/.env.example` (verify), `deployments/aio/community/README.md`, `deployments/cli/community/README.md`, `deployments/kubernetes/community/README.md` | All four files mention the flag with the same default |
| A.4 | Pin current V2 behavior with a regression test that snapshots `AnalyticsEngineV2` output for the 12 card specs in spec §7 | Coda | `apps/api/plane/tests/unit/analytics_v2/test_card_snapshots.py` (new) | Test snapshots exist for cards A–L and pass on master |
| A.5 | Document the freeze in `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/PHASE-A-COMPLETE.md` (link to PR that lands A.1–A.4) | Anna | new file | File exists |

**Exit gate:** no test that exists today is removed in subsequent phases; V2 unit suite still green.

## Phase B — Extract reusable analytics presentation infrastructure

**Goal:** Pull generic dashboard widgets out of the builder namespace into a shared Analytics V2 presentation layer; prove `/analytics/v2/batch/` parity with the old `/dashboards/{id}/data/`.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| B.1 | Move `apps/web/core/components/dashboards/widgets/truncation-banner.tsx` → `apps/web/core/components/analytics/v2/renderers/truncation-banner.tsx`; update barrel `apps/web/core/components/analytics/v2/index.ts` | Pixel | new + 1 edit | Existing dashboard tests still green; new path exported from v2 barrel |
| B.2 | Extract renderer primitives from `apps/web/core/components/dashboards/widgets/analytics-widget.tsx` into `apps/web/core/components/analytics/v2/renderers/{number,gauge,bar,line,pie,donut,matrix,aggregate-table,work-item-table}.tsx` | Pixel | 9 new files + 1 edit | Same render output for the same input fixture (add render-equality test) |
| B.3 | Move `apps/web/core/components/dashboards/widgets/widget-drilldown-drawer.tsx` → `apps/web/core/components/analytics/v2/renderers/widget-drilldown-drawer.tsx`; it already wraps `insight-drilldown.tsx` | Pixel | new + 1 edit | Customized Insights drill-down still works |
| B.4 | Move `apps/api/plane/utils/dashboard_analytics.py` → `apps/api/plane/analytics/v2/batch.py`; rewrite the public surface to take a list of queries + a global scope, not a `dashboard_id` | Coda | new + deprecation shim | Parity test: same input payload through `/dashboards/{id}/data/` vs `/analytics/v2/batch/` returns same JSON shape |
| B.5 | Add `apps/api/plane/tests/contract/app/test_analytics_v2_batch_parity.py` that replays 5 saved dashboard payloads through both endpoints and asserts shape equality (excludes `request_id`) | Coda | new file | Test passes; old endpoint still works |
| B.6 | Refactor `apps/web/core/components/dashboards/widgets/analytics-data.ts` to call `/analytics/v2/batch/` instead of `/dashboards/{id}/data/` | Pixel | edit | Existing dashboard widgets still render; only the network call changed |
| B.7 | Mark `apps/api/plane/utils/dashboard_analytics.py` deprecated with `DeprecationWarning`; keep import-compatible until Phase E | Coda | edit + new `apps/api/plane/utils/dashboard_analytics.py` docstring note | Deprecation warning emits in tests |

**Exit gate (§17.B acceptance):**
- All `analytics_v2/*` unit tests pass.
- All `apps/web/tests/dashboards/dashboard-widgets.render.test.tsx` cases pass against the extracted renderers.
- Batch result parity test (B.5) green.
- Drill-down/CSV behavior preserved (existing tests in `apps/web/tests/dashboards/`).

## Phase C — Build fixed Workspace Dashboard

**Goal:** Single workspace dashboard that renders the 12 cards from spec §7 against Analytics V2 batch endpoint, with per-user preference persistence.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| C.1 | Add card registry at `apps/web/core/components/dashboards/v3/card-registry.ts` containing 12 entries (A–L) with `defaults` + `controls` per spec §5.1 + §7 | Pixel | new file | TS compiles; each entry's defaults round-trip through §10.2 schema validator |
| C.2 | Build fixed responsive layout at `apps/web/core/components/dashboards/v3/dashboard-shell.tsx` (sections per §7.2–7.5, mobile collapse per §6.1) | Pixel | new file | Renders 12 cards in 4 sections; CSS-grid breakpoints 320/640/1024 |
| C.3 | Implement global controls (time range, date basis, scope filters, reset) at `apps/web/core/components/dashboards/v3/global-controls.tsx` | Pixel | new file | State changes re-fetch batch; reset restores defaults |
| C.4 | Implement per-card controls (metric/dimension/breakdown/display/normalization/allocation/visualization) at `apps/web/core/components/dashboards/v3/card-controls.tsx` | Pixel | new file | Selecting a control updates only that card's query in the batch payload |
| C.5 | Wire global controls to preferences store at `apps/web/core/stores/dashboard-preferences.store.ts` (per-user, localStorage key `(workspaceId,userId)` per §15.1) | Pixel | new file | Reload restores selections; cross-workspace preferences isolated |
| C.6 | Add batch query composer at `apps/web/core/components/dashboards/v3/batch-composer.ts` (card defs + preferences + global scope → `/analytics/v2/batch/` payload) | Pixel | new file | Matches Analytics V2 `AnalyticsQueryV2` schema; partial-failure tolerated |
| C.7 | Wire v3 route at `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/page.tsx` to render `dashboard-shell` directly (no list). Reuse existing `layout.tsx` and `header.tsx` (keep title; remove plural feel). | Pixel | edit | URL stays plural for migration ease per §4.1; renders single fixed dashboard |
| C.8 | Remove `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/page.tsx` from nav (delete directory or redirect to `/dashboards` from the client route) | Pixel | delete or edit | Navigating to `/dashboards/{any-id}` redirects to `/dashboards` |
| C.9 | Backend: ensure `/analytics/v2/batch/` accepts the v3 payload shape (already does per `apps/api/plane/app/urls/analytic.py:60`; verify in test) | Coda | `apps/api/plane/tests/contract/app/test_analytics_v2_app.py` extend | Contract test for v3 payload round-trip passes |
| C.10 | Add end-to-end smoke test `apps/web/tests/dashboards/v3/workspace-dashboard-v3.smoke.test.tsx` that mounts the route, mocks batch endpoint, asserts all 12 cards present | Pixel | new file | Test passes against flag-on instance config |
| C.11 | Add ACL regression: viewer without workspace access is redirected by `apps/web/core/helpers/workspace-dashboards-route-guard.ts` — extend to also cover v3 | Pixel | edit | Existing kill-switch test still passes |

**Exit gate:**
- v3 route loads 12 cards against an empty workspace (data-empty state, not config-empty per §4.2).
- Global filter change triggers exactly one batch request (debounce verified in network mock).
- Preferences survive reload and are isolated per `(workspace, user)`.

## Phase D — Remove old builder UI

**Goal:** Delete dashboard list, create flow, tabs/favorites, edit mode, grid drag/resize, widget CRUD UI, share/owner/visibility UI, Save-to-dashboard link.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| D.1 | Delete `apps/web/core/components/dashboards/list/` (root + `filter.ts`) | Pixel | delete directory | No TS errors; no test imports remain |
| D.2 | Delete `apps/web/core/components/dashboards/detail/` (root, grid, header) | Pixel | delete directory | No TS errors |
| D.3 | Delete `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx` | Pixel | delete file | No TS errors |
| D.4 | Delete `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx` | Pixel | delete file | Customized Insights renders without the Save button (assertion in `customized-insights-v2.test.ts`) |
| D.5 | Delete `apps/web/core/components/dashboards/layout.ts` (drag/resize helpers); `widgets/` becomes empty except for `analytics-widget.tsx` which moves into Analytics V2 namespace in B.2 | Pixel | delete file | No TS errors |
| D.6 | Delete `apps/web/core/store/dashboard.store.ts` and `apps/web/core/hooks/store/use-dashboard.ts` | Pixel | delete files | No TS errors |
| D.7 | Delete `apps/web/core/components/dashboards/constants.ts` (or trim to v3 card-registry exports only) | Pixel | delete or trim | No TS errors; no stale `MARKDOWN_PLACEHOLDER_QUERY_CONFIG` |
| D.8 | Strip all dashboard-specific keys from `packages/i18n/src/locales/*/common.json` (key prefix `dashboard_shell.*` per English file at line 853) — but keep title key if header still shows "Dashboard" | Pixel | edit 21 locale files | Diff shows only deletion lines for builder-specific keys |
| D.9 | Remove "Dashboards" plural nav item hint; rename label to "Dashboard" if header still points to plural | Pixel | search across `apps/web/core/components/**/*.tsx` for `dashboard_shell.*` i18n keys and nav labels | No dangling i18n key references |

**Exit gate:**
- No file in `apps/web/core/components/dashboards/` outside of `v3/` and `widgets/analytics-widget.tsx` (which gets deleted in B.2's tail).
- No test file in `apps/web/tests/dashboards/` references a removed file.
- `apps/web/tests/analytics/customized-insights-v2.test.ts` no longer expects Save-to-dashboard.

## Phase E — Remove old builder APIs and models

**Goal:** Strip builder endpoints and tables after no UI or service depends on them.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| E.1 | Remove builder endpoints from `apps/api/plane/app/urls/dashboard.py` (everything except keep-as-deprecated `workspace-dashboard-data` until B.5 parity ship) | Coda | edit | URL list = empty or single deprecated entry |
| E.2 | Remove views in `apps/api/plane/app/views/dashboard/base.py` corresponding to removed URLs | Coda | edit | No dead view code |
| E.3 | Remove `apps/api/plane/app/permissions/dashboard.py` and `apps/api/plane/app/serializers/dashboard.py` (or trim if reused by analytics) | Coda | delete or trim | No dangling imports |
| E.4 | Remove `apps/api/plane/utils/dashboard_analytics.py` (replaced by `analytics/v2/batch.py` in B.4) | Coda | delete file | No imports remain |
| E.5 | Drop deprecated service `apps/web/core/services/dashboard.service.ts`; ensure `apps/web/core/services/` has no `dashboard.*` import | Pixel | delete file | Web build green |
| E.6 | Write forward migration `apps/api/plane/db/migrations/0135_drop_dashboard_tables.py` that drops `dashboard`, `dashboard_project`, `dashboard_widget`, `dashboard_member_access`, `dashboard_favorite` after verifying no production rows reference them | Coda | new migration | Migration applies cleanly on staging DB; rollback also written |
| E.7 | Remove `Dashboard`, `DashboardProject`, `DashboardWidget`, `DashboardMemberAccess`, `DashboardFavorite` from `apps/api/plane/db/models/dashboard.py` and `apps/api/plane/db/models/__init__.py` | Coda | edit | `python manage.py makemigrations --check` clean |
| E.8 | Update `apps/api/plane/db/models/__init__.py` to drop the imports of removed models | Coda | edit | No `ImportError` at boot |
| E.9 | Update `apps/api/plane/tests/contract/app/test_dashboard_app.py` to assert 410 Gone on legacy routes; remove tests for fully-deleted endpoints | Coda | edit | Tests pass against the deleted URL set |
| E.10 | Remove `apps/api/plane/tests/unit/models/test_dashboard_model.py` and `apps/api/plane/tests/unit/utils/test_dashboard_serializer_acl.py` | Coda | delete files | No dead test files |

**Exit gate (§16.7 constraints):**
- 0135 migration applies on staging DB without error.
- Historical migrations 0054/0090/0092/0134 remain **unchanged in git** — never edit migrations that already shipped.
- `/analytics/v2/batch/` contract still green.
- Analytics V2 unit tests still green.

## Phase F — Cleanup documentation and tests

**Goal:** Stale docs and tests removed; operator docs updated; v3 covered by tests.

| # | Task | Owner | Path | Acceptance |
|---|------|-------|------|------------|
| F.1 | Delete builder-specific i18n keys in all 21 locale files (cleanup of any leftovers from D.8) | Pixel | edit 21 files | `grep -r dashboard_shell packages/i18n/src/locales/ | wc -l` returns only v3 keys |
| F.2 | Update `deployments/aio/community/README.md`, `deployments/cli/community/README.md`, `deployments/kubernetes/community/README.md` to mention `WORKSPACE_DASHBOARDS` and document the on/off semantics | Coda | edit | All three READMEs include a one-line flag description |
| F.3 | Update `apps/api/.env.example:88-89` comment to reflect v3 (no longer "kill switch", now "toggle v3 dashboard") | Coda | edit | Comment reads as v3 |
| F.4 | Replace `apps/web/tests/dashboards/dashboard-widgets.render.test.tsx` with `apps/web/tests/dashboards/v3/dashboard-v3.render.test.tsx` that exercises the 12 cards against mock batch responses | Pixel | replace | New test green; old test deleted |
| F.5 | Replace `apps/web/tests/dashboards/dashboard-widgets.test.ts` and `dashboard-shell.test.ts` with v3 equivalents | Pixel | replace | Tests green |
| F.6 | Update `apps/api/plane/tests/contract/app/test_analytics_v2_app.py` to add v3 batch smoke (12 cards in one batch) | Coda | edit | New smoke case passes |
| F.7 | Update `packages/types/src/instance/base.ts:69-70` doc comment from "kill switch" to "toggle v3 workspace dashboard" | Pixel | edit | Comment reflects v3 |
| F.8 | Update `docs/workspace-dashboards-analytics-v2-spec.md` §1 header to add "Implementation status: Phase X in progress" tag so future readers see the migration state | Anna | edit (no spec change, only status note) | Status note present |
| F.9 | Land a brief CHANGELOG-style note at `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/PHASE-F-COMPLETE.md` summarizing what shipped vs what was deleted | Anna | new file | File exists with the deletion count |

**Exit gate:**
- All v3 routes and APIs covered by automated tests.
- Zero references to `Dashboard*` model, `dashboard_*` URL, or `save-insight-to-dashboard` anywhere except in deleted-file commit messages.
- `pnpm test` and `pytest` green.

## Effort estimate (rough, for Alex to validate)

| Phase | Calendar days | Backend | Frontend |
|-------|---------------|---------|----------|
| A | 1 | 0.5 | 0.5 |
| B | 3–4 | 2 (Coda) | 2 (Pixel) |
| C | 5–7 | 1 (parity work) | 5–6 (heavy UI) |
| D | 1 | — | 1 |
| E | 2 | 2 (migration, model cleanup) | 0.5 (service cleanup) |
| F | 1 | 0.5 | 0.5 |

**Total: ~13–16 working days**, not counting code review cycles. Roughly 3 calendar weeks with one reviewer per phase.

## Risk callouts

1. **Phase E migration** is the only irreversible step. Requires DB row-count check across all deployments before merge; Alex/Huy must approve the migration script before staging apply.
2. **Phase B renderer extraction** is the highest-risk frontend refactor — multiple existing render tests must keep passing. Plan includes a render-equality test (B.2) precisely to de-risk this.
3. **Phase C v3 route** must not block on `WORKSPACE_DASHBOARDS=1` until Alex flips it on for production. Pixel should ship v3 behind the same flag.
4. **Per-user preferences in localStorage** (§15.1) means cross-device sync is deferred to a future iteration; the spec accepts this trade-off.
