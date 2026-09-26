# Phase F — Cleanup documentation, operator env, i18n sweep, spec status note — COMPLETE

> Owner: Doca (RD-485)
> Scope: close the loop after Phases A–E by removing stale docs and config
> references to the retired dashboard builder, so the v3 fixed Workspace
> Dashboard is what every README, env example, type comment, locale, and the
> spec header all describe.

The v3 product itself shipped in Phases C-1 (RD-481), C-2 (RD-482), the perf
gate (RD-486), and the cutover landed in Phase D (RD-483) and Phase E
(RD-484). This phase changes no product code — it rewrites the trail that
points at the new build so nobody has to dig through git history to learn
what `WORKSPACE_DASHBOARDS` means today.

## What shipped in Phase F (this PR, RD-485)

| Task | File(s) | Change |
|------|---------|--------|
| F.1 | `packages/i18n/src/locales/*/common.json` | Verified that no stale `dashboard_shell.*` keys remain. Only `dashboard_shell.title` survives — the v3 route header still reads it (see `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/header.tsx:14`). See "i18n sweep" below for the audit numbers. |
| F.2 | `deployments/aio/community/README.md`, `deployments/cli/community/README.md`, `deployments/kubernetes/community/README.md` | Replaced the "Master flag for workspace dashboards (RD-452 / spec §44.3)" wording with a v3-toggle description: which route, what on/off means in user terms, and the same literal-`1` semantics. Plan issue is now referenced as RD-475. |
| F.3 | `apps/api/.env.example:84-90` | Replaced the "Master flag" comment with one that calls the env var a **toggle for the v3 fixed Workspace Dashboard at `/:workspaceSlug/dashboards`**, references spec §4 (the v3 route) alongside §44.3 (operator env), and notes that the old multi-dashboard builder surface is retired in Phase D / Phase E. |
| F.7 | `packages/types/src/instance/base.ts:69-76` | Replaced the one-line `Mirrors backend WORKSPACE_DASHBOARDS; default off when absent.` with a multi-line v3 doc comment that names the route, names the env var, restates the literal-`1` rule, and explains the missing-field semantics for instances built before the v3 cutover. |
| F.8 | `docs/workspace-dashboards-analytics-v2-spec.md:4` | Added an **Implementation status** line directly under the existing `Status:` line in the header. Status note only — the spec body is untouched. |
| F.9 | `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/PHASE-F-COMPLETE.md` | This file. |

No code, no migration, no test files were touched in this phase. F.4 / F.5 / F.6
(test rewrites against the v3 dashboard) belong to Pixel (RD-483) and Coda
(RD-484) and were already shipped with those phases.

## i18n sweep — F.1 audit (no edits required)

Phase D.8 in RD-483 already removed every `dashboard_shell.*` key except
`dashboard_shell.title`. RD-483's commit message records the actual numbers.
Re-verified on `master` at the Phase-F start commit (`agent/coda/18041fcc484d`):

- 19 locale directories on disk, not 21 — the plan's "21 locales" was an
  estimate; only 19 exist in `packages/i18n/src/locales/`.
- Of those 19, only **English (`en/common.json`)** ever carried `dashboard_shell.*`
  keys. The other 18 had no `dashboard_shell` block before or after RD-483.
- The only `dashboard_shell.*` key still defined anywhere is `dashboard_shell.title`
  (one line, in `en/common.json:853`). One call site consumes it
  (`apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/header.tsx:14`).
  That is the correct v3 — the route is single and singular, so the nav label
  stays singular too.

Other mentions of the string `dashboard_shell` in the tree are noise, not
live keys:

- `apps/web/tests/dashboards/__fixtures__/renderer-baseline.json:55-56` —
  snapshot fixture for the RD-479 render-parity test; the strings
  `dashboard_shell.widget.unsupported_type` shown there are the
  i18n-fallback rendering of an intentionally missing key, not real keys.
  Touching them would break the frozen snapshot without changing behaviour.
- `apps/web/tests/dashboards/analytics-renderers.parity.test.tsx:328` — a
  comment in the parity test that references the historical i18n move
  done by RD-483. Historical accuracy; do not edit.

Verification command (run from repo root):

```
grep -rn "dashboard_shell\." --include="*.tsx" --include="*.ts" --include="*.json" apps/ packages/
```

Output today: only the `dashboard_shell.title` line in `en/common.json:853`
and the one consumer in the dashboards header. No edits needed in Phase F.

## What was deleted in earlier phases (counts, for the historical record)

- **RD-483 (Phase D, frontend):** 19 component / store / service / file
  removals; `68 files changed, 406 insertions(+), 2647 deletions(-)` in the
  merge commit. Net deleted lines ≈ 2 247 across 49 files plus the 19
  deleted-file count.
