# Wiki for Plane CE — Implementation Plan

> Status: **Draft for review**
>
> Depends on: [wiki-ce-spec.md](./wiki-ce-spec.md)
>
> Target branch for implementation: create feature branches from `preview` after this plan is approved.
>
> Planning principle: small reviewable PRs, no large “Wiki mega-PR”.

---

## 1. Implementation strategy

### 1.1 Architecture

Use Plane's existing Page stack as the kernel.

```text
                         Page
                          │
              ┌───────────┴────────────┐
              │                        │
        Project Page               Workspace Wiki
        is_global=false            is_global=true
              │                        │
         ProjectPage                Workspace
              │                        │
         Project RBAC              Wiki ACL
              │                        │
              └────────────┬───────────┘
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

### 1.3 Anti-goals

Do not:

- create a separate Wiki service;
- create a second editor;
- create `WikiPage` duplicating `Page`;
- remove project scoping from current Page code;
- implement a generic plugin framework as part of Wiki P0;
- depend on Plane AI;
- depend on a vector database;
- mix Collections/Comments/Publish into the first backend PR.

---

# 2. PR dependency graph

```text
WIKI-01 Backend workspace-page core
          │
          ├──────────────┐
          ▼              ▼
WIKI-02 Live         WIKI-03 Web shell/store
collaboration             │
          └──────┬────────┘
                 ▼
        WIKI-04 Core UX + hardening
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
 WIKI-05     WIKI-06    WIKI-07
 Sharing &   Collections Templates/
 Comments                Publish/Export
       └─────────┬──────────┘
                 ▼
         WIKI-08 Editor parity
                 │
                 ▼
       WIKI-09 Advanced parity
                 │
                 ▼
       WIKI-10 AI/importers optional
```

WIKI-01 through WIKI-04 form the **Core Wiki production milestone**.

WIKI-05 onward form the **Commercial parity track**.

---

# 3. WIKI-01 — Workspace Page backend core

## Goal

Provide secure workspace-level Page APIs without changing Project Page behavior.

## 3.1 Add workspace-specific serializer path

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

## 3.2 Add WorkspacePagePermission

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

## 3.3 Add workspace Page queryset/service

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

## 3.4 Add workspace Page endpoints

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

## 3.5 Hierarchy validator

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

## 3.6 Recursive archive/restore

Tasks:

- [ ] Verify existing recursive CTE is safe for Wiki.
- [ ] Add visited/cycle-safe behavior if needed.
- [ ] Ensure only Wiki descendants in same workspace are affected.
- [ ] Test deep trees.

## 3.7 Favorites

Current project favorites are project-scoped.

Tasks:

- [ ] Verify favorite model can reference a Wiki Page without Project relation.
- [ ] If yes, add workspace favorite endpoint.
- [ ] If no, extend model minimally.
- [ ] List favorites permission-safely.

## 3.8 Search

Tasks:

- [ ] Search `name`.
- [ ] Search `description_stripped`.
- [ ] Filter effective access before response.
- [ ] Avoid snippets from inaccessible pages.
- [ ] Use existing search service if it can safely index global pages.
- [ ] Do not introduce vector search.

## 3.9 External API compatibility

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

## 3.10 Backend tests

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
- [ ] project page regression.

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

# 4. WIKI-02 — Workspace Page realtime collaboration

## Goal

Support commercial-like realtime collaborative editing for Wiki using the existing Hocuspocus/Yjs service.

## 4.1 Extend document types

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

## 4.2 Add WorkspacePageService

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

## 4.3 Extend service handler

File:

```text
apps/live/src/services/page/handler.ts
```

Tasks:

- [ ] dispatch `project_page`;
- [ ] dispatch `workspace_page`;
- [ ] reject unknown document types.

## 4.4 Authentication/authorization

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

## 4.5 Revocation behavior

At minimum:

- [ ] new writes after access revocation fail;
- [ ] current session receives an error/force close if persistence becomes forbidden.

Later optimization can actively disconnect sessions when ACL changes.

## 4.6 Tests

Add live tests for:

- [ ] load workspace page;
- [ ] initialize HTML -> Yjs binary;
- [ ] persist update;
- [ ] unauthorized workspace;
- [ ] private page no access;
- [ ] locked page;
- [ ] read-only user when sharing exists;
- [ ] title sync authorization;
- [ ] project_page regression.

## WIKI-02 acceptance

Wiki and Project Pages can use the same live service concurrently with separate secure document types.

---

# 5. WIKI-03 — Web Wiki shell, store and editor

## Goal

Expose first-class Workspace Wiki UI using existing Page components.

## 5.1 Routes through existing extension seam

Use:

```text
apps/web/app/routes/extended.ts
```

Target:

```text
/:workspaceSlug/wiki
/:workspaceSlug/wiki/:pageId
```

Create route components in an isolated Wiki area, for example:

```text
apps/web/app/(all)/[workspaceSlug]/wiki/
  (list)/page.tsx
  (detail)/[pageId]/page.tsx
  ...
