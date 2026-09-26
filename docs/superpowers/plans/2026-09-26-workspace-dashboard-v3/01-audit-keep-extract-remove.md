# §16 Audit — KEEP / EXTRACT / REMOVE

> Map of current `master` (`5af14ad45`) files to spec §16 KEEP / EXTRACT / REMOVE buckets.
> All paths are relative to repo root.

## §16.1 KEEP — Backend analytics engine

The Analytics V2 engine is the canonical query engine for the new dashboard. **Do not touch except to add tests pinning current behavior** before refactoring (Phase A.4).

| Path | Lines | Why KEEP |
|------|-------|----------|
| `apps/api/plane/analytics/__init__.py` | 1 | Package init |
| `apps/api/plane/analytics/apps.py` | — | App config |
| `apps/api/plane/analytics/v2/__init__.py` | 26 | Public export: `AnalyticsEngineV2`, `AnalyticsQueryV2`, `AnalyticsResponseV2` |
| `apps/api/plane/analytics/v2/acl.py` | 112 | ACL-safe base queryset (§14.2) |
| `apps/api/plane/analytics/v2/time_scope.py` | 305 | Preset/custom time window resolution (§8.1) |
| `apps/api/plane/analytics/v2/metrics.py` | 273 | Metric registry (§9.1) |
| `apps/api/plane/analytics/v2/dimensions.py` | 237 | Dimension registry (§9.2) |
| `apps/api/plane/analytics/v2/filters.py` | 93 | Structured filter application (§8.3) |
| `apps/api/plane/analytics/v2/allocation.py` | 48 | full_credit / split_equal contribution (§9.6) |
| `apps/api/plane/analytics/v2/normalization.py` | 139 | Percentage normalization modes (§9.5) |
| `apps/api/plane/analytics/v2/comparison.py` | 167 | Reference period resolution (§8) |
| `apps/api/plane/analytics/v2/drilldown.py` | 143 | Aggregate → matching raw items (§13) |
| `apps/api/plane/analytics/v2/serializer.py` | 35 | JSON schema for public contract |
| `apps/api/plane/analytics/v2/query.py` | 761 | Entry point, batch execution, caps |

**Tests that must keep passing throughout the migration:**

- `apps/api/plane/tests/unit/analytics_v2/test_allocation.py` (65)
- `apps/api/plane/tests/unit/analytics_v2/test_cap_enforcement.py` (360)
- `apps/api/plane/tests/unit/analytics_v2/test_comparison.py` (89)
- `apps/api/plane/tests/unit/analytics_v2/test_date_grouping.py` (185)
- `apps/api/plane/tests/unit/analytics_v2/test_multi_membership.py` (223)
- `apps/api/plane/tests/unit/analytics_v2/test_normalization.py` (125)
- `apps/api/plane/tests/unit/analytics_v2/test_registries.py` (94)
- `apps/api/plane/tests/unit/analytics_v2/test_split_equal_budget.py` (123)
- `apps/api/plane/tests/unit/analytics_v2/test_time_scope.py` (223)
- `apps/api/plane/tests/unit/analytics_v2/test_workload.py` (284)
- `apps/api/plane/tests/contract/app/test_analytics_v2_app.py`
- `apps/api/plane/tests/perf/test_page_analytics_perf.py` (302)

The `/analytics/v2/batch/` route at `apps/api/plane/app/urls/analytic.py:60` already exists — KEEP, Phase C will reuse it directly.

## §16.2 KEEP — Frontend analytics/query primitives

These already power Customized Insights and are the substrate the new dashboard will mount on top of. They are **generic** and must not be deleted just because they were born inside the Dashboard effort.

| Path | Lines | Why KEEP |
|------|-------|----------|
| `apps/web/core/components/analytics/v2/cells.ts` | 196 | Cell → chart/table presentation mapping (§16.2) |
| `apps/web/core/components/analytics/v2/drilldown.ts` | 53 | Drill-down selection mapping (§13) |
| `apps/web/core/components/analytics/v2/mapping.ts` | 102 | Legacy → V2 mappings |
| `apps/web/core/components/analytics/v2/query.ts` | 116 | Client-side query builder (Customized Insights) |
| `apps/web/core/components/analytics/v2/use-insight-value-resolver.ts` | 102 | UUID/dimension label resolution |
| `apps/web/core/components/analytics/v2/insight-drilldown.tsx` | 145 | Drill-down drawer integration |
| `apps/web/core/components/analytics/v2/index.ts` | 10 | Barrel export — keep, possibly extend |

