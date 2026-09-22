# Wiki for Plane CE — Product & Technical Specification

> Status: **Draft for review**
>
> Target repository: `r2d-ai/plane`
>
> Baseline: `r2d-ai/plane:preview` pinned at `02c19e1341d93141e8ad7b3278298adce208bafc` for implementation review. Stable fallback: upstream `makeplane/plane:master` release `v1.4.2` at `5f7d92784c403f76284f0f16718f320221dc7fec`.
>
> Research baseline: **2026-09-22**
>
> Goal: implement a workspace-level Wiki in Plane CE with behavior and UX as close as practical to Plane Commercial, while reusing CE's existing Page/editor/live-collaboration foundations and minimizing long-term upstream merge conflicts.

---

## 1. Executive decision

### 1.1 Wiki should be a native Plane feature, not a separate application

Plane CE already contains most of the primitives required for Wiki:

- a workspace-owned `Page` model;
- `Page.parent` for nesting;
- `Page.sort_order` for ordering;
- `Page.is_global`, which is currently unused by the CE project-page path and is a strong fit for distinguishing workspace Wiki pages;
- `PageVersion`;
- page locking;
- page access/public-private state;
- archive/restore;
- favorites;
- rich document editor;
- collaborative Yjs/Hocuspocus document persistence;
- project page stores/services/UI that are already mostly generic;
- explicit `workspace_page` in shared webhook/query parameter types;
- Wiki-specific empty-state assets in the web app.

The implementation should therefore **reuse the Page entity and Page engine** rather than introduce a second `WikiPage` model.

Recommended scope discriminator:

```text
Project Page
  Page.is_global = false
  Page.workspace = workspace
  Page <-> ProjectPage <-> Project

Workspace Wiki Page
  Page.is_global = true
  Page.workspace = workspace
  no ProjectPage relation required

Instance / Company Wiki Page
  Page.is_global = true
  Page.workspace = NULL
  no ProjectPage relation
  readable by every active authenticated user in the instance
```

This keeps all three surfaces on the same editor, versioning, asset, activity, export, and realtime primitives.

The Instance / Company Wiki is a fork-specific extension. Plane's public Commercial documentation currently describes Wiki as **workspace-level**, even when it is positioned as company-wide knowledge. Because this deployment intentionally uses multiple workspaces for separate departments, a true instance scope is required above Plane's commercial workspace scope.

Do **not** implement Instance Wiki with a fake/hidden workspace. A synthetic workspace would pollute workspace membership, search, labels, assets, navigation, deletion semantics, and could become visible through unrelated workspace APIs. Instead, allow `Page.workspace=NULL` only for instance-level global pages and explicitly support that scope in Page-adjacent models/services.

### 1.2 Do not implement Wiki as a Plane App / external plugin

Plane now documents “Plane Apps” as a beta extension platform based on:

- OAuth 2.0;
- API access;
- webhooks;
- bot/user tokens;
- external services using the Node/Python SDKs.

That extension mechanism is suitable for agents, automation, integrations, dashboards, and webhook handlers. It does **not** provide a documented mechanism for injecting a first-class native workspace route, sidebar entry, MobX store, editor extensions, Django models, or Hocuspocus document type.

Therefore Wiki cannot achieve commercial-like native UX as an external Plane App.

### 1.3 Use Plane's existing compile-time extension seams wherever possible

The CE source contains clear extension seams that appear designed to separate CE from commercial code, including:

- `apps/web/app/routes/extended.ts`;
- `packages/types/src/page/extended.ts`;
- `apps/web/core/hooks/pages/use-extended-editor-extensions.ts`;
- `apps/web/core/hooks/pages/use-pages-pane-extensions.ts`;
- `apps/live/src/services/page/extended.service.ts`, which explicitly notes that the implementation exists in the enterprise repository;
- other `extended.*` hooks/types across the monorepo.

The Wiki implementation should behave like a **compile-time native extension module**:

1. put Wiki-specific code in isolated Wiki/workspace-page modules;
2. register through existing extension seams when available;
3. make the smallest possible changes to shared CE core;
4. avoid a new generic plugin framework in the first Wiki milestone.

A generic feature-plugin registry can be evaluated later if Workflow, Portal, Teamspaces, etc. repeatedly require the same injection points.

---

## 2. Product objective

Add a first-class **Wiki** application at workspace scope.

Primary URL surface:

```text
/:workspaceSlug/wiki
/:workspaceSlug/wiki/:pageId
```

The user should experience Wiki as a sibling of Work/Projects rather than as a special Project Page.

Primary use cases:

- company policies;
- onboarding documents;
- runbooks;
- engineering references;
- architecture decisions;
- meeting/decision records;
- operating procedures;
- cross-project documentation.

Project Pages continue to exist and remain scoped to individual projects.

---

## 3. Commercial parity target

The target is behavioral parity with the public Plane Wiki feature set as of 2026-09-22, subject to capabilities available in CE.

### 3.1 Core Wiki

| Capability | Commercial behavior / public description | CE target |
| --- | --- | --- |
| Workspace Wiki | Wiki pages live at workspace level | Required |
| Nested pages | Deep parent/child hierarchy | Required |
| Reordering | Drag-and-drop/order within hierarchy | Required |
| Public pages | Workspace-visible documentation | Required |
| Private pages | Creator/private visibility | Required |
| Shared pages | Named users with scoped access | Required after core |
| Archive | Archived Wiki section | Required |
| Favorites | Dedicated favorite access | Required |
| Search | Search Wiki by title/content | Required |
| Rich editor | Existing Page editor | Required |
| Realtime collaboration | Collaborative editing | Required |
| Work embeds | Link/embed work items and related execution context | Required |
| Automatic outline/TOC | Existing editor outline | Required |
| Page locking | Lock a page against edits | Required |
| Version history | Browse and restore prior versions | Required |
| Version comparison | Compare changes between versions | Parity phase |
| Page comments | Collaborative review/comments | Parity phase |
| Publish externally | Public URL, external viewing/commenting where supported | Parity phase |
| Templates | Workspace/page templates | Parity phase |
| Export | Page export | Required |
| Nested export | Export page hierarchy as ZIP with PDF/DOCX output | Parity phase |
| Labels | Labels on Wiki pages | Parity phase |
| Page analytics | Page/Collection view analytics | Later parity |
| Collections | Group pages into Collections | Required parity |
| Collection ACL | Public/private collection and View/Comment/Edit roles | Required parity |
| ACL inheritance | Collection -> Page -> child page inheritance | Required parity |
| Tabs/toggles | Rich page organization blocks | Editor parity |
| Page hierarchy embeds | Embed parent/children or page lists | Editor parity |
| Mermaid | Diagram rendering | Editor parity |
| Draw.io | Diagram integration | Optional integration parity |
| LaTeX | Formula/document block support | Editor parity where feasible |
| URL media embeds | Images/video and rich embeds | Editor parity |
| MS Office in-place editing | Edit attached Office files via desktop Office | Later/optional |
| AI Block | Inline generated content | Deferred to Plane AI/provider work |
| AI editing/search | AI native Wiki assistance | Deferred |
| Confluence/Notion import | Documentation import | Deferred integration phase |

