# Builder Cleanup List

> Exhaustive list of every file and i18n key that exists only to support the old builder product.
> All deletions happen in Phase D (UI) and Phase E (backend/models/migration).
> Removal is conditional on Phase B render/parser extraction being green.

## Backend — Python files to delete

| Path | Lines | Used by (today) | Safe to delete after |
|------|-------|-----------------|---------------------|
| `apps/api/plane/app/views/dashboard/base.py` | 683 | `apps/api/plane/app/urls/dashboard.py` | Phase E.1 (after URL removal) |
| `apps/api/plane/app/views/dashboard/__init__.py` | — | imports above | Phase E.2 |
| `apps/api/plane/app/permissions/dashboard.py` | 76 | views above | Phase E.3 |
| `apps/api/plane/app/serializers/dashboard.py` | 135 | views above | Phase E.3 |
| `apps/api/plane/app/urls/dashboard.py` | 82 | `apps/api/plane/app/urls/__init__.py` (or equivalent) | Phase E.1 |
| `apps/api/plane/utils/dashboard_analytics.py` | 391 | views above | Phase E.4 (only 2 consumers, both deleted in Phase E — no replacement module needed) |
| `apps/api/plane/db/models/dashboard.py` | ~360 | `apps/api/plane/db/models/__init__.py` | Phase E.7 (after E.6 migration) |

## Backend — Test files to delete

| Path | Lines | Delete after |
|------|-------|--------------|
| `apps/api/plane/tests/contract/app/test_dashboard_app.py` | 874 | Phase E.9 (replace with 410-Gone assertions if any legacy URL remains) |
| `apps/api/plane/tests/unit/models/test_dashboard_model.py` | 431 | Phase E.10 |
| `apps/api/plane/tests/unit/utils/test_dashboard_serializer_acl.py` | 210 | Phase E.10 |

## Backend — Models to drop (forward migration only)

| Model in `apps/api/plane/db/models/dashboard.py` | Line | Table name (to drop) |
|--------------------------------------------------|------|----------------------|
| `Dashboard` | 27 | `dashboards` |
| `DashboardProject` | 160 | `dashboard_projects` |
| `DashboardWidget` | 205 | `dashboard_widgets` |
| `DashboardMemberAccess` | 248 | `dashboard_member_accesses` |
| `DashboardFavorite` | 307 | `dashboard_favorites` |

**Forward migration:** `apps/api/plane/db/migrations/0135_drop_dashboard_tables.py` (Phase E.6).

**Historical migrations to NOT touch:**
- `0054_dashboard_widget_dashboardwidget.py`
- `0090_rename_dashboard_deprecateddashboard_and_more.py`
- `0092_alter_deprecateddashboardwidget_unique_together_and_more.py`
- `0134_dashboards.py`

## Backend — URL routes to remove

All under `apps/api/plane/app/urls/dashboard.py`:

| URL pattern | Route name | Delete |
|-------------|------------|--------|
| `workspaces/<slug>/dashboards/` | `workspace-dashboards` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/` | `workspace-dashboard-detail` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/duplicate/` | `workspace-dashboard-duplicate` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/widgets/` | `workspace-dashboard-widgets` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/widgets/<widget_id>/` | `workspace-dashboard-widget-detail` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/layout/` | `workspace-dashboard-layout` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/favorite/` | `workspace-dashboard-favorite` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/widgets/<widget_id>/drilldown/` | `workspace-dashboard-widget-drilldown` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/widgets/<widget_id>/export/` | `workspace-dashboard-widget-export` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/members/` | `workspace-dashboard-members` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/members/<member_id>/` | `workspace-dashboard-member-detail` | Phase E.1 |
| `workspaces/<slug>/dashboards/<id>/data/` | `workspace-dashboard-data` | Phase E.1 (delayed until Phase B parity shipped, see §11.1) |

## Frontend — Directories and files to delete

| Path | Lines | Notes |
|------|-------|-------|
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/` (whole directory) | 23 in `page.tsx` | Phase D.2 / D redirect — delete after C.8 redirects |
| `apps/web/core/components/dashboards/list/` | 211 + 25 | Phase D.1 |
| `apps/web/core/components/dashboards/detail/` | 170 + 144 + 90 | Phase D.2 |
| `apps/web/core/components/dashboards/widgets/markdown-placeholder.tsx` | 27 | Phase D.3 |
| `apps/web/core/components/dashboards/widgets/analytics-widget.tsx` | 572 | Phase B.2 (moved into `analytics/v2/renderers/`, not deleted) |
| `apps/web/core/components/dashboards/widgets/analytics-data.ts` | 191 | Phase B.6 (refactored to call `/analytics/v2/batch/`) |
| `apps/web/core/components/dashboards/widgets/widget-drilldown-drawer.tsx` | 135 | Phase B.3 (moved into `analytics/v2/renderers/`) |
| `apps/web/core/components/dashboards/widgets/truncation-banner.tsx` | 30 | Phase B.1 (moved into `analytics/v2/renderers/`) |
| `apps/web/core/components/dashboards/layout.ts` | 117 | Phase D.5 |
| `apps/web/core/components/dashboards/constants.ts` | 40 | Phase D.7 (trim) |
| `apps/web/core/components/dashboards/detail/widget-shell.tsx` | 77 | Phase D.2 (delete with `detail/`) |
| `apps/web/core/components/analytics/v2/save-insight-to-dashboard.tsx` | 196 | Phase D.4 (per §18.1) |
| `apps/web/core/services/dashboard.service.ts` | — | Phase E.5 |
| `apps/web/core/store/dashboard.store.ts` | — | Phase D.6 |
| `apps/web/core/hooks/store/use-dashboard.ts` | — | Phase D.6 |
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/header.tsx` | 17 | **KEEP** — needed for v3 page header |

