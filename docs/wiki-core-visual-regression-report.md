# WIKI-04c Core Wiki visual regression gate

Baseline: `r2d-ai/plane:master` at `5f7d92784c403f76284f0f16718f320221dc7fec`.

Known drift: spec sections 31.4 through 31.7 still describe the earlier `preview` baseline; the Core gate uses `master` per `docs/wiki-ce-implementation-plan.md`.

## Compared surfaces

| Pair | Viewports | Themes | Gate result |
| --- | --- | --- | --- |
| Workspace Wiki list/detail vs Project Pages list/detail primitives | 390x844, 768x1024, 1440x900 | light, dark | Required before WIKI-01..05 merge |
| Company Wiki read-only list/detail vs Workspace Wiki primitives | 390x844, 768x1024, 1440x900 | light, dark | Required before WIKI-01..05 merge |
| Project Pages list/detail baseline vs current branch | 390x844, 768x1024, 1440x900 | light, dark | Must show no unintended visual change |

## Required assertions

- Workspace Wiki and Company Wiki reuse the existing Page editor/header/action primitives. A grep review must not find a duplicate editor shell, header action bar, or page action implementation introduced only for Wiki.
- Collection and tree controls must use existing Plane density, spacing, color tokens, icon button treatments, menus, tabs, tooltips, and empty-state patterns.
- Light and dark empty states must render without clipped text, contrast loss, or one-off illustration changes.
- Company Wiki open-read users must see a native readonly state: readable content, visible metadata, copy/export/version affordances where allowed, and no disabled-looking broken controls.
- Project Pages must preserve the baseline create/edit/title/description/archive/lock/favorite/duplicate/version visual behavior unless a PR explicitly documents an intentional change.

## Merge gate

The Core milestone is not ready until the visual pair captures above are attached to the PR and reviewed together with:

- backend contract/security regression suite;
- live websocket tests;
- `pnpm check`;
- Project Page visual regression confirmation.