### 3.2 Minimum production milestone

The first production-usable milestone does **not** need every advanced commercial feature.

It must include:

1. workspace Wiki navigation;
2. list/tree view;
3. create/read/update/archive/delete;
4. public/private access;
5. nested hierarchy;
6. drag-and-drop reordering;
7. rich editor;
8. realtime collaboration;
9. lock/unlock;
10. favorites;
11. version history + restore;
12. attachments/assets;
13. title/content search;
14. export using the existing Page export pipeline;
15. strict workspace/page authorization;
16. hierarchy cycle prevention;
17. test coverage for REST and websocket access.

Shared-page ACL and Collections are the next parity milestone and must be considered in the core schema/permission design from the start.

---

## 4. Existing CE foundation

### 4.1 Page model

Current `apps/api/plane/db/models/page.py` already provides key fields:

- `workspace`;
- `name`;
- `description_json`;
- `description_binary`;
- `description_html`;
- `description_stripped`;
- `owned_by`;
- `access`;
- `color`;
- `labels`;
- `parent`;
- `archived_at`;
- `is_locked`;
- `view_props`;
- `logo_props`;
- `is_global`;
- `projects` through `ProjectPage`;
- move metadata;
- `sort_order`;
- external import IDs.

The existing schema is already compatible with workspace Wiki pages.

### 4.2 Page versioning

`PageVersion` already stores:

- workspace;
- page;
- save timestamp;
- owner;
- binary/html/json/stripped document forms;
- sub-page metadata.

No second Wiki version model should be created.

### 4.3 Project Page path

Current project Page APIs are project-scoped and enforce `ProjectPage` membership.

The existing serializer create path assumes `project_id` and creates `ProjectPage`; therefore workspace Wiki requires a separate workspace serializer/view/service path rather than weakening project scoping.

### 4.4 Existing reusable web UI

The CE web app already contains reusable Page components for:

- editor root/body/header;
- toolbar;
- list filters/order/search;
- create/delete/export modals;
- page header actions;
- lock control;
- favorite control;
- archive badge;
- sync/offline indicators;
- navigation pane;
- outline;
- assets;
- document info;
- version history;
- version restore views.

Wiki should reuse these components.

### 4.5 Existing reusable stores

`BasePage` already encapsulates most page operations.

Current `ProjectPage` extends it with:

- project-aware service calls;
- project role permissions;
- project URL generation.

Wiki should add `WorkspacePage` using the same base class.

### 4.6 Existing live collaboration

The live service already has:

- Hocuspocus;
- Yjs binary storage;
- Redis integration;
- REST-backed page persistence;
- title synchronization;
- database extension;
- asset resolution.

Current limitation:

`apps/live/src/types/index.ts` currently recognizes only `"project_page"` as a document type even though shared request types already anticipate `workspace_page`.

Workspace Wiki should extend the existing live pipeline, not create another collaboration service.

---

## 5. Data model

### 5.1 Workspace Wiki Page

Reuse `Page`.

Invariant for Wiki:

```text
page.workspace_id = target workspace
page.is_global = true
page.parent is null OR:
  parent.workspace_id = page.workspace_id
  parent.is_global = true
```

A workspace Wiki page must not require a `ProjectPage` row.

### 5.2 Project Page compatibility

Project pages remain:

```text
page.is_global = false
active ProjectPage relation exists
```

No migration should rewrite existing project-page content unless required to normalize legacy data.

### 5.3 Shared page access

Commercial Wiki supports sharing private pages with named members.

Add an explicit page-sharing model rather than overloading `Page.access`.

Proposed logical model:

```text
PageShare
- id
- workspace_id
- page_id
- member_id
- role: VIEW | COMMENT | EDIT
- created_by
- created_at
- updated_at
```

Constraints:

- unique active share per `(page_id, member_id)`;
- shared member must belong to the same workspace;
- share page must be a workspace Wiki page;
- `EDIT` implies view/comment;
- `COMMENT` implies view;
- owner does not need a share row.

Exact naming may be adjusted to Plane conventions during implementation.

### 5.4 Page comments

Project work-item comments are not a safe direct substitute for Page comments because they carry work-item-specific assumptions.

Introduce a Page-comment model or a generic entity-comment abstraction only if a safe existing generic abstraction exists at implementation time.

Minimum logical fields:

```text
PageComment
- id
- workspace_id
- page_id
- actor_id
- body / description formats
- parent_id (thread/reply if supported)
- resolved_at / resolved_by (if matching UX)
- edited_at
- created_at
- updated_at
```

Permissions must derive from effective Page access.

### 5.5 Collections

Collections are a workspace-level Wiki grouping primitive.

Proposed logical entities:

```text
PageCollection
- id
- workspace_id
- name
- description
- logo/icon props
- access: PUBLIC | PRIVATE
- sort_order
- is_default
- created_by

PageCollectionMember
- collection_id
- member_id
- role: VIEW | COMMENT | EDIT

PageCollectionPage
- collection_id
- page_id
- sort_order
```

Important behavior:

- a default collection may exist per workspace;
- moving pages between collections must be explicit;
- private collection membership is not visible to unauthorized users;
- collection role is inherited by pages;
- descendants inherit restrictions through their parent hierarchy;
- implementation must define a single deterministic effective-permission algorithm.

Whether `PageCollectionPage` is a join model or a direct FK should be selected after confirming whether Commercial permits a page in multiple Collections. The first implementation must not accidentally support multi-collection membership if the product UX does not.

---

## 6. Permission model

### 6.1 Never reuse `ProjectPagePermission` for Wiki

`ProjectPagePermission` is intentionally project-scoped and validates active `ProjectPage` membership.

Wiki needs a dedicated `WorkspacePagePermission`.

### 6.2 Base rules

For every Wiki lookup:

```text
workspace.slug = URL workspaceSlug
page.workspace_id = resolved workspace
page.is_global = true
page.deleted_at IS NULL
```

Never perform `Page.objects.get(id=page_id)` followed by a later workspace check.

This is a hard BOLA/IDOR invariant.

### 6.3 Effective access

The effective access function should be centralized.

Pseudo-logic:

```text
effective_access(user, page):

  if user is not an active workspace member:
      DENY

  if user == page.owner:
      OWNER

  inherited = collection/page-parent inherited access
  direct = page share role, if any

  if page is PRIVATE:
      allow max(inherited, direct)
      otherwise DENY

  if page is PUBLIC:
      baseline from workspace role
      combine with inherited/direct restrictions
```

The exact baseline edit policy should follow Plane CE role semantics at implementation time.

### 6.4 Required operations

Permission checks must distinguish at least:

- view;
- comment;
- edit content;
- rename/update metadata;
- create child;
- reorder/move;
- share;
- lock/unlock;
- archive/restore;
- delete;
- publish;
- manage collection membership.

Do not implement access as a single boolean.

### 6.5 Private page confidentiality