```

Actual physical path should follow current React Router conventions and route config constraints.

## 5.2 Workspace page service

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

## 5.3 Workspace Page entity

Create:

```text
apps/web/core/store/pages/workspace-page.ts
```

Extend `BasePage`.

Implement:

- workspace permission getters;
- URL redirection: `/{workspaceSlug}/wiki/{pageId}`;
- workspace service callbacks.

## 5.4 Workspace Page store

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

## 5.5 Root store registration

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

## 5.6 Store hook

File:

```text
apps/web/core/hooks/store/use-page-store.ts
```

Add:

```ts
EPageStoreType.WORKSPACE
```

Return `context.workspacePages`.

## 5.7 Editor setup

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

## 5.8 Sidebar navigation

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

## 5.9 i18n

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

## 5.10 Existing Wiki assets

Reuse:

```text
apps/web/app/assets/empty-state/wiki/
```

Do not duplicate illustrations.

## WIKI-03 acceptance

- Wiki route loads natively;
- user can create/open/edit a workspace Page;
- collaborative editor connects as `workspace_page`;
- sidebar navigation works;
- Project Page UI remains unchanged.

---

# 6. WIKI-04 — Core Wiki UX, hierarchy and hardening

## Goal

Finish the production-usable Wiki milestone.

## 6.1 Wiki navigation sections

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

## 6.2 Nested tree

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

## 6.3 Parent/child URLs and breadcrumbs

Add:

- hierarchy breadcrumb;
- parent navigation;
- child listing where Commercial UX exposes it.

## 6.4 Archive

- [ ] archive parent and descendants according to agreed semantics;
- [ ] restore behavior explicit;
- [ ] archived tree separate;
- [ ] no active navigation to archived child accidentally.

## 6.5 Version history

Reuse existing pane.

Add/verify:

- workspace page version list;
- preview;
- restore;
- actor/timestamp.

## 6.6 Export

Wire existing export modal/pipeline to workspace Page.

Verify:

- permissions;
- images/assets;
- code/table formatting;
- large document errors.

Nested ZIP export belongs to WIKI-07.

## 6.7 Search integration

- [ ] top-level Wiki search;
- [ ] title/content;
- [ ] private access filtering;
- [ ] highlight/preview without content leakage.

Optional in this PR if current workspace global search can be safely extended:

- include Wiki Pages in command/search palette.

## 6.8 Performance

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

## 6.9 Security regression suite

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

Exercise all IDs from wrong user/workspace against:

- metadata API;
- description API;
- version API;
- archive;
- lock;
- duplicate;
- favorite;
- search;
- websocket.

## Core milestone gate

WIKI-01..04 merge only when:

- [ ] backend tests pass;
- [ ] live tests pass;
- [ ] web lint/types pass;
- [ ] project Page regression passes;
- [ ] no known BOLA leak;
- [ ] hierarchy cannot cycle.

---

# 7. WIKI-05 — Shared pages and comments

## Goal

Implement Commercial-style named-user sharing and review collaboration.

## 7.1 Migration: PageShare

Add share model per spec.

Tasks:

- [ ] DB model;
- [ ] unique constraint;
- [ ] workspace consistency validation;
- [ ] roles View/Comment/Edit;
- [ ] indexes;
- [ ] serializer/API;
- [ ] activity events.

## 7.2 Effective permission service

Before adding multiple ACL sources, extract a centralized service:

```text
get_page_capabilities(user, page)
can_view_page(...)
can_comment_page(...)
can_edit_page(...)
can_manage_page(...)
```

All REST, search, realtime, comments, export, assets must call the same permission logic.

Avoid duplicated permission policy in UI/backend/live.

## 7.3 Sharing UI

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

## 7.4 Page comments

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

## 7.5 Realtime permission matrix

Tests:

- View cannot edit;
- Comment can comment but cannot edit document;
- Edit can edit;
- share removal blocks later writes.

## WIKI-05 acceptance

Private pages can be safely shared with specific members using View/Comment/Edit semantics.

---

# 8. WIKI-06 — Collections

## Goal

Implement current Commercial Wiki Collections including privacy and permission inheritance.

## 8.1 Observe/confirm commercial semantics before schema lock

Resolve:

- one page per Collection vs many;
- default Collection semantics;
- move subtree behavior;
- direct share vs Collection ACL precedence.

Document the results in `wiki-ce-spec.md` before migration merge.

## 8.2 Models/migrations

Implement selected models:

- PageCollection;
- collection membership/ACL;
- page association/order.

Add:

- default collection constraint;
- indexes;
- same-workspace validation.

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
direct PageShare
      +
Collection access/member role
      +
parent inheritance
      =
effective capabilities
```