## Frontend — Test files to replace/delete

| Path | Action | When |
|------|--------|------|
| `apps/web/tests/dashboards/dashboard-widgets.render.test.tsx` (239) | Replace with v3 render test | Phase F.4 |
| `apps/web/tests/dashboards/dashboard-widgets.test.ts` (67) | Replace with v3 widget contract | Phase F.5 |
| `apps/web/tests/dashboards/dashboard-shell.test.ts` (87) | Replace with v3 shell test | Phase F.5 |
| `apps/web/tests/dashboards/workspace-dashboards-kill-switch.render.test.tsx` (134) | Keep — flag still meaningful in Phase C | Phase A3/C |
| `apps/web/tests/dashboards/workspace-dashboards-kill-switch.test.ts` (48) | Keep | Phase A3/C |

## Frontend — i18n keys to delete

All keys under `dashboard_shell.*` in `packages/i18n/src/locales/<locale>/common.json` (21 locale files).

English key namespace at `packages/i18n/src/locales/en/common.json:853`:

- `dashboard_shell.title` — **KEEP** (header label is reused for v3 page)
- `dashboard_shell.time.*` — REMOVE (Phase D.8 — v3 uses different time control labels)
- `dashboard_shell.widget.*` — REMOVE (Phase D.8 — v3 uses card titles from card-registry)
- `dashboard_shell.*` (other builder keys, list/mine/shared/favorites/duplicate/share/edit/etc.) — REMOVE (Phase D.8)
- `dashboard_shell.save_insight_to_dashboard.*` (if present in `save-insight-to-dashboard.tsx` consumer) — REMOVE (Phase D.8)

After cleanup, only `dashboard_shell.title` should remain, and that one may be renamed in Phase F to `workspace_dashboard.title` for clarity.

## Frontend — Hooks and stores to delete

- `apps/web/core/hooks/store/use-dashboard.ts`
- `apps/web/core/store/dashboard.store.ts`

Both exist only to support list/edit state. v3 uses the new `apps/web/core/stores/dashboard-preferences.store.ts` (Phase C.5) which is localStorage-backed.

## Cross-cutting — Feature-flag plumbing

After Phase C ships and the new dashboard is the only path:
- `apps/web/core/helpers/workspace-dashboards-route-guard.ts` — keep file, simplify to `redirect` to `/no-access` or similar (not `/__workspace_dashboards_disabled__`)
- `packages/types/src/instance/base.ts:69-70` — keep field, update doc comment (Phase F.7)
- `apps/api/plane/settings/common.py:634` — keep flag, rename to `WORKSPACE_DASHBOARD` (singular) in a separate PR, not coupled with this work
- `apps/api/.env.example:88-89` — keep line, refresh comment (Phase F.3)

**The flag itself stays** — even with v3 only, the operator may want to turn it off per workspace tier.

## NOT in this cleanup list (intentionally left alone)

- `apps/web/core/components/home/` and `apps/web/core/hooks/store/use-home.ts` — these are the legacy *personal* home page (stickies, quick links, recent activity). They share the word "dashboard" historically but are NOT the Workspace Dashboard. Do not delete.
- `apps/web/core/components/home/home-dashboard-widgets.tsx` — same as above.
- `apps/api/plane/db/models/workspace.py:377 HomeWidgetKeys` — unrelated enum.
- `apps/web/core/components/analytics/work-items/customized-insights.tsx` — KEEP, this is the Analytics surface.
- Analytics V2 engine files (`apps/api/plane/analytics/v2/*`) — KEEP, see 01-audit.

## Total file deletions (count)

- Backend Python source: 7 files
- Backend Python tests: 3 files
- Backend models: 5 (inside 1 file, dropped via migration)
- Backend URL routes: 11 (10 immediate, 1 conditional on Phase B parity)
- Frontend source files: ~13 (mix of deletes and moves into v2 namespace)
- Frontend test files: 3 replaced (kill-switch tests kept)
- Frontend i18n keys: ~25 keys × 21 locales = ~525 lines removed