For unauthorized users, private pages/collections should behave as nonexistent wherever practical:

- not returned in lists;
- not returned in search;
- not shown in recents;
- not exposed through parent/child tree metadata;
- not leaked in counts;
- no asset URL leakage;
- no websocket document access.

---

## 7. Hierarchy invariants

Wiki supports deep nesting, so hierarchy validation is security- and reliability-critical.

On create/move/update parent:

1. parent cannot equal page;
2. parent must exist;
3. parent must belong to same workspace;
4. parent must be a Wiki page;
5. parent must be visible/editable according to move semantics;
6. parent cannot be a descendant of page;
7. collection compatibility/inheritance must be validated;
8. archived state behavior must be explicit.

### 7.1 Cycle prevention

A -> B -> A must be impossible.

Do not rely only on UI drag/drop validation.

Server-side validation is mandatory.

Recursive archive/export/tree queries must be safe even if legacy/corrupt cycles exist.

### 7.2 Sort ordering

All order-by input must use a strict allowlist.

Reordering should use the existing float sort-order convention unless a more current Plane utility exists.

Concurrent reorders should avoid duplicate/unstable order when possible.

---

## 8. REST API

### 8.1 Internal CE API

Target internal endpoints:

```text
GET    /api/workspaces/:workspace_slug/pages/
POST   /api/workspaces/:workspace_slug/pages/

GET    /api/workspaces/:workspace_slug/pages/:page_id/
PATCH  /api/workspaces/:workspace_slug/pages/:page_id/
DELETE /api/workspaces/:workspace_slug/pages/:page_id/

PATCH  /api/workspaces/:workspace_slug/pages/:page_id/description/
POST   /api/workspaces/:workspace_slug/pages/:page_id/archive/
DELETE /api/workspaces/:workspace_slug/pages/:page_id/archive/

POST   /api/workspaces/:workspace_slug/pages/:page_id/lock/
DELETE /api/workspaces/:workspace_slug/pages/:page_id/lock/

PATCH  /api/workspaces/:workspace_slug/pages/:page_id/access/

GET    /api/workspaces/:workspace_slug/pages/:page_id/versions/
GET    /api/workspaces/:workspace_slug/pages/:page_id/versions/:version_id/
POST   /api/workspaces/:workspace_slug/pages/:page_id/versions/:version_id/restore/

POST   /api/workspaces/:workspace_slug/pages/:page_id/duplicate/
POST   /api/workspaces/:workspace_slug/pages/:page_id/move/
```

Endpoint names should follow existing Plane conventions where they differ.

### 8.2 External API compatibility

Plane's documented external API already exposes workspace Wiki pages at:

```text
POST /api/v1/workspaces/{workspace_slug}/pages/
GET  /api/v1/workspaces/{workspace_slug}/pages/{page_id}/
```

The CE implementation should converge on the same resource naming/semantics to reduce integration differences between CE and Commercial.

Do not break existing project-page API:

```text
/api/v1/workspaces/{workspace_slug}/projects/{project_id}/pages/
```

### 8.3 List filters

Minimum filters:

- public;
- private;
- archived;
- favorite;
- parent;
- owner;
- search;
- collection when Collections ship.

Ordering must use an allowlist.

---

## 9. Realtime collaboration

### 9.1 Document type

Extend live types:

```ts
type TDocumentTypes = "project_page" | "workspace_page";
```

### 9.2 Workspace service

Add a workspace page live service using:

```text
/api/workspaces/{workspaceSlug}
```

as the REST base path.

Reuse `PageCoreService` for:

- fetch page;
- fetch/update binary description;
- metadata updates;
- mentions;
- asset URL handling.

### 9.3 Handler

`getPageService(documentType, context)` must dispatch:

- `project_page` -> ProjectPageService;
- `workspace_page` -> WorkspacePageService.

### 9.4 Authorization

A valid authenticated websocket is **not enough**.

The document-specific REST/API permission must verify page access before:

- loading initial Yjs state;
- persisting Yjs updates;
- updating title;
- resolving assets.

Unauthorized users must not receive document bytes.

### 9.5 Lock behavior

Locked Wiki pages must reject write persistence.

Read-only collaborative connections may remain possible if the UI supports them.

---

## 10. Web architecture

### 10.1 Routes

Preferred routes:

```text
/:workspaceSlug/wiki
/:workspaceSlug/wiki/:pageId
```

Use `apps/web/app/routes/extended.ts` where practical rather than hardcoding all routes into CE base route definitions.

### 10.2 Store type

Extend:

```ts
enum EPageStoreType {
  PROJECT = "PROJECT_PAGE",
  WORKSPACE = "WORKSPACE_PAGE",
}
```

### 10.3 Workspace page service/store

Add:

```text
WorkspacePageService
WorkspacePageVersionService
WorkspacePage extends BasePage
WorkspacePageStore
```

Responsibilities unique to Workspace Wiki:

- workspace URLs;
- workspace permission mapping;
- hierarchy;
- Wiki list sections;
- Collections;
- sharing.

Everything else should stay in shared Page code.

### 10.4 Navigation

Add Wiki as workspace navigation.

Target information architecture:

```text
Wiki
  Favorites
  Public
  Private
  Collections
  Archived
```

The exact visual layout should track current Commercial Wiki as closely as practical.

### 10.5 Page tree

Tree requirements:

- lazy or efficient loading for large workspaces;
- arbitrary nesting depth;
- expand/collapse;
- create child;
- drag/drop reorder;
- move to another parent;
- cycle prevention feedback;
- access-aware hiding;
- archived pages excluded from active tree;
- collection-aware rendering when Collections ship.

---

## 11. Editor parity

### 11.1 Reuse existing editor first

The first Wiki release should not fork the editor.

Use `@plane/editor` and existing Page editor props.

### 11.2 Existing extension hook

`useExtendedEditorProps` is the preferred place for Wiki/commercial-like Page editor enhancements where applicable.

### 11.3 Block roadmap

Target parity in this order:

1. existing text/headings/lists/quotes;
2. tables;
3. code blocks;
4. images/assets;
5. work-item embeds;
6. links/mentions;
7. toggles;
8. tabs;
9. Mermaid;
10. Page hierarchy/page-list embed;
11. URL video/media embed;
12. LaTeX;
13. Draw.io integration;
14. Office attachment integration.

Do not block core Wiki on advanced blocks.

---

## 12. Search

### 12.1 Core search

Minimum:

- page title;
- `description_stripped`;
- labels when available.

Every result must be permission-filtered before returning to the client.

### 12.2 No vector database requirement for core Wiki

Core Wiki search should not require embeddings or a vector service.

Postgres full-text/trigram search is sufficient for the initial implementation if the existing search infrastructure cannot already index workspace pages.

AI/natural-language retrieval is a separate enhancement.

---

## 13. Version history

Required:

- list versions;
- view version;
- restore version;
- actor/time metadata.

Parity enhancement:

- compare arbitrary page versions;
- visually show added/removed/changed content.

Version retrieval must be page/workspace scoped. A version ID alone is never sufficient authorization.

---