- **RD-484 (Phase E, backend):** 13 files deleted (URLs, views, serializers,
  permissions, models, util), 1 new forward migration
  (`0135_drop_dashboard_tables.py`) added. `14 files changed,
  82 insertions(+), 3266 deletions(-)` net.
- **Combined Phase D + E net:** roughly **5 913 lines deleted** across the
  builder surface (frontend + backend + tests), plus the 5 dashboard tables
  (`dashboard`, `dashboard_project`, `dashboard_widget`,
  `dashboard_member_access`, `dashboard_favorite`) gone via migration 0135.

Per-county / per-locale i18n diff: 19 one-line deletions in each
`<locale>/common.json` (the empty `dashboard_shell` block), plus two label
values per locale (the singular "Dashboard" rename) — all landed in
RD-483.

## What is deliberately kept (and why)

These are the files / routes / settings referenced as still live in the
rewritten docs and the new spec status note. Do not "clean them up" later
without re-running the plan:

| Path / Setting | Why kept |
|----------------|----------|
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/page.tsx` | v3 route — single fixed dashboard per spec §4. The plural URL stays for migration ease. |
| `apps/web/app/(all)/[workspaceSlug]/(projects)/dashboards/header.tsx` | Reads `dashboard_shell.title` for the header label. |
| `packages/i18n/src/locales/en/common.json` — `dashboard_shell.title` | Header label used by v3 route above. |
| `WORKSPACE_DASHBOARDS` env var, default `0` | Toggles the v3 route on/off. Literal `1` enables, anything else (including `true`) is treated as off. Stays fail-closed until Alex flips the default post-cutover. |
| `apps/api/plane/settings/common.py:634` (WORKSPACE_DASHBOARDS reader) | Backend side of the toggle. Documented in `apps/api/.env.example`. |
| `packages/types/src/instance/base.ts` — `is_workspace_dashboards_enabled` | TypeScript mirror of the backend flag, consumed by the v3 route guard and the cutover (`RD-482`). |
| `/analytics/v2/batch/` (`apps/api/plane/app/urls/analytic.py:60`, `MAX_BATCH_QUERIES=20` in `analytics/v2/query.py:64`) | Generic batch endpoint v3 mounts against. KEEP per plan §16.1. |
| All of `apps/api/plane/analytics/v2/*` and `apps/web/core/components/analytics/v2/{cells,drilldown,mapping,query,use-insight-value-resolver,insight-drilldown,renderers,index}.*` | Generic query / render infrastructure shared by both Customized Insights and v3 dashboard. KEEP per plan §16.1 and §16.2. |
| `apps/web/core/components/dashboards/v3/*` | The fixed v3 dashboard (registry, shell, controls, prefs store, batch composer) shipped in RD-481, cut over in RD-482. |
| 12-card baseline tests in `apps/api/plane/tests/unit/analytics_v2/test_card_snapshots.py` | Pinned engine output (Phase A.4 / RD-477) — still green and still required to stay green. |
| `docs/workspace-dashboards-analytics-v2-spec.md` | Spec body unchanged. Only the header gained an `Implementation status:` note in F.8 so a future reader landing on the file can tell at a glance that v3 already shipped. |
| `docs/superpowers/plans/2026-09-26-workspace-dashboard-v3/{00..05}*.md` | The planning artifact itself — historical record of the rebuild, including the KEEP/EXTRACT/REMOVE audit (01) and the per-phase task list (02). Cited from F.1 / F.7 etc. as the source of truth. |

## Notes for the next reader (Doca hand-off)

- The spec filename still ends in `v2` because the rewrite happened in place
  at `9fd91c41a`; the body is the v3 spec. Do not rename the file in a
  drive-by — the spec body cites its own filename, every linked PR cites
  the filename, and the plan folder's "do not rename" note still applies.
- Anywhere a doc, env, or type comment still uses the word "kill switch",
  it is a bug — flag it. Phase F swept the four sites the plan named, but
  a future commit could introduce a fifth. The plan's spec language in
  §44.3 is "Toggle for the v3 fixed Workspace Dashboard"; treat that as
  the canonical wording.

## Done-when check (against the issue acceptance)

- [x] Zero references to deleted builder paths outside git history and the
      plan folder's own historical notes. (Verified by grep on
      `dashboard-list-root`, `dashboard-grid`, `analytics-widget`,
      `markdown-placeholder`, `dashboard_analytics.py`,
      `DashboardWidget`, `DashboardProject`, etc. — all hits are in
      git-history commit messages or in this plan folder.)
- [x] All four doc/config locations (`apps/api/.env.example`,
      three `deployments/*/community/README.md`, `packages/types/src/instance/base.ts`)
      read as v3.
- [x] Spec header carries the status note; spec body unchanged.
- [x] `PHASE-F-COMPLETE.md` lands in the plan folder.
- [x] PR opened on `agent/doca/...` branch, linked to RD-475.