Customized Insights itself (`apps/web/core/components/analytics/work-items/customized-insights.tsx`) is KEEP — it is the Analytics surface per spec §3.

## §16.3 KEEP or EXTRACT — Chart/render infrastructure

The renderers under `apps/web/core/components/dashboards/widgets/` are imported only by the old dashboard widgets, but their bodies are generic. Phase B extracts them to `apps/web/core/components/analytics/v2/renderers/` so both Customized Insights and the new dashboard use them.

| Path | Lines | Bucket |
|------|-------|--------|
| `apps/web/core/components/dashboards/widgets/analytics-widget.tsx` | 572 | **EXTRACT** (top-level shell → adapter) |
| `apps/web/core/components/dashboards/widgets/analytics-data.ts` | 191 | **EXTRACT** (analytics response parsing, batch caller) |
| `apps/web/core/components/dashboards/widgets/widget-drilldown-drawer.tsx` | 135 | **EXTRACT** (already a thin wrapper around `insight-drilldown.tsx`) |
| `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx` | 27 | **REMOVE** (markdown widget is out of scope §3.2) |
| `apps/web/core/components/dashboards/widgets/truncation-banner.tsx` | 30 | **EXTRACT** (generic truncation warning, KEEP per §16.3) |
| `apps/web/core/components/dashboards/detail/widget-shell.tsx` | 77 | **REMOVE** (12-col grid wrapper, see §16.5) |

Renderer primitives to identify and extract during Phase B (current location inside `analytics-widget.tsx`):
- number/stat, gauge, bar, line, pie, donut — extract as `<Renderer kind="…">` components
- matrix model + renderer — extract as standalone matrix component
- aggregate table renderer
- work-item table renderer
- CSV helpers
- chart click hooks (drill-down dispatch)

## §16.4 KEEP or EXTRACT — Batch/query composition plumbing

| Path | Lines | Bucket | Notes |
|------|-------|--------|-------|
| `apps/api/plane/utils/dashboard_analytics.py` | 391 | **REMOVE in Phase E.4** | Only imported by `app/serializers/dashboard.py` + `app/views/dashboard/base.py`; both deleted in Phase E. `/analytics/v2/batch/` (`apps/api/plane/app/urls/analytic.py:60`, with `MAX_BATCH_QUERIES=20` at `apps/api/plane/analytics/v2/query.py:64`) already implements generic batch — no extract needed. |
| `apps/api/plane/app/views/dashboard/base.py` `WorkspaceDashboardDataViewSet` | — | **REMOVE in Phase E** | Current `/dashboards/{id}/data/` endpoint. Drop together with the rest of `dashboard/base.py` once Phase C uses `/analytics/v2/batch/`. |

Generic batch behaviour we must preserve per §16.4:
- base/global query + card-local query composition
- partial failure per query
- viewer token resolution (if still needed by future admin templates)
- reusing the Analytics V2 engine, not client-side aggregation

## §16.5 REMOVE from product surface

These files implement the builder UX the spec explicitly retires. See `03-builder-cleanup-list.md` for the full per-file breakdown. Summary here:

| Path (or pattern) | Why REMOVE |
|-------------------|------------|
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/page.tsx` | List route, replaced by single fixed dashboard per §4 |
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/page.tsx` | Per-id detail route — must disappear from nav per §4.1 |
| `apps/web/core/components/dashboards/list/dashboard-list-root.tsx` | Tabs (all/mine/shared/favorites) UI |
| `apps/web/core/components/dashboards/list/filter.ts` | Tab filter helper (only used by list) |
| `apps/web/core/components/dashboards/detail/dashboard-detail-root.tsx` | Edit/view mode + grid + drag/resize host |
| `apps/web/core/components/dashboards/detail/dashboard-grid.tsx` | 12-col editable grid (replace with responsive section layout) |
| `apps/web/core/components/dashboards/detail/dashboard-header.tsx` | Rename/duplicate/favorite/share menu |
| `apps/web/core/components/dashboards/layout.ts` | Layout persistence helpers (move/resize) |
| `apps/web/core/components/dashboards/constants.ts` (parts) | `DASHBOARD_LIST_TABS`, `DEFAULT_WIDGET_LAYOUT`, `MARKDOWN_PLACEHOLDER_QUERY_CONFIG` |
| `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx` | Markdown widget — out of scope |
| `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx` | "Save to dashboard" link — §18.1 explicit REMOVE |
| `apps/web/core/store/dashboard.store.ts` | MobX store for list/edit state |
| `apps/web/core/hooks/store/use-dashboard.ts` | Hook layer for the store |
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/header.tsx` | Header keeps; rename semantics only (no rename action button) |

## §16.6 REMOVE or deprecate — Builder-specific API surface

`apps/api/plane/app/urls/dashboard.py` registers every builder endpoint. Phase E removes them; Phase B keeps them around for the new dashboard to keep working until it has its own router.

| URL | Name | Bucket |
|-----|------|--------|
| `workspaces/{slug}/dashboards/` | `workspace-dashboards` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/` | `workspace-dashboard-detail` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/duplicate/` | `workspace-dashboard-duplicate` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/widgets/` | `workspace-dashboard-widgets` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/widgets/{widgetId}/` | `workspace-dashboard-widget-detail` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/layout/` | `workspace-dashboard-layout` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/favorite/` | `workspace-dashboard-favorite` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/data/` | `workspace-dashboard-data` | **Keep until Phase B §11.1 parity proven** |
| `workspaces/{slug}/dashboards/{id}/widgets/{widgetId}/drilldown/` | `workspace-dashboard-widget-drilldown` | REMOVE (drilldown lives in Analytics V2) |
| `workspaces/{slug}/dashboards/{id}/widgets/{widgetId}/export/` | `workspace-dashboard-widget-export` | REMOVE (CSV moves to V2) |
| `workspaces/{slug}/dashboards/{id}/members/` | `workspace-dashboard-members` | REMOVE |
| `workspaces/{slug}/dashboards/{id}/members/{memberId}/` | `workspace-dashboard-member-detail` | REMOVE |

## §16.7 Builder data models — to be removed (Phase E only)

Models in `apps/api/plane/db/models/dashboard.py` (paths in spec §16.7):

| Model | Bucket | Note |
|-------|--------|------|
| `Dashboard` (line 27) | REMOVE in Phase E | Forward migration after UI/API gone |
| `DashboardProject` (line 160) | REMOVE in Phase E | Manual source-project persistence |
| `DashboardWidget` (line 205) | REMOVE in Phase E | Builder widget rows |
| `DashboardMemberAccess` (line 248) | REMOVE in Phase E | Sharing ACL (§14.1 says dashboard has no separate ACL in P0) |
| `DashboardFavorite` (line 307) | REMOVE in Phase E | Per-user favorite list |

**Pre-removal migrations kept in place:**
- `0054_dashboard_widget_dashboardwidget.py` — original legacy dashboard tables, untouched
- `0090_rename_dashboard_deprecateddashboard_and_more.py` — rename, untouched
- `0092_alter_deprecateddashboardwidget_unique_together_and_more.py` — untouched
- `0134_dashboards.py` — current builder tables, **must NOT be modified in place** per §16.7; a forward migration drops these in Phase E only

## Feature-flag plumbing (KEEP through Phase C, then audit)

- `apps/api/plane/settings/common.py:634` — `WORKSPACE_DASHBOARDS = os.environ.get(...) == "1"`, fail-closed default
- `apps/api/plane/license/api/views/instance.py:168` — `is_workspace_dashboards_enabled` exposed in instance config
- `packages/types/src/instance/base.ts:69-70` — typed mirror
- `apps/web/core/helpers/workspace-dashboards-access.ts` — `isWorkspaceDashboardsEnabled()`
- `apps/web/core/helpers/workspace-dashboards-route-guard.ts` — redirect on off
- `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/layout.tsx` — `clientLoader` calls route guard
- `apps/api/.env.example:88-89` — `WORKSPACE_DASHBOARDS=0`
- `apps/api/plane/tests/contract/app/test_dashboard_app.py:30` — `enable_workspace_dashboards` fixture
- `apps/web/tests/dashboards/workspace-dashboards-kill-switch.test.ts`
- `apps/web/tests/dashboards/workspace-dashboards-kill-switch.render.test.tsx`

Phase A keeps this fail-closed. Phase C re-evaluates the flag's purpose (probably flip default-on or rename once only the new dashboard ships).

## Summary count

- **KEEP** (no refactor): 14 backend files, 7 frontend files
- **EXTRACT** (move to Analytics V2 namespace, KEEP behavior): 4 dashboard files + 1 utility + renderer internals
- **REMOVE** (Phase D/E, after migration safety review): 5 dashboard files, 1 hook, 1 store, 1 i18n component, 1 link, 5 models, 11 URL routes (10 hard, 1 conditional on Phase B parity)