## 14. Comments

Commercial Wiki supports Page comments.

Target:

- page-level comment thread;
- replies if consistent with current product;
- edit/delete creator restrictions;
- comment reactions if reusable;
- comment permission distinct from edit permission;
- collection `COMMENT` role support;
- later inline/block comments if page-level comments ship first.

The spec intentionally separates **page comments** from **inline comments** so the initial implementation can deliver useful review collaboration without prematurely binding comment storage to editor node IDs.

---

## 15. Publishing

Parity target:

- publish a Wiki page externally;
- stable public link/token;
- revoke publication;
- optional external comments if implemented;
- assets render safely;
- no leakage of non-published private descendants;
- explicit behavior for nested export/publish.

Publishing must use a separate public permission path. It must never reuse workspace membership assumptions.

---

## 16. Templates

Target:

- save Page as template;
- template visibility at workspace scope;
- create Page from template;
- preserve supported editor content/structure;
- template management permissions.

Do not duplicate the document engine for templates; store template document content in a compatible format.

---

## 17. Export

### 17.1 Initial

Reuse existing page PDF/export UI/pipeline where possible.

### 17.2 Parity

Commercial behavior now includes exporting a Page with nested pages and packaging output as ZIP, including PDF/DOCX-related formats.

Requirements:

- explicit root page;
- descendants traversed safely;
- stable hierarchy order;
- permission check for every included page;
- predictable file naming;
- asset handling;
- export job limits to prevent resource exhaustion.

---

## 18. Labels

Commercial Wiki supports Page labels.

The current `Page` model already has labels.

Wiki implementation should expose:

- add/remove label;
- filter by label;
- label in search;
- permission-safe list.

Avoid a second Wiki label system.

---

## 19. Collections and ACL inheritance

Collections are a major commercial-parity feature and must be treated as an authorization feature, not only UI grouping.

### 19.1 Effective permissions

A private Collection applies its restrictions to pages inside it.

Subpages inherit from their parent.

Implementation must define precedence explicitly.

Recommended principle:

```text
effective capability = most restrictive mandatory ancestor boundary
                       + explicitly granted role within that boundary
```

A direct Page share must not accidentally bypass a private Collection if Commercial behavior treats Collection privacy as authoritative.

This rule must be confirmed against observed Commercial behavior before the Collection implementation is merged.

### 19.2 Atomic moves

Moving a page into/out of a private Collection can change access for an entire subtree.

The operation should:

1. validate requester permission;
2. calculate affected subtree;
3. validate target collection;
4. update association;
5. invalidate relevant cache/search entries;
6. emit activity/events;
7. commit atomically.

---

## 20. Activity, events, webhooks

Workspace Wiki mutations should integrate with Plane's existing activity/event mechanisms where possible.

Minimum event categories:

- page created;
- page updated;
- page moved;
- page archived/restored;
- page deleted;
- access changed;
- share changed;
- lock changed;
- comment created/updated/deleted;
- collection changed.

Webhook parity can follow after internal events are stable.

Avoid embedding sensitive page content into webhook payloads by default.

---

## 21. Performance

Expected large-workspace concerns:

- tree traversal;
- recursive hierarchy queries;
- search;
- permission filtering;
- version history;
- realtime sessions.

Candidate indexes to evaluate with `EXPLAIN` rather than add blindly:

```text
(workspace_id, is_global, archived_at)
(workspace_id, is_global, parent_id, sort_order)
(page_id, last_saved_at) for versions
(collection_id, sort_order)
(page_id, member_id) for shares
```

Use pagination for flat lists/search.

Do not load an entire large Wiki document tree if the UI only needs one branch.

---

## 22. Security requirements

These are release blockers.

### 22.1 BOLA / IDOR

Every entity lookup must be scoped by workspace and entity relation.

Test cross-workspace UUID reuse/guessing for:

- page;
- version;
- share;
- comment;
- collection;
- export;
- asset;
- websocket document.

### 22.2 Stored content

Continue using existing HTML sanitization and binary/JSON conversion paths.

No new editor block may introduce unsanitized HTML/script execution.

### 22.3 Assets

Asset retrieval must verify effective page access or use appropriately scoped signed URLs.

Private-page attachment URLs must not become permanent public URLs.

### 22.4 Recursive operations

Archive/delete/move/export must guard against cycles and resource exhaustion.

### 22.5 Search leakage

Unauthorized private pages must not leak through:

- result title;
- snippets;
- autocomplete;
- counts;
- filters;
- AI context.

### 22.6 Websocket authorization

Test:

- unauthenticated connection;
- workspace non-member;
- member without private-page access;
- read-only share trying to write;
- locked page write;
- access revoked during session.

---

## 23. Testing requirements

### Backend

- serializer tests;
- permission matrix tests;
- hierarchy invariant tests;
- archive/restore tests;
- move/reorder tests;
- version scoping tests;
- sharing tests;
- Collection inheritance tests;
- API contract tests;
- cross-workspace BOLA tests.

### Live

- workspace_page handler;
- load/store document;
- unauthorized load;
- unauthorized write;
- lock behavior;
- access revocation;
- title update authorization.

### Web

- store/service tests where infrastructure exists;
- tree behavior;
- filter tabs;
- drag/drop;
- permission-driven controls;
- route handling;
- private-page 404/not-authorized behavior;
- editor readonly state;
- version restore.

### Regression

Project Pages must retain:

- existing URLs;
- existing project scoping;
- existing realtime behavior;
- existing version API;
- existing permissions.

---

## 24. Backward compatibility and upstream strategy

### 24.1 Rules

- do not rename existing Page tables;
- do not weaken Project Page scoping;
- prefer additive models/URLs;
- prefer new workspace-specific adapters over branching generic code everywhere;
- keep changes near existing `extended.*` seams;
- avoid broad editor forks;
- keep shared changes small and covered by tests.

### 24.2 Upstream merge objective

A future upstream CE update should mostly conflict in:

- route registration;
- store registration;
- sidebar registration;
- live document handler;
- API URL registration.

Wiki business logic should live in isolated modules.

---

## 25. Definition of done: core Wiki

Core Wiki is production-ready when all are true:

- [ ] Wiki appears as workspace navigation.
- [ ] Workspace members can access `/:workspaceSlug/wiki`.
- [ ] Wiki page CRUD works independently of a Project.
- [ ] Wiki pages use `Page.is_global = true`.
- [ ] Project Pages continue to work unchanged.
- [ ] Public/private list filtering works.
- [ ] Nested page creation works.
- [ ] Reparent/reorder works.
- [ ] Self-parent and descendant-parent cycles are rejected server-side.
- [ ] Rich editor works.
- [ ] Yjs/Hocuspocus collaboration works for `workspace_page`.
- [ ] Unauthorized users cannot load document state.
- [ ] Page lock prevents writes.
- [ ] Version history and restore work.
- [ ] Favorites work.
- [ ] Archive/restore works recursively and safely.
- [ ] Title/content search works without private-page leakage.
- [ ] Existing export path works for Wiki pages.
- [ ] Backend/live/web regression tests pass.
- [ ] Cross-workspace BOLA tests pass.