Add test truth table before implementation.

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

## WIKI-06 acceptance

Private Collections are invisible outside ACL and permissions propagate consistently to pages/subpages.

---

# 9. WIKI-07 — Templates, publishing, nested export

These features share document cloning/rendering concepts but should still be separate commits inside the PR if practical.

## 9.1 Templates

Backend:

- template model or page-template extension;
- save current page as template;
- create page from template;
- workspace-scoped visibility.

Frontend:

- template picker on create;
- save as template;
- template management.

## 9.2 External publishing

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

## 9.3 Nested export

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

# 10. WIKI-08 — Editor parity

## Goal

Close the largest visible editor gap without forking the Page editor.

Use:

```text
packages/editor/
apps/web/core/hooks/pages/use-extended-editor-extensions.ts
```

Implement as independent sub-features with tests.

## 10.1 Toggle block

- collapsible content;
- serialization;
- collaborative compatibility;
- export rendering.

## 10.2 Tabs block

- horizontal/vertical;
- nested block content;
- Yjs compatibility;
- export fallback.

## 10.3 Mermaid

- fenced or dedicated block;
- safe rendering;
- no arbitrary script execution;
- export behavior.

## 10.4 Wiki Page hierarchy embed

Support commercial-like dynamic embeds:

- children of page;
- parent;
- configurable depth;
- flat page set;
- optional grouping by creator if parity is needed.

Must permission-filter every rendered page.

## 10.5 Media embeds

- image URL;
- video URL;
- safe allowed origins/protocols;
- responsive rendering.

## 10.6 LaTeX

Add only using a safe renderer with no arbitrary code execution.

## 10.7 Draw.io

Treat as integration/extension.

Do not block editor parity core if this requires external marketplace/app plumbing.

## WIKI-08 acceptance

Core editor remains shared by Project Pages and Wiki and new blocks do not regress either surface.

---

# 11. WIKI-09 — Advanced commercial parity

## 11.1 Version comparison

Implement document diff.

Requirements:

- compare selected versions;
- added/removed/changed visualization;
- permission-scoped version retrieval;
- large-page performance.

## 11.2 Page labels UX

Model already exists.

Add:

- label picker;
- filters;
- label search;
- list/tree indicators where useful.

## 11.3 Page/Collection analytics

Track:

- views;
- viewer identity where policy permits;
- timestamps;
- aggregate counts;
- CSV export.

Avoid counting background preload as a view.

Privacy/admin policy must be explicit.

## 11.4 Favorites dedicated view

If not already complete in WIKI-04, align with current commercial dedicated favorites UX.

