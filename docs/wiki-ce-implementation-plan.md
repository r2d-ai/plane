# Wiki for Plane CE — Implementation Plan

> Status: **Draft for review**
>
> Depends on: [wiki-ce-spec.md](./wiki-ce-spec.md)
>
> Implementation baseline: create feature branches from `r2d-ai/plane:master` (upstream `makeplane/plane:master`, release v1.4.2, SHA `5f7d92784c403f76284f0f16718f320221dc7fec`). Do not automatically follow a moving `master`.
>
> Planning principle: small reviewable PRs, no large “Wiki mega-PR”.
>
> **Company Wiki model (spec §29, revised 2026-09-22).** Company Wiki is **Workspace Wiki on a designated real workspace** fixed by `COMPANY_WIKI_WORKSPACE_SLUG`, not a `workspace=NULL` instance scope. `Page.workspace` stays non-null: there is **no** nullable-workspace migration, no `/api/instance/wiki/...` API path, no `instance_page` live document type, no `InstancePagePermission` and no `InstancePageService`. Company Wiki reuses the Workspace Wiki REST API, the `workspace_page` live document type and the workspace asset routes against the designated workspace; `COMPANY_WIKI_OPEN_READ` controls the read-only open-read override. The normative reference is [wiki-ce-spec.md §29](./wiki-ce-spec.md#29-company-wiki-fork-extension-designated-workspace-model); [§29.15](./wiki-ce-spec.md#2915-core-architecture-consequence) is the canonical ordering.
>
> Canonical ordering: WIKI-00 = Page-adjacent audit + hierarchy scope guard + regression (no nullable migration); WIKI-01 = Workspace Wiki backend core with `COMPANY_WIKI_WORKSPACE_SLUG` + `COMPANY_WIKI_OPEN_READ`; WIKI-02 = `workspace_page` realtime collaboration; WIKI-03 = Workspace Wiki + Company Wiki web surfaces (`/company-wiki` route alias resolving the designated workspace); WIKI-04 = hierarchy/search/export/security hardening; WIKI-05 = Collections (Core milestone). Sharing & comments, templates/publishing/nested export, editor parity, advanced parity and AI/importers are the parity/advanced track that follows.

---

## 1. Implementation strategy

### 1.1 Architecture

Use Plane's existing Page stack as the kernel.

```text
                                   Page
                                    │
                 ┌──────────────────┴──────────────────┐
                 │                                     │
           Project Page                          Workspace Wiki
        is_global=false                         is_global=true
        workspace!=NULL                        workspace!=NULL
        ProjectPage required                   no ProjectPage required
                 │                                     │
           Project RBAC                        Workspace RBAC
                 │                       (Company Wiki = Workspace Wiki
                 │                        on the designated workspace;
                 │                        COMPANY_WIKI_OPEN_READ adds
                 │                        authenticated read-only access)
                 └──────────────────┬──────────────────┘
                                    │
                             Shared Page Engine
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
               Editor            Versions            Assets
                 │
                Yjs
                 │
             Hocuspocus
```

### 1.2 Extension model

Use a **native compile-time extension**, not an external Plane App.

Existing extension seams to prefer:

- `apps/web/app/routes/extended.ts`;
- `packages/types/src/page/extended.ts`;
- `apps/web/core/hooks/pages/use-extended-editor-extensions.ts`;
- `apps/web/core/hooks/pages/use-pages-pane-extensions.ts`;
- `apps/live/src/services/page/extended.service.ts`.

Core files should only be changed when there is no registration seam.

### 1.3 Baseline decision and validation gate

The implementation baseline is `r2d-ai/plane:master` (upstream `makeplane/plane:master`, release v1.4.2, SHA `5f7d92784c403f76284f0f16718f320221dc7fec`). The earlier `preview` baseline (`02c19e1341…`) was dropped on 2026-09-22: its deployment gate hit preview-specific blockers (Caddy `Caddyfile.ce`, missing `plane-live` env values), so the fallback to `master` is an explicit architecture decision, not an agent-local workaround.

Before WIKI-01 code starts, validate the `master` baseline **without Wiki changes**:

- [ ] `pnpm check`;
- [ ] `pnpm build`;
- [ ] backend contract/unit test stack;
- [ ] build the self-host images used by the deployment;
- [ ] start the deployment stack;
- [ ] authenticate successfully;
- [ ] open workspace/project routes;
- [ ] create/open/edit an existing Project Page;
- [ ] verify Page realtime collaboration;
- [ ] upload/render a Page asset;
- [ ] verify reverse-proxy/static-app routes.

Record the validated SHA, the per-check result and any known pre-existing failures in the first implementation PR, so later Wiki regressions are not confused with pre-existing baseline issues.

### 1.4 Anti-goals

Do not:

- create a separate Wiki service;
- create a second editor;
- create `WikiPage` duplicating `Page`;
- remove project scoping from current Page code;
- create a `workspace=NULL` / instance Page scope: no nullable `Page.workspace` migration, no `/api/instance/wiki/...` route, no `instance_page` live document type, no `InstancePagePermission` / `InstancePageService`;
- create a hidden or fake workspace for Company Wiki (the designated workspace is a real, visible workspace);
- implement a generic plugin framework as part of Wiki P0;
- depend on Plane AI;
- depend on a vector database;
- mix Collections/Comments/Publish into the first backend PR.

---

# 2. PR dependency graph

```text
WIKI-00 Page scope foundation
(project vs wiki audit + hierarchy guard)
          │
          ▼
WIKI-01 Workspace Wiki backend core
(COMPANY_WIKI_WORKSPACE_SLUG +
 COMPANY_WIKI_OPEN_READ)
          │
          ├──────────────┐
          ▼              ▼
WIKI-02 Live         WIKI-03 Web surfaces
workspace_page       Workspace Wiki
                     + Company Wiki
                     (/company-wiki alias)
          └──────┬────────┘
                 ▼
        WIKI-04 Core UX + hardening
        across project and wiki scopes
                 │
                 ▼
        WIKI-05 Collections
        (Core milestone)
                 │
        ┌────────┼──────────┐
        ▼        ▼          ▼
  WIKI-06    WIKI-07     WIKI-08
  Sharing &  Templates/  Editor parity
  Comments   Publish/Export
        └────────┬──────────┘
                 ▼
        WIKI-09 Advanced parity
                 │
                 ▼
        WIKI-10 AI/importers optional
```

WIKI-00 through WIKI-05 form the **Core Wiki production milestone** (Collections is core, decision D6).

Workspace Wiki follows Plane Commercial behavior as closely as practical. Company Wiki is the same Workspace Wiki on the real workspace designated by `COMPANY_WIKI_WORKSPACE_SLUG`; `COMPANY_WIKI_OPEN_READ` adds authenticated read-only access for non-members. There is no separate instance scope.

WIKI-06 onward form the **Commercial parity / advanced extension track**.

---

# 3. WIKI-00 — Page scope foundation

## Goal

Make the existing Page engine safely support the two storage scopes before either Wiki API is considered stable:

```text
Project Page      = is_global=false, workspace!=NULL, ProjectPage relation
Workspace Wiki    = is_global=true,  workspace!=NULL  (no ProjectPage relation)
Company Wiki      = same as Workspace Wiki, on the workspace fixed by
                    COMPANY_WIKI_WORKSPACE_SLUG
```

`Page.workspace` stays **non-null**. This PR is deliberately audit/invariant focused: it adds the Page-adjacent audit, the hierarchy scope guard and regression tests. It ships no broad new Wiki UI and **no nullable-workspace migration**.

## 3.1 Page scope helpers

- [ ] keep `Page.workspace` non-null; do not add a null-workspace / instance scope;
- [ ] retain all existing workspace IDs unchanged;
- [ ] add scope helper(s) rather than scattering `is_global` checks everywhere;
- [ ] do not replace `is_global` across the entire upstream codebase in this PR.

Recommended helpers:

```text
page.scope                       # "project" | "wiki"
page.is_project_page             # is_global == False
page.is_workspace_page           # is_global == True (Workspace Wiki + Company Wiki)
```

Company Wiki is not a distinct storage scope: it is Workspace Wiki on the designated workspace.

## 3.2 Audit Page-adjacent models

Company Wiki pages are ordinary Workspace Wiki rows in a real workspace, so this audit verifies that Page-adjacent models already work for a wiki page (`is_global=true`, non-null workspace, no `ProjectPage` link). No schema changes are expected.

- [ ] `PageVersion.workspace`: derive from `page.workspace_id`; works for a wiki page.
- [ ] `PageLog.workspace`: derive from `page.workspace_id`; works for a wiki page.
- [ ] `PageLabel`: stays workspace-only; Company Wiki uses the designated workspace's labels.
- [ ] favorites (`UserFavorite`): `WorkspaceBaseModel`; keyed on the page's real workspace, no fake workspace.
- [ ] recent visits (`UserRecentVisit`): workspace-scoped; wiki pages use their real workspace.
- [ ] export jobs: verify serialization does not assume a project context.
- [ ] background Page version/log tasks: verify they resolve scope from the page, not a project.

## 3.3 Asset scope

`FileAsset.workspace` is already nullable, but Page asset URL generation currently assumes workspace/project context.

Tasks:

- [ ] define the Workspace Wiki / Company Wiki asset URL contract on the existing workspace asset routes;
- [ ] add a scope-aware asset authorization helper;
- [ ] ensure Company Wiki assets never use a fake workspace;
- [ ] ensure workspace/project asset URLs remain unchanged;
- [ ] test cross-scope asset UUID access.

Implementation of the final route lands in WIKI-01, but the contract must be fixed here.

## 3.4 Hierarchy scope guard

One shared server-side validator must enforce the invariants for both scopes. Reject:

- project parent -> Wiki child;
- Wiki parent -> project child;
- different workspace parents;
- deleted parent;
- self/descendant cycles.

A malformed legacy tree must fail safe (terminate and reject) rather than loop.

## 3.5 Scope regression tests

Before feature APIs:

- [ ] existing Project Page remains non-null workspace;
- [ ] existing project page tests pass;
- [ ] workspace Wiki fixture can exist with non-null workspace and no ProjectPage;
- [ ] `Page.workspace` is still required (non-null) for every Page;
- [ ] version/log creation works for a wiki page;
- [ ] model/service helpers classify project vs wiki correctly;
- [ ] the hierarchy guard rejects every case in §3.4;
- [ ] recursive archive/unarchive is cycle-safe.

## WIKI-00 acceptance

The data layer can represent Company Wiki as Workspace Wiki on the designated workspace without synthetic workspaces, without a nullable-workspace migration, and without changing existing Project Page behavior.

---

# 4. WIKI-01 — Workspace Wiki backend core

## Goal

Provide secure Wiki APIs for **Workspace Wiki** and **Company Wiki** without changing Project Page behavior.

Workspace Wiki is scoped by workspace membership. Company Wiki is the same Workspace Wiki on the real workspace fixed by `COMPANY_WIKI_WORKSPACE_SLUG`: `COMPANY_WIKI_OPEN_READ=true` lets every authenticated active user read it, while create/edit/lock/archive/manage stay with admin/owner of the designated workspace. There is no separate instance API, permission class or store.

## 4.0 Company Wiki reuses the workspace Wiki API

Company Wiki has no API path of its own. It is served by the workspace Wiki endpoints against the designated workspace slug resolved from `COMPANY_WIKI_WORKSPACE_SLUG`:

```text
GET/POST   /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/
GET/PATCH/DELETE /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/
GET/PATCH  /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/description/
POST/DELETE /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/archive/
POST/DELETE /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/lock/
GET        /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/versions/
GET        /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/versions/<version_id>/
POST       /api/workspaces/<COMPANY_WIKI_WORKSPACE_SLUG>/pages/<page_id>/duplicate/
```

Tasks:

- [ ] add a `COMPANY_WIKI_WORKSPACE_SLUG` setting and resolve the designated workspace from it;
- [ ] add a `COMPANY_WIKI_OPEN_READ` flag for the read-only open-read override;
- [ ] when `COMPANY_WIKI_OPEN_READ=true`, an authenticated active non-member may read the designated workspace's Wiki pages but must not write, lock, archive or manage them;
- [ ] when `COMPANY_WIKI_OPEN_READ=false`, Company Wiki read/write both require active membership of the designated workspace via `WorkspacePagePermission`;
- [ ] apply the open-read override on the read path only, layered on top of `WorkspacePagePermission`; never weaken the member path;
- [ ] an unauthenticated request is denied regardless of `COMPANY_WIKI_OPEN_READ`;
- [ ] add the designated workspace slug to `RESTRICTED_URLS` alongside `company-wiki`;
- [ ] do not infer Company Wiki write permission from being admin/owner of some other workspace.

## 4.1 Add workspace-specific serializer path

Current issue:

`PageSerializer.create()` assumes `project_id` and always creates a `ProjectPage` relation.

Tasks:

- [ ] Do not weaken the existing Project Page serializer.
- [ ] Add a workspace-page creation serializer or explicit create service.
- [ ] Set:
  - [ ] `workspace` from URL workspace;
  - [ ] `owned_by` from request user;
  - [ ] `is_global=True`;
  - [ ] default public/private access according to product semantics;
  - [ ] `sort_order`;
  - [ ] optional validated `parent`.
- [ ] Do not create `ProjectPage`.
- [ ] Reuse current description sanitization/conversion paths.
- [ ] Return the same Page shape where practical so shared frontend components work.

Likely files:

```text
apps/api/plane/app/serializers/page.py
apps/api/plane/app/views/page/
```

Prefer adding workspace-specific classes/files over branching every existing project Page code path.

## 4.2 Add WorkspacePagePermission

Tasks:

- [ ] Introduce dedicated workspace Wiki permission class.
- [ ] Require active WorkspaceMember.
- [ ] Scope every page lookup by:
  - [ ] workspace slug/id;
  - [ ] `is_global=True`;
  - [ ] active/non-deleted page.
- [ ] Implement action-level checks:
  - [ ] view;
  - [ ] create;
  - [ ] edit;
  - [ ] archive;
  - [ ] restore;
  - [ ] delete;
  - [ ] lock/unlock;
  - [ ] access change;
  - [ ] duplicate;
  - [ ] parent move/reorder.
- [ ] Keep private Page semantics isolated for later PageShare extension.
- [ ] Ensure unauthorized private page behaves as 404/not found where appropriate.

Likely file:

```text
apps/api/plane/app/permissions/page.py
```

If adding a separate module improves isolation:

```text
apps/api/plane/app/permissions/workspace_page.py
```

## 4.3 Add workspace Page queryset/service

Tasks:

- [ ] Filter `workspace__slug=slug`.
- [ ] Filter `is_global=True`.
- [ ] Add active WorkspaceMember check.
- [ ] Support root list.
- [ ] Support optional children/parent filter.
- [ ] Support:
  - [ ] access;
  - [ ] archived;
  - [ ] favorites;
  - [ ] owner;
  - [ ] search.
- [ ] Add strict order-by allowlist.
- [ ] Preserve `description_stripped` for search.

## 4.4 Add workspace Page endpoints

Target internal endpoints:

```text
GET/POST /api/workspaces/<slug>/pages/
GET/PATCH/DELETE /api/workspaces/<slug>/pages/<page_id>/

POST/DELETE /api/workspaces/<slug>/pages/<page_id>/archive/
POST/DELETE /api/workspaces/<slug>/pages/<page_id>/lock/
POST        /api/workspaces/<slug>/pages/<page_id>/access/

GET/PATCH   /api/workspaces/<slug>/pages/<page_id>/description/

GET         /api/workspaces/<slug>/pages/<page_id>/versions/
GET         /api/workspaces/<slug>/pages/<page_id>/versions/<version_id>/

POST        /api/workspaces/<slug>/pages/<page_id>/duplicate/
```

Tasks:

- [ ] Add URL patterns without colliding with project page paths.
- [ ] Keep current project URLs unchanged.
- [ ] Use workspace-specific viewsets.
- [ ] Reuse existing archive/lock/version/duplicate helpers only after making scope explicit.

Likely files:

```text
apps/api/plane/app/urls/page.py
apps/api/plane/app/views/page/base.py
apps/api/plane/app/views/page/version.py
```

Preferred if size grows:

```text
apps/api/plane/app/views/page/workspace.py
apps/api/plane/app/views/page/workspace_version.py
```

## 4.5 Hierarchy validator

Create one server-side validator reusable by workspace Wiki and eventually Project Pages.

Rules:

- [ ] page cannot parent itself;
- [ ] parent must be same workspace;
- [ ] parent must be same scope (`is_global`);
- [ ] parent cannot be descendant of page;
- [ ] deleted parent rejected;
- [ ] archived-parent behavior explicitly defined;
- [ ] malformed legacy cycles fail safely.

Implementation options:

- iterative ancestor walk with visited IDs;
- recursive SQL/CTE with cycle guard.

Do not trust frontend-only validation.

## 4.6 Recursive archive/restore

Tasks:

- [ ] Verify existing recursive CTE is safe for Wiki.
- [ ] Add visited/cycle-safe behavior if needed.
- [ ] Ensure only Wiki descendants in same workspace are affected.
- [ ] Test deep trees.

## 4.7 Favorites

Current project favorites are project-scoped.

Tasks:

- [ ] Verify favorite model can reference a Wiki Page without Project relation.
- [ ] If yes, add workspace favorite endpoint.
- [ ] If no, extend model minimally.
- [ ] List favorites permission-safely.

## 4.8 Search

Tasks:

- [ ] Search `name`.
- [ ] Search `description_stripped`.
- [ ] Filter effective access before response.
- [ ] Avoid snippets from inaccessible pages.
- [ ] Use existing search service if it can safely index global pages.
- [ ] Do not introduce vector search.

## 4.9 External API compatibility

Plane Commercial documents:

```text
POST /api/v1/workspaces/{workspace_slug}/pages/
GET  /api/v1/workspaces/{workspace_slug}/pages/{page_id}/
```

Tasks:

- [ ] Locate CE external API router.
- [ ] Add workspace Page endpoint with CE PAT/API auth.
- [ ] Match documented fields where supported.
- [ ] Keep project page endpoint unchanged.
- [ ] Add API contract tests.

## 4.10 Backend tests

Add tests before merge.

Required cases:

- [ ] create public Wiki page;
- [ ] create private Wiki page;
- [ ] retrieve own page;
- [ ] retrieve public page;
- [ ] deny cross-workspace page UUID;
- [ ] deny private page;
- [ ] patch scoped correctly;
- [ ] description read/write scoped correctly;
- [ ] archive/restore;
- [ ] lock/unlock;
- [ ] locked write denied;
- [ ] duplicate;
- [ ] version list;
- [ ] version retrieve cross-page denied;
- [ ] invalid order-by rejected;
- [ ] self-parent rejected;
- [ ] descendant-parent cycle rejected;
- [ ] project page regression;
- [ ] Company Wiki `COMPANY_WIKI_OPEN_READ=true`: authenticated non-member can read, cannot write;
- [ ] Company Wiki `COMPANY_WIKI_OPEN_READ=false`: non-member cannot read;
- [ ] Company Wiki: anonymous denied regardless of the flag;
- [ ] Company Wiki: non-member cannot write through `/api/workspaces/<designated_slug>/pages/`.

Likely test directory:

```text
apps/api/plane/tests/contract/app/
apps/api/plane/tests/unit/
```

## WIKI-01 acceptance

- secure workspace Page CRUD works;
- no ProjectPage relation required;
- existing Project Pages unchanged;
- all BOLA/hierarchy tests pass.

---

# 5. WIKI-02 — Workspace Page realtime collaboration

## Goal

Support commercial-like realtime collaborative editing for Wiki using the existing Hocuspocus/Yjs service. Company Wiki uses the same service with `workspaceSlug = COMPANY_WIKI_WORKSPACE_SLUG`; there is no separate instance document type.

## 5.1 Extend document types

Current:

```ts
type TDocumentTypes = "project_page";
```

Target:

```ts
type TDocumentTypes = "project_page" | "workspace_page";
```

Files:

```text
apps/live/src/types/index.ts
```

Shared request types already anticipate `workspace_page`; reuse them.

## 5.2 Add WorkspacePageService

Create:

```text
apps/live/src/services/page/workspace-page.service.ts
```

Responsibilities:

- extend existing page service;
- base path `/api/workspaces/{workspaceSlug}`;
- fetch page;
- fetch/update description;
- update title/properties;
- resolve assets.

Company Wiki needs no additional service: it is the same service with the designated workspace slug.

## 5.3 Extend service handler

File:

```text
apps/live/src/services/page/handler.ts
```

Tasks:

- [ ] dispatch `project_page`;
- [ ] dispatch `workspace_page`;
- [ ] reject unknown document types.

## 5.4 Authentication/authorization

File areas:

```text
apps/live/src/lib/auth.ts
apps/live/src/extensions/database.ts
apps/live/src/extensions/title-sync.ts
```

Tasks:

- [ ] `projectId` remains optional for workspace page.
- [ ] workspace slug mandatory for `workspace_page`.
- [ ] initial document load hits permission-protected API.
- [ ] update persistence hits permission-protected API.
- [ ] title sync respects effective Page permission.
- [ ] lock prevents writes.
- [ ] Company Wiki (`workspaceSlug = COMPANY_WIKI_WORKSPACE_SLUG`): initial load allowed for an authenticated active non-member only when `COMPANY_WIKI_OPEN_READ=true`; persistence always requires admin/owner of the designated workspace.
- [ ] anonymous connections never receive document bytes.

## 5.5 Revocation behavior

At minimum:

- [ ] new writes after access revocation fail;
- [ ] current session receives an error/force close if persistence becomes forbidden.

Later optimization can actively disconnect sessions when ACL changes.

## 5.6 Tests

Add live tests for:

- [ ] load workspace page;
- [ ] initialize HTML -> Yjs binary;
- [ ] persist update;
- [ ] unauthorized workspace;
- [ ] private page no access;
- [ ] locked page;
- [ ] read-only user when sharing exists;
- [ ] title sync authorization;
- [ ] project_page regression;
- [ ] Company Wiki open-read: non-member can load state but cannot persist;
- [ ] Company Wiki anonymous connection denied.

## WIKI-02 acceptance

Wiki and Project Pages can use the same live service concurrently with separate secure document types. Company Wiki reuses `workspace_page` with the designated workspace slug.

---

# 6. WIKI-03 — Web Wiki surfaces, stores and editor

## Goal

Expose two first-class Wiki surfaces using existing Page components:

- Workspace Wiki: `/:workspaceSlug/wiki`;
- Company Wiki: `/company-wiki`, independent of workspace context.

## 6.1 Routes through existing extension seam

Use:

```text
apps/web/app/routes/extended.ts
```

Target:

```text
/:workspaceSlug/wiki
/:workspaceSlug/wiki/:pageId

/company-wiki
/company-wiki/:pageId
```

`/company-wiki` must be a standalone route under the authenticated app shell, not nested under `:workspaceSlug`. Internally it resolves `COMPANY_WIKI_WORKSPACE_SLUG` and renders the Workspace Wiki UI against that workspace; copied links stay `/company-wiki/:pageId` (no workspace slug). Add `company-wiki` **and** the configured Company Wiki workspace slug to `RESTRICTED_URLS` (`packages/constants/src/workspace.ts`) to avoid route ambiguity and slug squatting.

Create route components in an isolated Wiki area, for example:

```text
apps/web/app/(all)/[workspaceSlug]/wiki/
  (list)/page.tsx
  (detail)/[pageId]/page.tsx
  ...
```

Actual physical path should follow current React Router conventions and route config constraints.

## 6.2 Workspace page services

Create:

```text
apps/web/core/services/page/workspace-page.service.ts
apps/web/core/services/page/workspace-page-version.service.ts
```

Match `ProjectPageService` method shape where possible.

Methods:

- list;
- retrieve;
- create;
- update;
- description;
- archive/restore;
- lock/unlock;
- access;
- favorite;
- duplicate;
- delete;
- versions;
- restore version if supported.

## 6.3 Workspace Page entity

Create:

```text
apps/web/core/store/pages/workspace-page.ts
```

Extend `BasePage`.

Implement:

- workspace permission getters;
- URL redirection: `/{workspaceSlug}/wiki/{pageId}`;
- workspace service callbacks.

## 6.4 Workspace Page store

Create:

```text
apps/web/core/store/pages/workspace-page.store.ts
```

Responsibilities:

- list pages;
- current page details;
- create/update/delete;
- archive;
- favorites;
- filters;
- search;
- hierarchy;
- move/reorder.

Keep API surface as parallel to `ProjectPageStore` as reasonable.

## 6.5 Root store registration

Current core root directly owns `projectPages`.

Required minimal core patch:

```text
apps/web/core/store/root.store.ts
```

Tasks:

- [ ] add `workspacePages`;
- [ ] instantiate it in constructor;
- [ ] reset it on sign out.

This is one of the unavoidable compile-time integration points unless a store registry is introduced later.

## 6.6 Store hook

File:

```text
apps/web/core/hooks/store/use-page-store.ts
```

Add:

```ts
EPageStoreType.WORKSPACE;
```

Return `context.workspacePages`.

## 6.7 Editor setup

Reuse:

- `PageRoot`;
- Page editor header;
- navigation pane;
- asset handling;
- outline;
- version UI;
- lock control;
- offline/syncing badges.

Wiki page detail should set:

```ts
storeType: EPageStoreType.WORKSPACE

webhookConnectionParams: {
  documentType: "workspace_page",
  workspaceSlug,
}
```

No `projectId`.

## 6.8 Sidebar navigation

Current workspace sidebar is driven from constants.

Core patch likely required:

```text
packages/constants/src/workspace.ts
```

Add a Wiki pinned/static navigation item.

Also add `wiki` to reserved workspace slugs if route collision is possible:

```text
RESTRICTED_URLS
```

Prefer putting Wiki under the workspace section near Projects/Work according to current Commercial UX.

## 6.9 i18n

Add keys according to current i18n policy.

At minimum:

- Wiki;
- Public;
- Private;
- Archived;
- Favorites;
- Create page;
- Create sub-page;
- Move;
- Empty states;
- errors/permission messaging.

Follow repository rule: new keys must exist in all language files; English placeholder is acceptable where translations are unavailable.

## 6.10 Existing Wiki assets

Reuse:

```text
apps/web/app/assets/empty-state/wiki/
```

Do not duplicate illustrations.

## 6.11 Company Wiki UI

Reuse the Workspace Wiki store/service, parameterized by the designated workspace slug instead of the current workspace. No separate instance store or service.

Required behavior:

- [ ] canonical links are `/company-wiki/:pageId`;
- [ ] the route resolves `COMPANY_WIKI_WORKSPACE_SLUG` and renders the Workspace Wiki UI against that workspace;
- [ ] workspace switcher does not change loaded Company Wiki content;
- [ ] Company Wiki link is visible/reachable from every workspace;
- [ ] read-only users (or non-members when `COMPANY_WIKI_OPEN_READ=true`) get read-only UI;
- [ ] admin/owner of the designated workspace gets create/edit/reorder/lock/archive controls;
- [ ] editor connects with `documentType: "workspace_page"` and `workspaceSlug = COMPANY_WIKI_WORKSPACE_SLUG`;
- [ ] `projectId` is null for Company Wiki collaboration;
- [ ] search/favorites/recents are user-global (keyed on the page, which lives in the designated workspace);
- [ ] header/breadcrumb visibly says **Company Wiki** to avoid confusing it with current workspace Wiki.

## 6.12 UI conformity implementation tasks

This is a required part of WIKI-03, not a later polish task.

### Reuse existing Plane components

- [ ] list shell uses existing `PagesListView` / `PagesListRoot` patterns;
- [ ] detail uses shared `PageRoot`;
- [ ] document editor uses shared Page editor body/header/toolbar;
- [ ] header uses existing `Header` + `Breadcrumbs`;
- [ ] actions reuse `PageHeaderActions`;
- [ ] sync status reuses `PageSyncingBadge`;
- [ ] access indicator reuses `PageAccessIcon` where applicable;
- [ ] right pane reuses `PageNavigationPaneRoot`;
- [ ] versions reuse existing Page version UI;
- [ ] empty/loading/error states reuse existing Plane components/assets.

### Design system rules

- [ ] use the design system the adjacent `master` Page code already uses; do not introduce `@makeplane/propel` or any preview-only migration inside Wiki PRs;
- [ ] preserve the existing `@plane/ui` wrappers where the reused Page component still uses them;
- [ ] do not perform broad design-system migration inside Wiki PR;
- [ ] no new component library;
- [ ] no hard-coded application colors;
- [ ] use the semantic theme classes available on `master` (`bg-surface-*`, `border-subtle`, `text-primary/secondary/tertiary`, `rounded-sm`, `text-13`, `px-page-x`, or the current equivalents).

### Scope clarity

- [ ] Workspace Wiki breadcrumb visibly identifies current Workspace + Wiki;
- [ ] Company Wiki header/breadcrumb says Company Wiki and never inserts fake workspace context;
- [ ] sidebar labels distinguish `Company Wiki` from `Wiki`;
- [ ] Company Wiki link remains canonical when switching workspaces.

### Responsive/theme

- [ ] light theme;
- [ ] dark theme;
- [ ] 1440px;
- [ ] 1024px;
- [ ] 768px/narrow viewport;
- [ ] no unbounded tree indentation/overflow.

### Visual review

For each new Wiki screen, capture the nearest native Plane reference screen at the same viewport/theme.

Minimum pairs:

```text
Workspace Wiki list  <-> Project Pages list
Wiki page detail     <-> Project Page detail
Wiki header          <-> Page list/detail header
Wiki sidebar item    <-> existing workspace sidebar item
Wiki navigation pane <-> existing Page navigation pane
```

A UI PR must explain any deliberate deviation from the native reference.

## WIKI-03 acceptance

- Wiki route loads natively;
- user can create/open/edit a workspace Page;
- collaborative editor connects as `workspace_page`;
- `/company-wiki` loads the designated workspace's Wiki and non-members get read-only UI when `COMPANY_WIKI_OPEN_READ=true`;
- sidebar navigation works;
- Project Page UI remains unchanged.

---

# 7. WIKI-04 — Core Wiki UX, hierarchy and hardening

## Goal

Finish the production-usable Wiki milestone for **both Workspace Wiki and Company Wiki**.

## 7.1 Wiki navigation sections

Implement:

```text
Favorites
Public
Private
Archived
```

Behavior:

- counts must not leak inaccessible pages;
- filters persist appropriately;
- search applies within effective visibility.

## 7.2 Nested tree

Features:

- [ ] arbitrary depth;
- [ ] expand/collapse;
- [ ] child count where safe;
- [ ] create child;
- [ ] drag/drop;
- [ ] reorder siblings;
- [ ] reparent;
- [ ] optimistic UI only if rollback is robust;
- [ ] server error restores prior UI order.

## 7.3 Parent/child URLs and breadcrumbs

Add:

- hierarchy breadcrumb;
- parent navigation;
- child listing where Commercial UX exposes it.

## 7.4 Archive

- [ ] archive parent and descendants according to agreed semantics;
- [ ] restore behavior explicit;
- [ ] archived tree separate;
- [ ] no active navigation to archived child accidentally.

## 7.5 Version history

Reuse existing pane.

Add/verify:

- workspace page version list;
- preview;
- restore;
- actor/timestamp.

## 7.6 Export

Wire existing export modal/pipeline to workspace Page.

Verify:

- permissions;
- images/assets;
- code/table formatting;
- large document errors.

Nested ZIP export belongs to WIKI-07.

## 7.7 Search integration

- [ ] top-level Wiki search;
- [ ] title/content;
- [ ] private access filtering;
- [ ] highlight/preview without content leakage.

Optional in this PR if current workspace global search can be safely extended:

- include Wiki Pages in command/search palette.

## 7.8 Performance

Test with generated data:

- 1,000 pages;
- 5,000 pages;
- deep hierarchy;
- wide hierarchy.

Measure:

- first Wiki load;
- tree expansion;
- search;
- page open;
- permission-filtered list.

Add indexes only from measured query plans.

## 7.9 Security regression suite

Mandatory test matrix:

```text
User A workspace 1
User B workspace 1
Guest workspace 1
User C workspace 2

Public Wiki Page W1
Private Page owned A
Nested private child
Archived page
Locked page
```

Exercise all IDs from wrong user/workspace/scope against:

- metadata API;
- description API;
- version API;
- archive;
- lock;
- duplicate;
- favorite;
- search;
- websocket.

## 7.10 Visual regression gate

Before WIKI-04 is complete:

- [ ] compare Workspace Wiki against Project Pages at matching viewport/theme;
- [ ] compare Company Wiki against the same Page primitives;
- [ ] confirm no duplicate editor/header/action implementations were introduced;
- [ ] confirm all new tree/Collection-specific controls use current Plane density/tokens;
- [ ] verify light/dark empty states;
- [ ] verify readonly Company Wiki looks native rather than disabled/broken;
- [ ] verify current Project Page visual behavior did not change unintentionally.

## Core milestone gate

WIKI-01..05 merge only when:

- [ ] backend tests pass;
- [ ] live tests pass;
- [ ] web lint/types pass;
- [ ] project Page regression passes;
- [ ] no known BOLA leak;
- [ ] no cross-scope Page/asset/version leak;
- [ ] Company Wiki is readable across workspaces when `COMPANY_WIKI_OPEN_READ=true`, but never anonymously, and never writable by non-members;
- [ ] hierarchy cannot cycle.

---

# 8. WIKI-05 — Collections (Core milestone)

## Goal

Implement current Commercial Wiki Collections including privacy and permission inheritance. Collections are a Core milestone deliverable (decision D6) and apply to Workspace Wiki and Company Wiki alike.

## 8.1 Observe/confirm commercial semantics before schema lock

Resolve:

- one page per Collection vs many;
- default Collection semantics;
- move subtree behavior;
- Collection ACL precedence relative to direct PageShare (WIKI-06) and parent inheritance.

Document the results in `wiki-ce-spec.md` before migration merge (open question Q8).

## 8.2 Models/migrations

Implement selected models:

- PageCollection;
- collection membership/ACL;
- page association/order.

Add:

- default collection constraint;
- indexes;
- same-workspace validation (a Collection belongs to exactly one workspace and never mixes the designated Company Wiki workspace with another).

## 8.3 APIs

Target:

```text
GET/POST /api/workspaces/:slug/page-collections/
GET/PATCH/DELETE /api/workspaces/:slug/page-collections/:id/

POST/DELETE/PATCH collection members
POST/PATCH move page into collection
PATCH reorder collections/pages
```

Exact endpoint names should follow public Plane External API naming if documented before implementation.

## 8.4 Effective ACL inheritance

Centralize:

```text
workspace role
      +
page access
      +
Collection access/member role
      +
parent inheritance
      +
(direct PageShare, added in WIKI-06)
      =
effective capabilities
```

Add a test truth table before implementation. Company Wiki Collections are readable by every authenticated active user when `COMPANY_WIKI_OPEN_READ=true`, and manageable by admin/owner of the designated workspace.

## 8.5 Atomic subtree moves

Moving a parent page must not temporarily expose private descendants.

Use transaction.

Invalidate search/cache entries.

## 8.6 UI

Add:

- Collections section;
- create/edit/delete;
- public/private;
- members;
- View/Comment/Edit roles;
- default Collection;
- reorder;
- page move;
- nested Page tree inside collection.

## WIKI-05 acceptance

Private Collections are invisible outside ACL and permissions propagate consistently to pages/subpages. Collections work for Workspace Wiki and Company Wiki with the same ACL inheritance.

---

# 9. WIKI-06 — Sharing and comments

## Goal

Implement Commercial-style named-user sharing and review collaboration. This builds on the WIKI-05 effective-capability service and adds the direct-share ACL source; it is part of the parity track, not Core.

## 9.1 Migration: PageShare

Add share model per spec.

Tasks:

- [ ] DB model;
- [ ] unique constraint;
- [ ] workspace consistency validation;
- [ ] roles View/Comment/Edit;
- [ ] indexes;
- [ ] serializer/API;
- [ ] activity events.

## 9.2 Extend the effective permission service

Extend the WIKI-05 centralized service with the direct-share source:

```text
get_page_capabilities(user, page)
can_view_page(...)
can_comment_page(...)
can_edit_page(...)
can_manage_page(...)
```

All REST, search, realtime, comments, export, assets must call the same permission logic.

Avoid duplicated permission policy in UI/backend/live.

## 9.3 Sharing UI

Add:

- Share dialog;
- member search;
- role selector;
- remove access;
- current access summary.

Private Page behavior target:

- creator sees page;
- explicitly shared users see according to role;
- unshared users cannot discover it.

## 9.4 Page comments

Add PageComment storage/API.

Features:

- create;
- edit own;
- delete own;
- list;
- reply if product parity requires in first comment release;
- permission roles.

UI:

- navigation pane or Page side panel consistent with current commercial layout.

## 9.5 Realtime permission matrix

Tests:

- View cannot edit;
- Comment can comment but cannot edit document;
- Edit can edit;
- share removal blocks later writes.

## WIKI-06 acceptance

Private pages can be safely shared with specific members using View/Comment/Edit semantics.

---

# 10. WIKI-07 — Templates, publishing, nested export

These features share document cloning/rendering concepts but should still be separate commits inside the PR if practical.

## 10.1 Templates

Backend:

- template model or page-template extension;
- save current page as template;
- create page from template;
- workspace-scoped visibility.

Frontend:

- template picker on create;
- save as template;
- template management.

## 10.2 External publishing

Backend:

- publish entity/token;
- revoke;
- public retrieval;
- safe asset resolution;
- optional external comments in later commit.

Security:

- published page only;
- no traversal into private unpublished relatives;
- rate limiting;
- sanitized output.

Frontend:

- Publish dialog;
- public URL;
- copy;
- revoke;
- preview.

Space/public app may be the appropriate rendering surface; evaluate before implementation.

## 10.3 Nested export

Implement:

- root page selection;
- descendant traversal;
- stable hierarchy ordering;
- PDF/DOCX generation where existing pipeline supports;
- ZIP packaging;
- safe file names;
- per-page access check;
- export size/depth limits;
- asynchronous job if required.

## WIKI-07 acceptance

Commercial-like document reuse/distribution exists without bypassing Wiki ACL.

---

# 11. WIKI-08 — Editor parity

## Goal

Close the largest visible editor gap without forking the Page editor.

Use:

```text
packages/editor/
apps/web/core/hooks/pages/use-extended-editor-extensions.ts
```

Implement as independent sub-features with tests.

## 11.1 Toggle block

- collapsible content;
- serialization;
- collaborative compatibility;
- export rendering.

## 11.2 Tabs block

- horizontal/vertical;
- nested block content;
- Yjs compatibility;
- export fallback.

## 11.3 Mermaid

- fenced or dedicated block;
- safe rendering;
- no arbitrary script execution;
- export behavior.

## 11.4 Wiki Page hierarchy embed

Support commercial-like dynamic embeds:

- children of page;
- parent;
- configurable depth;
- flat page set;
- optional grouping by creator if parity is needed.

Must permission-filter every rendered page.

## 11.5 Media embeds

- image URL;
- video URL;
- safe allowed origins/protocols;
- responsive rendering.

## 11.6 LaTeX

Add only using a safe renderer with no arbitrary code execution.

## 11.7 Draw.io

Treat as integration/extension.

Do not block editor parity core if this requires external marketplace/app plumbing.

## WIKI-08 acceptance

Core editor remains shared by Project Pages and Wiki and new blocks do not regress either surface.

---

# 12. WIKI-09 — Advanced commercial parity

## 12.1 Version comparison

Implement document diff.

Requirements:

- compare selected versions;
- added/removed/changed visualization;
- permission-scoped version retrieval;
- large-page performance.

## 12.2 Page labels UX

Model already exists.

Add:

- label picker;
- filters;
- label search;
- list/tree indicators where useful.

## 12.3 Page/Collection analytics

Track:

- views;
- viewer identity where policy permits;
- timestamps;
- aggregate counts;
- CSV export.

Avoid counting background preload as a view.

Privacy/admin policy must be explicit.

## 12.4 Favorites dedicated view

If not already complete in WIKI-04, align with current commercial dedicated favorites UX.

## 12.5 Comment moderation

If matching current Commercial:

- hide/unhide;
- reason;
- admin permission;
- preserve audit trail.

---

# 13. WIKI-10 — Optional integrations: AI and importers

Not part of Wiki core.

## 13.1 Plane AI/provider work

Later capabilities:

- summarize page;
- edit page by agent;
- AI block;
- natural-language Wiki search;
- label suggestions.

Architecture requirement:

Wiki should expose stable APIs/events so AI can consume it without direct DB coupling.

## 13.2 Notion import

Import HTML ZIP:

- hierarchy;
- pages;
- attachments;
- tables;
- links;
- mapping report.

## 13.3 Confluence import

Import supported XML ZIP:

- spaces/pages;
- hierarchy;
- comments;
- attachments;
- diagram conversion when practical.

---

# 14. Suggested file layout

This is a target, not a mandatory exact structure.

## API

```text
apps/api/plane/app/
  permissions/
    page.py
    workspace_page.py              # if separation chosen
  serializers/
    page.py
    workspace_page.py              # if separation chosen
  views/page/
    base.py                         # existing project path
    version.py                      # existing
    workspace.py                    # new
    workspace_version.py            # optional
    collection.py                   # WIKI-05
    sharing.py                      # WIKI-06
    comments.py                     # WIKI-06
    publish.py                      # WIKI-07
  urls/
    page.py
```

## Web

```text
apps/web/
  app/.../wiki/
  core/
    components/wiki/
    services/page/
      workspace-page.service.ts
      workspace-page-version.service.ts
    store/pages/
      workspace-page.ts
      workspace-page.store.ts
```

Continue reusing `core/components/pages/`; Wiki-specific components should mostly be navigation/tree/collection/share surfaces.

## Live

```text
apps/live/src/
  services/page/
    workspace-page.service.ts
    handler.ts
  types/index.ts
```

## Types

Prefer extending existing Page types instead of duplicating them:

```text
packages/types/src/page/
```

---

# 15. Shared-core patch budget

To keep upstream updates manageable, target as few edits as possible to generic CE files.

Expected unavoidable shared changes:

| Core file                                     | Reason                            |
| --------------------------------------------- | --------------------------------- |
| `apps/web/core/store/root.store.ts`           | register WorkspacePageStore       |
| `apps/web/core/hooks/store/use-page-store.ts` | support WORKSPACE                 |
| `packages/constants/src/workspace.ts`         | native sidebar + restricted route |
| `apps/live/src/types/index.ts`                | workspace_page document type      |
| `apps/live/src/services/page/handler.ts`      | service dispatch                  |
| `apps/api/plane/app/urls/page.py`             | workspace Page routes             |

Preferred extension seam:

| File                                | Use                                        |
| ----------------------------------- | ------------------------------------------ |
| `apps/web/app/routes/extended.ts`   | Wiki route registration                    |
| `use-extended-editor-extensions.ts` | commercial-like editor blocks              |
| `use-pages-pane-extensions.ts`      | comments/extra pane tabs if suitable       |
| `PageService` extended live layer   | shared enterprise-compatible page behavior |

If a PR begins modifying many unrelated Page/project files, stop and refactor toward a workspace adapter.

---

# 16. Database migration policy

- one logical schema change per feature PR;
- reversible migrations;
- no destructive migration in Core Wiki;
- existing project Page rows untouched;
- no automatic `is_global` rewrite without audited query;
- indexes added from measured query plan;
- constraints preferred where PostgreSQL can enforce invariants safely.

Before every migration PR:

```text
python manage.py makemigrations --check
python manage.py migrate
python manage.py migrate <previous migration>
python manage.py migrate
```

Run under repository-supported test stack.

---

# 17. Required validation commands

Follow `AGENTS.md`.

## Web/monorepo

```bash
pnpm check
```

Targeted during development:

```bash
pnpm check:lint
pnpm check:types
pnpm turbo run check --filter=web
```

Use exact available package commands if filters differ.

## Backend

```bash
docker compose -f docker-compose-test.yml up --build --abort-on-container-exit --exit-code-from api-tests
```

Targeted subsets are acceptable during development, but Core milestone must run the relevant contract/security regression suite.

---

# 18. Review checklist for every implementation PR

## Architecture

- [ ] Reuses Page model/editor instead of duplicating.
- [ ] Workspace logic isolated from Project Page logic.
- [ ] Uses extension seam where available.
- [ ] No unnecessary generic plugin framework.

## Security

- [ ] Workspace-scoped lookup.
- [ ] `is_global=True` enforced.
- [ ] No ID-only lookup.
- [ ] Private page not leaked in list/search/count.
- [ ] Asset access considered.
- [ ] Websocket access considered.
- [ ] Recursive operations cycle-safe.

## Regression

- [ ] Project Page behavior unchanged.
- [ ] Existing page routes unchanged.
- [ ] Existing project permissions unchanged.
- [ ] Existing project realtime collaboration unchanged.

## Tests

- [ ] positive path;
- [ ] permission denial;
- [ ] cross-workspace BOLA;
- [ ] malformed hierarchy;
- [ ] regression.

---

# 19. Suggested implementation order for coding agents

Do not parallelize tasks that modify the same core file unless branches are carefully coordinated.

Safe parallelism after WIKI-01 API contract is stable:

```text
Agent A: WIKI-02 Live
Agent B: WIKI-03 Web service/store/routes
Agent C: security/contract tests for WIKI-01
```

Merge order:

```text
WIKI-00
WIKI-01
WIKI-02
WIKI-03
WIKI-04
WIKI-05
```

For parity phase:

- WIKI-05 Collections establishes the reusable effective-capability engine;
- WIKI-06 sharing extends that engine with the direct PageShare source;
- WIKI-07 can partially run in parallel after permissions stabilize;
- WIKI-08 editor blocks can run mostly independently;
- WIKI-09 after core data/access models settle.

---

# 20. Proposed PR naming

```text
feat(wiki): add workspace page backend
feat(wiki): add workspace page realtime collaboration
feat(wiki): add workspace wiki web app
feat(wiki): add hierarchy search and core hardening
feat(wiki): add collections and inherited access
feat(wiki): add page sharing and comments
feat(wiki): add templates publishing and nested export
feat(editor): add wiki commercial-parity blocks
feat(wiki): add version diff labels and analytics
```

Keep commits similarly scoped.

---

# 21. Review gates before implementation starts

Before WIKI-01 code begins, reviewer should approve these architecture decisions:

- [ ] Reuse `Page`; no duplicate Wiki content table.
- [ ] Project Page = `is_global=False, workspace!=NULL`.
- [ ] Workspace Wiki = `is_global=True, workspace!=NULL`.
- [ ] Company Wiki = Workspace Wiki on the workspace fixed by `COMPANY_WIKI_WORKSPACE_SLUG` (`is_global=True, workspace!=NULL`); `COMPANY_WIKI_OPEN_READ` controls the read-only open-read override.
- [ ] Do not create a hidden/fake workspace for Company Wiki (the designated workspace is real and visible).
- [ ] Do not migrate `Page.workspace` to nullable, and do not add an instance scope, `/api/instance/wiki` API, `instance_page` live type, `InstancePagePermission` or `InstancePageService`.
- [ ] Wiki implemented as native compile-time extension, not external Plane App.
- [ ] Use existing Page editor/live stack.
- [ ] Core Wiki milestone = WIKI-00..05 (Collections is core, decision D6).
- [ ] Sharing is parity-track (WIKI-06), after Collections; the WIKI-05 capability service anticipates direct shares.
- [ ] AI/importers are not Core Wiki blockers.
- [ ] No generic plugin framework in P0.

Once these are approved, WIKI-01 can be converted into granular GitHub issues/tasks and implementation can start.

---

# 22. Upstream baseline and sync policy

## Current decision

Implementation base:

```text
r2d-ai/plane:master
5f7d92784c403f76284f0f16718f320221dc7fec
release v1.4.2
```

This SHA matches `makeplane/plane:master` v1.4.2. The earlier `preview` baseline (`02c19e1341…`) was dropped on 2026-09-22 after its deployment gate failed on preview-specific infrastructure (Caddy `Caddyfile.ce` server-block ordering, missing `plane-live` env values). The switch to `master` is an explicit architecture decision; see §1.3 and spec §31.6.

## Why `master` v1.4.2

- the fork's `master` is synced from upstream and is the default branch;
- it is the stable release the deployment stack is validated against;
- no preview-only toolchain movement (Caddy/nginx swap, Node/pnpm churn, Docker hardening, pinned Quay MinIO image) has to be reconciled before Wiki work;
- the Page model/store/live seams needed by Wiki are present in v1.4.2.

## Preview-specific work is deferred

The preview line's UI/design-system migration (React 19 / React Router 8 / Propel) is **not** part of Wiki. Do not introduce preview-only components or design-system changes inside Wiki PRs; that migration is a separate future effort.

## Sync rule during Wiki development

Do not rebase every Wiki PR onto a moving upstream branch.

Use dedicated upstream-sync PRs:

1. compare the baselined SHA with the latest upstream `master` (and, separately, evaluate `preview`);
2. classify changes:
   - security;
   - Page/editor;
   - design system;
   - migrations;
   - deployment;
   - unrelated;
3. run baseline + Wiki regression suite;
4. merge the upstream sync only after review.

This keeps coding-agent work deterministic and avoids mixing feature defects with upstream churn.