---

## 26. Definition of done: commercial-parity Wiki

Commercial-parity target is reached when, in addition to core:

- [ ] Shared private pages with View/Comment/Edit ACL.
- [ ] Page comments.
- [ ] Collections.
- [ ] Private Collections with ACL inheritance.
- [ ] Default Collection.
- [ ] Collection/page drag/drop.
- [ ] Templates.
- [ ] External publishing.
- [ ] Version comparison.
- [ ] Labels exposed in Wiki UX.
- [ ] Favorites dedicated view.
- [ ] Nested hierarchy export.
- [ ] Tabs and toggles.
- [ ] Mermaid.
- [ ] Page hierarchy embeds.
- [ ] URL media embeds.
- [ ] Page/Collection analytics.
- [ ] Remaining advanced editor integrations evaluated individually.

AI, importers, and Office desktop integration are separate tracks because they depend on services/integrations beyond the Wiki core.

---

## 27. Public references used for parity research

Research baseline: 2026-09-22.

- Plane Wiki product page: https://plane.so/wiki
- Plane pricing / feature matrix: https://plane.so/pricing
- Workspace Wiki API — create page: https://developers.plane.so/api-reference/page/add-workspace-page
- Workspace Wiki API — retrieve page: https://developers.plane.so/api-reference/page/get-workspace-page
- Project Page API — create page: https://developers.plane.so/api-reference/page/add-project-page
- Collections introduction: https://plane.so/blog/introducing-collections-and-ai-native-documentation
- Collections changelog: https://plane.so/changelog/2026-04-15-wiki-collections-initiative-boards
- Page/version/label enhancements: https://plane.so/changelog/2026-07-31-skills-plane-ai-richer-pages-audit-logs
- Nested export/toggles/security fixes: https://plane.so/changelog/2026-08-14-collapsible-toggle-blocks-dashboard-intake-widgets
- Page tabs, page hierarchy links, analytics: https://plane.so/changelog/2026-08-31-shared-views-tabs-in-pages-and-more
- Release v3.2.0: https://plane.so/changelog/release-v3-2-0-workspace-governance-ai-memory-pii-scanning-and-more
- Plane App extension model: https://developers.plane.so/dev-tools/build-plane-app/overview
- Plane Marketplace overview: https://plane.so/marketplace

---

## 28. Open questions to validate during implementation

These should be resolved by observing current Commercial behavior or public docs before the affected parity PR:

1. Can one Wiki page belong to multiple Collections or exactly one?
2. Exact precedence between direct Page share and private Collection ACL.
3. Whether Workspace Admin/Owner may read a creator-private page without explicit share.
4. Whether page-level comments and inline/block comments share a storage model.
5. Whether public pages are editable by all Workspace Members by default or require a separate edit capability.
6. Exact semantics of external comments on published pages.
7. Whether moving a parent across Collections always moves all descendants.
8. Exact collection/default collection behavior for legacy/uncollected pages.
9. Exact version-diff granularity expected by current Commercial UI.

None of these questions block the core Wiki milestone; the architecture above intentionally keeps room for the parity features.


---

## 29. Instance-wide Company Wiki (fork extension)

This section is normative and supersedes workspace-only assumptions elsewhere in this document where instance-scoped Pages are concerned.

### 29.1 Product requirement

The deployment uses multiple workspaces, typically representing departments/teams. Some documents must be canonical for the entire company rather than copied into every workspace.

Examples:

- company handbook;
- security policies;
- IT usage guides;
- onboarding policy;
- leave/expense policy;
- organization-wide SOPs;
- shared engineering/security standards;
- emergency/contact procedures;
- company forms and references.

Add a separate **Company Wiki** surface with canonical routes:

```text
/company-wiki
/company-wiki/:pageId
```

The same Company Wiki is reachable from every workspace, but the URL must not contain a workspace slug. This prevents the same instance-level document from acquiring different canonical URLs depending on which workspace the user happened to enter from.

Recommended navigation:

```text
Company Wiki        <- instance-wide
Wiki                <- current workspace
Projects
...
```

A later navigation redesign may group both under a single Knowledge/Wiki entry, but the two scopes must remain visually distinguishable.

### 29.2 Scope semantics

Use the existing Page model with these invariants:

```text
PROJECT PAGE
  is_global = false
  workspace_id IS NOT NULL
  active ProjectPage relation required

WORKSPACE WIKI
  is_global = true
  workspace_id IS NOT NULL
  no ProjectPage relation required

INSTANCE / COMPANY WIKI
  is_global = true
  workspace_id IS NULL
  no ProjectPage relation
```

Recommended DB invariant:

```text
workspace_id IS NOT NULL OR is_global = true
```

In other words, a Project Page may never have a null workspace.

Do not create `WikiPage` or `InstanceWikiPage` content tables unless implementation evidence shows that nullable workspace breaks too many existing Page assumptions. The default design is one Page engine with three scopes.

### 29.3 Required schema changes

Current `Page.workspace` is non-null. Change it to nullable.

Audit every Page-adjacent model that currently assumes a workspace:

- `PageVersion.workspace` — make nullable for instance Page versions, or derive scope solely from `page`;
- `PageLog.workspace` — make nullable for instance Page activity, or derive from `page`;
- `PageLabel.workspace` — existing labels are workspace-owned, so **do not reuse workspace Labels for Company Wiki in Core V1**;
- `FileAsset.workspace` is already nullable, but Page asset routes currently assume workspace/project URL shapes and require a dedicated instance-Page asset route;
- favorites/recents/search must accept instance scope without inventing workspace membership.

Migration requirements:

- existing rows retain their current workspace IDs;
- existing Project Pages and Workspace Wiki semantics remain unchanged;
- no bulk rewrite of `is_global`;
- null workspace is accepted only through instance-Wiki APIs;
- add contract tests proving ordinary Page APIs cannot accidentally create a null-workspace Project/Workspace Page.

### 29.4 Read/write permission model

**Company-public means instance-authenticated, not Internet-public.**

Core V1:

| Actor | Read | Create/Edit | Lock/Archive/Delete | Manage editors |
| --- | --- | --- | --- | --- |
| Anonymous | No | No | No | No |
| Active normal instance user | Yes | No | No | No |
| Instance Admin | Yes | Yes | Yes | Yes |

Active instance user means an authenticated `User` with `is_active=True`. Bots/service identities should be excluded from default human-read semantics unless explicitly required.

A later delegated-authoring phase should add an explicit instance Wiki role such as:

```text
InstanceWikiMember
  instance
  user
  role = EDITOR | MANAGER
```

Suggested semantics:

- EDITOR: create/edit pages, create children, attach files;
- MANAGER: EDITOR + lock/archive/reorder/manage Company Wiki structure;
- InstanceAdmin: implicit MANAGER and can manage delegated roles.

Do not infer instance-wide edit permission from being Admin of any single workspace.

### 29.5 Instance hierarchy

Instance Page parent rules:

- parent must also have `workspace_id=NULL`;
- parent must have `is_global=True`;
- workspace Wiki cannot parent an instance Page;
- instance Page cannot parent a workspace/project Page;
- all cycle-prevention rules apply unchanged.

This ensures the hierarchy never crosses security scopes.

### 29.6 Instance API

Preferred internal API shape:

```text
GET/POST /api/instance/wiki/pages/
GET/PATCH/DELETE /api/instance/wiki/pages/:page_id/

GET/PATCH /api/instance/wiki/pages/:page_id/description/
POST/DELETE /api/instance/wiki/pages/:page_id/lock/
POST/DELETE /api/instance/wiki/pages/:page_id/archive/

GET /api/instance/wiki/pages/:page_id/versions/
GET /api/instance/wiki/pages/:page_id/versions/:version_id/
POST /api/instance/wiki/pages/:page_id/duplicate/
```

The exact prefix may be adjusted to repository conventions during implementation. Plane already exposes instance administration under `/api/instances/`; Company Wiki does not need to live in the license app merely because its scope is instance-wide.

Every lookup must enforce:

```text
page.workspace_id IS NULL
page.is_global = true
page.deleted_at IS NULL
```

No workspace slug or workspace membership check is involved.

### 29.7 External API

Instance Wiki is fork-specific and has no current Plane Commercial External API equivalent.

Do not pretend it is a commercial endpoint.

If exposed later, use a clearly separate contract, for example:

```text
/api/v1/instance/wiki/pages/
```

PAT authorization must distinguish:

- normal user read;
- delegated editor write;
- instance admin manage.

### 29.8 Realtime collaboration

Add a third live document type:

```ts
type TDocumentTypes =
  | "project_page"
  | "workspace_page"
  | "instance_page";
```

Add `InstancePageService` using the instance Wiki REST path.

Connection params:

```text
documentType = instance_page
workspaceSlug = null
projectId = null
```

Authorization requirements:

- user must be authenticated and active to load document state;
- writer must be InstanceAdmin/delegated editor;
- page lock rejects writes;
- access revocation/editor-role revocation rejects later writes;
- document bytes must never be returned to anonymous connections.

### 29.9 Assets

Current `FileAsset.workspace` is nullable, which is useful, but current Page-description asset URLs assume workspace/project paths.

Add explicit instance Wiki asset endpoints rather than fabricating a workspace:

```text
/api/assets/v2/instance/pages/:page_id/:asset_id/
```

Exact route can follow asset-service conventions.

Rules:

- asset must belong to requested Page;
- Page must be an instance Page;
- authenticated active user may read;
- only a user with Page edit capability may upload/delete/restore;
- signed/storage URLs must not make Company Wiki assets anonymously public.

### 29.10 Search

Company Wiki search is instance-wide.

Core behavior:

- title + stripped content;
- hierarchy-aware;
- same result regardless of current workspace;
- available from Company Wiki surface;
- optionally merged into global search later.

Search results must be tagged by scope so UI can distinguish:

```text
Company Wiki
Workspace Wiki
Project Page
```

No workspace filter should accidentally hide instance Pages.

### 29.11 Favorites and recents

Favorites/recents should be user-global for Company Wiki.

A user favoriting a Company Wiki page from Workspace A must see the same favorite when currently browsing Workspace B.

Do not store a fake workspace ID solely to support favorites.

### 29.12 Labels and Collections

Core Company Wiki does **not** require labels because current Plane Labels are workspace-scoped.

For parity/extensions later:

- introduce instance-level labels or generalize Label scope;
- allow Collections at instance scope;
- Collection scope must never mix instance and workspace Pages;
- Company Wiki Collections remain readable by all active users by default;
- optional private instance Collections can be added only if there is a real company use case.

Do not block Company Wiki V1 on generalized labels/Collections.

### 29.13 UI behavior

Company Wiki should reuse the same Page editor and navigation components as Workspace Wiki.

Distinct UI cues are required:

- header/breadcrumb says **Company Wiki**;
- workspace switcher does not change the loaded Company Wiki Page;
- copied links use `/company-wiki/:pageId`;
- create-page controls are hidden for users without instance Wiki write capability;
- read-only users still get search, outline, version browsing, copy link, export where permitted.

### 29.14 Company Wiki Core definition of done

- [ ] Canonical `/company-wiki` route exists outside workspace scope.
- [ ] Link is reachable from every workspace.
- [ ] All active authenticated users can read Company Wiki.
- [ ] Anonymous access is denied.
- [ ] InstanceAdmin can create/edit/lock/archive/delete.
- [ ] Instance pages store `workspace_id=NULL`, `is_global=True`.
- [ ] Workspace/Project APIs cannot create or mutate instance Pages accidentally.
- [ ] Nested instance Pages work and cannot cross into workspace/project hierarchy.
- [ ] Realtime editing supports `instance_page`.
- [ ] Instance Page assets use an explicit non-workspace route.
- [ ] Version history works with null workspace.
- [ ] Search/favorites/recents work independently of current workspace.
- [ ] Existing Project Pages and Workspace Wiki remain regression-safe.
- [ ] Security tests cover cross-scope UUID attempts in both directions.

### 29.15 Core architecture consequence

Because Instance Wiki is now a required feature, the first implementation PR must establish Page scope compatibility **before** Workspace Wiki APIs are treated as final.

Recommended implementation order becomes:

```text
WIKI-00 Page scope foundation
   ├─ nullable Page.workspace for instance scope
   ├─ PageVersion/PageLog compatibility
   ├─ scope helpers/invariants
   └─ asset scope design
        ↓
WIKI-01 Workspace + Instance Wiki backend
        ↓
WIKI-02 workspace_page + instance_page realtime
        ↓
WIKI-03 Workspace Wiki + Company Wiki web surfaces
        ↓
WIKI-04 hierarchy/search/export/security hardening
```

This avoids building a workspace-only abstraction and immediately refactoring it when Company Wiki is added.


---

## 30. UI/UX conformity with Plane

This section is normative. Wiki must look and behave like a native Plane feature. Commercial feature parity does **not** justify introducing a parallel visual language.

### 30.1 UI source of truth

For implementation based on the approved preview baseline, the visual/component source of truth is the existing Plane UI on:

```text
r2d-ai/plane:preview
SHA 02c19e1341d93141e8ad7b3278298adce208bafc
```

When commercial screenshots or public product pages differ from the CE/preview shell, follow this precedence:

```text
1. Current local Plane shell/layout/design system
2. Current existing Page UX/components
3. Commercial Wiki information architecture and behavior
4. Commercial pixels/styling
```

The goal is **Commercial Wiki behavior inside current Plane UI**, not a visually copied island that looks like another Plane version.

### 30.2 Reuse existing Page surfaces

Workspace Wiki and Company Wiki must reuse the same Page primitives currently used by Project Pages wherever the interaction is equivalent.

Required reuse targets include:

- `PageRoot`;
- `PageEditorBody`;
- `PageEditorHeaderRoot`;
- `PageEditorToolbarRoot`;
- `PageNavigationPaneRoot`;
- `PageVersionsOverlay`;
- `PagesVersionEditor`;
- `PageHeaderActions`;
- `PageSyncingBadge`;
- `PageAccessIcon`;
- `PagesListRoot`;
- `PagesListView`;
- `PageSearchInput`;
- `PageOrderByDropdown`;
- `PageFiltersSelection`;
- `PageAppliedFiltersList`;
- existing Page loaders and empty-state components.

Do not fork these components solely to change labels, URLs, permission sources, or page scope. Add parameters/adapters instead.

New Wiki-specific components should be limited mainly to:

- nested Wiki tree;
- Company-vs-Workspace scope indicator;
- sharing UI;
- Collections;
- collection/page hierarchy controls;
- commercial-parity blocks that do not already exist.

### 30.3 Header and breadcrumb rules

List screens should follow the existing Project Pages header pattern:

- use Plane `Header`;
- use `Header.LeftItem` and `Header.RightItem`;
- use existing `Breadcrumbs`;
- use `BreadcrumbLink`;
- primary create action belongs on the right;
- use the current Page/Wiki icon set from Plane's existing icon packages.

Workspace Wiki breadcrumb target:

```text
Workspace / Wiki
Workspace / Wiki / <Page>
```

Company Wiki breadcrumb target:

```text
Company Wiki
Company Wiki / <Page>
```

Do not place a fake workspace in Company Wiki breadcrumbs.

Detail screens must keep:

- sync indicator in the header;
- Page actions in the same location/order conventions as existing Pages;
- Page access icon where access state is meaningful;
- title editing in the existing Page editor header, not duplicated into app header.

### 30.4 List and empty-state behavior

Wiki list screens should visually derive from existing Pages list screens.

Requirements:

- use the existing page list shell, loader, search, filters and order controls;
- use current `EmptyStateDetailed` / existing Wiki empty-state assets;
- reuse existing assets under `apps/web/app/assets/empty-state/wiki/`;
- support light and dark themes with the matching provided asset;
- do not create custom card systems for basic page lists if Plane's existing list row pattern is sufficient.

The nested tree may introduce a dedicated row component, but it must use the same:

- typography scale;
- hover state;
- selected state;
- icon sizing;
- padding rhythm;
- menu/action affordances;
- semantic colors.

### 30.5 Editor layout

Do not create a Wiki-specific editor shell.

The current Page editor layout is authoritative:

- document body remains centered/width-controlled by existing Page width logic;
- full-width option uses existing `view_props.full_width`;
- content horizontal spacing uses existing `px-page-x` behavior;
- outline/summary follows existing Page content browser;
- right navigation pane uses existing Page navigation pane;
- version history opens through the same pane/overlay mechanisms;
- readonly state must be implemented through the shared editor configuration.

Company Wiki normal users should see the same editor surface in readonly mode rather than a separate document renderer.

### 30.6 Navigation pane

Continue using `PageNavigationPaneRoot`.

Current Plane preview already uses Propel Tabs/Tooltip in this pane. Wiki extensions such as Comments or additional commercial panels should register via the Page pane extension seam when possible.

Do not add a second right sidebar.

Recommended panels over time:

```text
Outline
Assets
Info
Versions
Comments        # parity phase
```

Collection management belongs outside the document navigation pane unless current Commercial behavior clearly places it there.

### 30.7 Design-system dependency policy

Preview is actively migrating to `@makeplane/propel`.

Rules for new Wiki code:

1. If an equivalent component already exists in `@makeplane/propel` and adjacent preview code uses it, use it.
2. If current Page code still uses a Plane wrapper such as `@plane/ui` or `@plane/propel`, reuse that existing primitive rather than replacing it only for Wiki.
3. Do not perform broad UI-library migrations as part of Wiki PRs.
4. Do not introduce a fourth component library.
5. Icons should prefer the same Propel icon source used by adjacent current Plane components.

Examples from current preview Page UI:

- icons: `@makeplane/propel/icons`;
- navigation pane tabs/tooltips: `@makeplane/propel/components/*`;
- some Page buttons/toasts remain through `@plane/propel/*`;
- `Header` and `Breadcrumbs` currently remain in `@plane/ui`.

Wiki should follow the adjacent component being extended, not an arbitrary global migration rule.

### 30.8 Styling rules

Use Plane semantic tokens/classes.

Preferred existing patterns include:

```text
bg-surface-1
bg-surface-2
bg-layer-1
border-subtle
text-primary
text-secondary
text-tertiary
text-placeholder
rounded-sm
text-13
text-16
px-page-x
```

Requirements:

- no hard-coded hex/RGB colors for application UI;
- no custom shadow/radius system;
- no one-off spacing scale when existing tokens/utilities fit;
- no fixed light-theme colors;
- loading, hover, disabled, selected and error states must work in both themes.

### 30.9 Typography and density

Match existing Plane density.

Default UI text should follow adjacent Plane components, commonly:

- 13px class for controls/list/sidebar text;
- 16px class for small headings where existing Plane screens use it;
- existing editor typography for document content.

Do not make Wiki resemble a marketing/documentation website with oversized headings, wide cards, or excessive whitespace.

### 30.10 Buttons, menus and dialogs

Reuse existing Plane button/menu/modal patterns.

Rules:

- one primary action per header where possible;
- destructive actions use current danger/destructive conventions;
- context actions belong in the existing Page action menu pattern;
- creation dialogs should follow current Page modal/form density;
- permission-disabled actions should be hidden or disabled according to existing Plane conventions, not custom tooltips/messages.

### 30.11 Workspace sidebar

Workspace Wiki should appear through the existing sidebar navigation model and `SidebarItemBase`.

Company Wiki must be reachable from every workspace but remain instance-scoped.

UI requirements:

- use the same Sidebar navigation row height, icon size and `text-13` label style;
- do not add a separate oversized Knowledge navigation panel to the main sidebar;
- active state must use the standard `SidebarNavItem`;
- current workspace Wiki and Company Wiki must have labels/icons clear enough to prevent scope confusion.

Recommended labels:

```text
Company Wiki
Wiki
```

Avoid ambiguous duplicate labels such as two entries both named `Wiki`.

### 30.12 Responsive/mobile behavior

Wiki must inherit Plane's existing responsive shell behavior.

Core requirements:

- no horizontal overflow introduced by tree/list/header controls;
- action groups collapse using existing Plane responsive patterns;
- navigation pane behavior must match existing Page behavior;
- editor remains usable at tablet/mobile widths supported by the web app;
- tree nesting must not consume unlimited horizontal space on narrow screens.

Do not invent a separate mobile design in Wiki PRs. Native/mobile support is a separate project, but Wiki web UI must not block later reuse.

### 30.13 Loading, error and permission states

Use current Plane states:

- `PageLoader` for list/page shell where applicable;
- `PageContentLoader` for editor loading;
- existing LogoSpinner patterns where current Page route uses them;
- existing not-found/unauthorized screen components;
- existing toast infrastructure for mutations.

Do not render raw API error text in the document surface.