## 11.5 Comment moderation

If matching current Commercial:

- hide/unhide;
- reason;
- admin permission;
- preserve audit trail.

---

# 12. WIKI-10 — Optional integrations: AI and importers

Not part of Wiki core.

## 12.1 Plane AI/provider work

Later capabilities:

- summarize page;
- edit page by agent;
- AI block;
- natural-language Wiki search;
- label suggestions.

Architecture requirement:

Wiki should expose stable APIs/events so AI can consume it without direct DB coupling.

## 12.2 Notion import

Import HTML ZIP:

- hierarchy;
- pages;
- attachments;
- tables;
- links;
- mapping report.

## 12.3 Confluence import

Import supported XML ZIP:

- spaces/pages;
- hierarchy;
- comments;
- attachments;
- diagram conversion when practical.

---

# 13. Suggested file layout

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
    sharing.py                      # WIKI-05
    comments.py                     # WIKI-05
    collection.py                   # WIKI-06
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

# 14. Shared-core patch budget

To keep upstream updates manageable, target as few edits as possible to generic CE files.

Expected unavoidable shared changes:

| Core file | Reason |
| --- | --- |
| `apps/web/core/store/root.store.ts` | register WorkspacePageStore |
| `apps/web/core/hooks/store/use-page-store.ts` | support WORKSPACE |
| `packages/constants/src/workspace.ts` | native sidebar + restricted route |
| `apps/live/src/types/index.ts` | workspace_page document type |
| `apps/live/src/services/page/handler.ts` | service dispatch |
| `apps/api/plane/app/urls/page.py` | workspace Page routes |

Preferred extension seam:

| File | Use |
| --- | --- |
| `apps/web/app/routes/extended.ts` | Wiki route registration |
| `use-extended-editor-extensions.ts` | commercial-like editor blocks |
| `use-pages-pane-extensions.ts` | comments/extra pane tabs if suitable |
| `PageService` extended live layer | shared enterprise-compatible page behavior |

If a PR begins modifying many unrelated Page/project files, stop and refactor toward a workspace adapter.

---

# 15. Database migration policy

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

# 16. Required validation commands

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

# 17. Review checklist for every implementation PR

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

# 18. Suggested implementation order for coding agents

Do not parallelize tasks that modify the same core file unless branches are carefully coordinated.

Safe parallelism after WIKI-01 API contract is stable:

```text
Agent A: WIKI-02 Live
Agent B: WIKI-03 Web service/store/routes
Agent C: security/contract tests for WIKI-01
```

Merge order:

```text
WIKI-01
WIKI-02
WIKI-03
WIKI-04
```

For parity phase:

- WIKI-05 sharing establishes the reusable permission engine;
- WIKI-06 Collections must build on that engine;
- WIKI-07 can partially run in parallel after permissions stabilize;
- WIKI-08 editor blocks can run mostly independently;
- WIKI-09 after core data/access models settle.

---

# 19. Proposed PR naming

```text
feat(wiki): add workspace page backend
feat(wiki): add workspace page realtime collaboration
feat(wiki): add workspace wiki web app
feat(wiki): add hierarchy search and core hardening
feat(wiki): add page sharing and comments
feat(wiki): add collections and inherited access
feat(wiki): add templates publishing and nested export
feat(editor): add wiki commercial-parity blocks
feat(wiki): add version diff labels and analytics
```

Keep commits similarly scoped.

---

# 20. Review gates before implementation starts

Before WIKI-01 code begins, reviewer should approve these architecture decisions:

- [ ] Reuse `Page`; no `WikiPage`.
- [ ] `Page.is_global=True` denotes workspace Wiki.
- [ ] Wiki implemented as native compile-time extension, not external Plane App.
- [ ] Use existing Page editor/live stack.
- [ ] Core Wiki milestone = WIKI-01..04.
- [ ] Sharing/Collections added after core, but permission architecture anticipates them.
- [ ] AI/importers are not Core Wiki blockers.
- [ ] No generic plugin framework in P0.

Once these are approved, WIKI-01 can be converted into granular GitHub issues/tasks and implementation can start.