Unauthorized private pages should follow security semantics first; if policy is “not found”, UI must not reveal that a hidden page exists.

### 30.14 Theme compatibility

Every Wiki screen must be manually checked in:

- light theme;
- dark theme.

No feature is accepted if only the editor content works in dark mode while tree, collection, dialog, or empty-state surfaces break.

Use existing dark/light Wiki empty-state artwork rather than recoloring assets in CSS.

### 30.15 UI review matrix

Before each Wiki UI PR is accepted, compare it side by side with the nearest native Plane surface.

| Wiki surface | Native Plane reference |
| --- | --- |
| Workspace Wiki list | Project Pages list |
| Wiki page detail | Project Page detail |
| Header/breadcrumb | Project Page list/detail headers |
| Search/filter/order | Existing Page list controls |
| Document editor | Existing Project Page editor |
| Navigation pane | Existing Page navigation pane |
| Empty state | Existing Page/Wiki empty states |
| Sidebar item | Existing Projects/Views sidebar items |
| Share dialog | Closest current Plane member/access dialog |
| Collection list/tree | Existing Plane list/sidebar/tree density and Propel controls |

Any visual deviation must be justified by a Wiki-specific interaction requirement.

### 30.16 UI acceptance criteria

A Wiki UI PR fails review if it:

- duplicates an existing Plane component without a technical reason;
- introduces hard-coded design tokens;
- has a standalone visual language;
- uses different Page editor behavior for Workspace and Company Wiki without a scope-specific reason;
- creates inconsistent header/sidebar/breadcrumb patterns;
- fails light/dark theme;
- ignores existing loading/error/empty states;
- introduces avoidable new dependencies.

Recommended review captures:

```text
1440px light
1440px dark
1024px light
768px / narrow viewport
```

For the same PR, capture the nearest native Plane reference screen at the same viewport and theme.

---

## 31. Baseline review: preview vs stable v1.4.2

### 31.1 Repository facts

As of 2026-09-22:

```text
r2d-ai/plane:preview
  02c19e1341d93141e8ad7b3278298adce208bafc

makeplane/plane:preview
  02c19e1341d93141e8ad7b3278298adce208bafc

makeplane/plane:master
  5f7d92784c403f76284f0f16718f320221dc7fec
  release commit: v1.4.2
```

Therefore the fork's `preview` is currently an **exact copy of upstream preview**, not a locally diverged development branch.

Upstream calls its release branch `master`, not `main`.

Git topology reports:

```text
preview ahead of master: 63 commits
preview behind master: 5 commits
```

The five master-only commits are release commits for v1.3.0, v1.3.1, v1.4.0, v1.4.1 and v1.4.2. This topology is consistent with upstream maintaining a moving preview line and separate release commits; “behind by 5” must not be interpreted as five ordinary fixes missing from preview.

### 31.2 Relevant preview changes

Preview after v1.4.2 includes several changes beneficial to Wiki development:

#### UI/design system

- migration toward `@makeplane/propel` 0.3.0;
- migration of icons and multiple primitives to Propel;
- React upgraded from 18.3.1 to 19.2.8;
- React Router upgraded from v7 to v8;
- Page editor shell updated to use newer Propel Banner and icon primitives;
- root route/app shell structure updated.

#### Editor/tooling

- editor package folder structure flattened/refactored;
- Node minimum raised from 22.18 to 22.22;
- pnpm raised from 11.3 to 11.10.

#### Security/hardening directly relevant to this fork

Preview contains post-v1.4.2 fixes including:

- authentication rate limiting;
- webhook HMAC secret no longer leaked on reads;
- Page `order_by` sanitized through an allowlist;
- Spaces board object project scoping;
- SubIssue cross-project scoping;
- sanitize-html dependency update;
- nightly Trivy/dependency security fixes;
- draft-to-issue owner scoping.

The Page order-by fix is directly relevant to new Wiki list endpoints and should not be discarded.

#### Deployment

Preview changes web/admin static serving from nginx to Caddy and updates several Dockerfiles.

However, comparison of the root and community CLI compose files shows no broad service-topology rewrite; the visible compose-level production change is primarily the MinIO image moving from Docker Hub to a pinned Quay release. Web still serves through its existing container contract while the internal static server changes.

### 31.3 Core Wiki seam comparison

Important Wiki foundations are identical between v1.4.2 master and current preview:

- `Page` model;
- `BasePage` frontend store;
- `ProjectPageStore`;
- `usePageStore`;
- live `PageService` extension seam;
- live Page service handler;
- workspace navigation constants;
- Page list root.

Changed but compatible areas include:

- Page API view: preview adds safe `order_by` handling;
- Page editor root/header: minor design-system migration;
- app router shell: React Router v8-compatible shell change;
- package/editor dependencies and structure.

This means the proposed Wiki architecture does not depend on preview-only experimental data models.

### 31.4 Baseline decision

**Use preview as the implementation baseline.**

Reasons:

1. fork preview exactly matches upstream preview;
2. no fork-specific divergence must be reconciled;
3. Wiki is UI-heavy and preview already represents the UI/design-system direction after v1.4.2;
4. building Wiki on v1.4.2 would intentionally target React 18 / Router 7 / older component usage and then require immediate migration;
5. preview contains security fixes useful to Wiki;
6. the key Page/store/live extension seams remain stable.

### 31.5 Pin, do not chase preview

Implementation branches must be created from the reviewed SHA:

```text
02c19e1341d93141e8ad7b3278298adce208bafc
```

Do not continuously rebase onto whatever `preview` becomes during a multi-PR Wiki implementation.

Instead:

1. branch the Wiki stack from the pinned baseline;
2. finish/test each dependent Wiki PR;
3. periodically evaluate upstream preview in a dedicated sync PR;
4. rebase/cherry-pick only after CI and UI regression checks.

This prevents an upstream design-system migration from changing underneath coding agents mid-feature.

### 31.6 Stable fallback

Fallback to `makeplane/plane:master` / v1.4.2 only if the pinned preview baseline fails the project's actual self-host deployment gate.

Fallback triggers include:

- preview images cannot build reproducibly;
- current deployment/reverse-proxy assumptions are incompatible with Caddy changes;
- required production integration fails smoke tests;
- React 19/Router 8 introduces a blocker in a required existing feature.

If fallback is triggered:

- establish a new fork `main`/stable branch from upstream master v1.4.2;
- update this spec baseline;
- selectively backport security fixes relevant to Wiki, especially Page ordering/scoping fixes;
- implement Wiki against stable UI primitives;
- do not mix preview-only Propel migration into Wiki PRs.

### 31.7 Baseline validation gate before WIKI-00

Before feature implementation begins on preview, run at least:

```text
pnpm check
pnpm build
backend contract/unit test stack
build self-host images used by current deployment
start the deployment stack
authenticate
open workspace/project/page
create/edit a Project Page
verify live collaboration
upload/render a Page asset
verify reverse-proxy routes
```

This gate validates the baseline itself, not Wiki code.

Record the result in the first implementation PR so later Wiki regressions are not confused with pre-existing preview issues.
