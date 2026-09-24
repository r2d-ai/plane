# Wiki Home, Default Collection, and Legacy Bootstrap Design

**Status:** Approved design for implementation

**Date:** 2026-09-24

**Repository:** `r2d-ai/plane`

**Related design:** [Unified Wiki App Design](./2026-09-23-unified-wiki-app-design.md)

## 1. Decision

Wiki Home is a **system dashboard**, not a `Page`.

Every active Wiki workspace has a default knowledge starting point:

1. a public default Collection named **General** for fresh/bootstrap scopes; and
2. one editable Welcome Wiki page in that Collection.

The same behavior applies to the designated Company/Instance Wiki workspace and
ordinary workspaces. The Company/Instance Wiki remains an ordinary real
workspace selected by `COMPANY_WIKI_WORKSPACE_SLUG`.

This design intentionally does **not** add:

- `entry_page_id`;
- a special Home/Entry Page model;
- a second page type;
- "set as home" semantics;
- Home-page delete/move protection;
- a new instance-level Wiki table.

The existing `Page`, `PageCollection`, and `PageCollectionPage` models are
sufficient.

## 2. Why

The commercial Wiki interaction model separates two concerns:

- **Home** resumes the user's work through greeting, recents, and stickies.
- **Collections/Pages** hold durable knowledge.

The current CE Home duplicates navigation data in the content pane
(Collections/Favorites) and still looks empty when the workspace contains
little content. Making Home a real editable Page would create a second
navigation concept, special lifecycle rules, and migration complexity without
improving the commercial-parity UX.

The simplest durable model is therefore:

```text
Wiki scope
├── Home                         system dashboard; never a Page
├── Collections
│   └── General                  default Collection
│       ├── Welcome to ...       normal editable Wiki Page
│       └── existing public docs
├── Shared
├── Private
└── Archived
```

## 3. Home UX contract

The canonical scope route remains:

```text
/wiki/:workspaceSlug
```

It renders `WikiHome`. It does not redirect to or resolve a page id.

### 3.1 Member view

For users who are active members of the selected workspace, Home contains:

1. the existing Plane user greeting;
2. **Recents**, filtered to Wiki pages only (`workspace_page`);
3. **Your stickies**, using the existing workspace stickies widget.

Target composition:

```text
               Good evening, Huy Doan
               🌙 Thursday, Sep 24 18:30

Recents
────────────────────────────────────────
📄 Welcome to Company's Wiki      1m ago

Your stickies                         + Add sticky
────────────────────────────────────────
[existing Plane sticky cards / empty state]
```

The implementation should reuse existing Plane primitives where possible:

- `UserGreetingsView`;
- Recent Page row/empty-state components;
- `StickiesWidget`.

Do not blindly use the generic `page` recent filter if that also includes
Project Pages. Wiki Home must request/filter `workspace_page` so Work/Project
page activity cannot appear inside Wiki.

### 3.2 Open-read non-member view

The designated Company/Instance Wiki may be readable by users who are not
members of that workspace.

For `scope.is_member == false`:

- do not call member-only Stickies APIs;
- do not call member-only workspace-recents APIs;
- render the greeting;
- render a compact **Recently updated** list derived from already-authorized
  Wiki navigation metadata for that scope, sorted by `updated_at DESC`;
- never reveal pages excluded by effective Wiki permissions.

This keeps Company Wiki Home useful without weakening workspace API
authorization.

### 3.3 Home must not duplicate the sidebar

Remove the current Home-body sections for:

- Favorites;
- Collection cards;
- the full page hierarchy;
- the current "Browse pages and collections in this workspace" hero;
- Home-level Templates/New page/Archived buttons when equivalent controls are
  already present in the Wiki shell/sidebar.

Favorites, Collections, Shared, Private, and Archived remain navigation
surfaces. Home is for resuming work.

### 3.4 Empty state

An empty Recents list and an empty Stickies list use Plane's existing empty
states. The screen should still look complete before the user has viewed any
Wiki page.

Do not show a large "No pages or collections yet" empty state on Home.

## 4. Sidebar contract

Home is a fixed navigation destination, never a tree parent.

For the default/Company Wiki scope:

```text
New page

⌂ Home

Collections
  ▾ General
      Welcome to Company's Wiki
      Company handbook
      Security policy

Shared
Private
Archived

WORKSPACES
  ▸ R&D
  ▸ Marketing
```

For an expanded ordinary workspace, clicking the workspace label opens that
workspace's Home dashboard; its expandable children are Collections/pages, not
children of a pseudo Home page.

Rules:

- Home never owns child pages.
- Collection hierarchy is rendered separately from Home.
- A page in a Collection is not rendered a second time as an uncollected root
  page.
- Private/shared pages remain in their existing personal/access sections and
  are not force-moved into public General during bootstrap.

## 5. Default Collection invariant

For a freshly bootstrapped workspace:

```text
PageCollection
  workspace   = workspace
  name        = "General"
  access      = PUBLIC (0)
  sort_order  = 0
  is_default  = true
  created_by  = workspace.owner
  updated_by  = workspace.owner
```

The existing database constraint remains authoritative: there may be at most
one active default Collection per workspace.

Runtime code must identify the default Collection by `is_default`, not by
the string `"General"`.

### 5.1 Existing custom Collections

Migration must be non-destructive:

- if an active default Collection already exists, preserve it;
- do not rename an existing user Collection;
- do not change an existing Collection's public/private access;
- if there is no default but an active Collection named `General`
  case-insensitively exists, promote that Collection to default;
- otherwise create the public `General` Collection.

This means `General` is guaranteed for legacy workspaces that predate
Collections, while already-customized Wiki workspaces are not rewritten.

## 6. Default Welcome page

Fresh workspaces receive one normal Workspace Wiki page.

Company/Instance Wiki title:

```text
Welcome to Company's Wiki
```

Ordinary workspace title:

```text
Welcome to <Workspace Name> Wiki
```

Required fields:

```text
workspace       = target workspace
owned_by        = workspace.owner
access          = PUBLIC (0)
is_global       = true
parent          = NULL
archived_at     = NULL
external_source = "wiki_bootstrap"
external_id     = "welcome-v1"
created_by      = workspace.owner
updated_by      = workspace.owner
```

The page is attached to the selected bootstrap/default Collection through
`PageCollectionPage`.

The Welcome page is deliberately a normal page:

- users may rename it;
- users may edit it;
- users may archive/delete it;
- it has normal history/comments/sharing/locking behavior;
- deleting it does not affect Wiki Home.

The bootstrap marker exists only for idempotency. UI logic must not treat the
page specially after creation.

### 6.1 Starter body

P0 must not hand-build Yjs/`description_binary` data inside a Django data
migration.

The migration may create the page with a valid empty editor document using the
same safe field defaults as a newly-created Page. On first open, the existing
editor/live pipeline initializes the document normally.

A richer commercial-style starter body can be applied through the normal Page
creation/template pipeline after P0, but it is not allowed to block or
complicate the legacy migration.

## 7. Legacy workspace migration

WikiCE is being added to an installation where workspaces already exist.
Therefore bootstrap is not only a "new workspace" behavior; it requires a
one-time data migration.

### 7.1 Scope

The migration runs for **every active workspace**:

```text
Workspace.deleted_at IS NULL
```

This includes the workspace designated by
`COMPANY_WIKI_WORKSPACE_SLUG`.

It does not require the workspace to already contain a Wiki page.

### 7.2 Migration file

Implement a data migration after the current Wiki schema migrations:

```text
apps/api/plane/db/migrations/0130_wiki_bootstrap_defaults.py
dependency: 0129_wikievent
```

No schema change is required.

The migration should use historical models via `apps.get_model()`; it must not
import runtime model classes or runtime service helpers.

Set:

```python
atomic = False
```

and process each workspace in its own `transaction.atomic()` block so a large
installation does not hold one transaction/lock for the whole deployment.

Use `.iterator(chunk_size=200)` or an equivalent bounded iteration.

### 7.3 Per-workspace migration algorithm

For each active workspace:

```text
BEGIN

1. Lock/re-read the workspace row.

2. Resolve bootstrap Collection:
   a. active is_default Collection exists
        -> preserve and use it;
   b. else active Collection name ~= "General"
        -> mark it is_default=true and use it;
   c. else
        -> create public "General", sort_order=0, is_default=true.

3. Resolve legacy Welcome page:
   a. active Wiki page with:
        external_source="wiki_bootstrap"
        external_id="welcome-v1"
        -> reuse it;
   b. else inspect active, PUBLIC, root, Wiki pages that are not already
      assigned to a Collection. If exactly one page title matches the legacy
      bootstrap shape:
        ^Welcome to .+Wiki$
      -> reuse it and stamp the bootstrap markers;
   c. else
        -> create the appropriate Welcome page owned by workspace.owner.

4. Ensure the resolved Welcome page has one active PageCollectionPage relation
   to the bootstrap Collection.
   - If it already belongs to another Collection, preserve the user's
     existing Collection and do not move it.
   - Never create two active Collection relations for one page.

5. If and only if step 2 created a new General Collection because the
   workspace had no active default Collection:
   migrate legacy uncollected PUBLIC root Wiki pages into General:
     page.is_global=true
     page.access=PUBLIC
     page.parent IS NULL
     page.archived_at IS NULL
     page.deleted_at IS NULL
     no active PageCollectionPage relation

   Create one PageCollectionPage relation per qualifying root.
   Descendants inherit the root Collection boundary; do not add redundant
   Collection relations to every descendant.

6. Do not move PRIVATE pages.
7. Do not modify PageShare rows.
8. Do not unarchive archived pages.
9. Do not touch Project Pages (is_global=false).

COMMIT
```

### 7.4 Why only public root pages are backfilled

Legacy WikiCE allowed Wiki pages before Collections existed. Leaving those
public pages as loose roots makes the new sidebar inconsistent and leaves
General empty.

Moving only uncollected public **root** pages is safe because:

- it gives legacy public documentation a predictable Collection;
- it does not relax private-page access;
- it does not disturb an existing user Collection;
- descendants retain their hierarchy and inherit the Collection from the root;
- it avoids duplicate `PageCollectionPage` rows.

### 7.5 Idempotency

The forward migration and runtime bootstrap helper must be safe to execute
multiple times.

After one successful pass, a second pass must create:

- 0 Collections;
- 0 Welcome pages;
- 0 duplicate Collection-page relations.

The existing unique constraints remain the final database guard.

### 7.6 Reverse migration

Use `migrations.RunPython.noop` for reverse.

Do **not** delete General/Welcome data automatically on rollback. By the time a
rollback happens users may already have renamed/edited pages or added content
to the Collection. Deleting seeded records would be destructive.

## 8. New workspace bootstrap

Legacy migration solves existing installations. New workspaces must satisfy the
same invariant.

Add an idempotent runtime helper, conceptually:

```python
ensure_wiki_defaults(workspace)
```

It should:

- create/promote the default Collection using the same rules;
- create the marked Welcome page if absent;
- attach it to the Collection;
- run transactionally;
- be safe under retries.

Call it from the explicit successful Workspace creation flow after the
workspace and owner are available.

Do not use an implicit Django `post_save` signal unless the existing Plane
workspace lifecycle already standardizes on such a signal. An explicit call is
easier to reason about and test.

A small repair management command may reuse the runtime helper:

```text
python manage.py ensure_wiki_defaults [--workspace <slug>] [--dry-run]
```

The command is recommended for operations but is not required for initial P0
UI completion.

## 9. Authorization and security

Bootstrap must never weaken existing Wiki authorization.

Hard requirements:

- only `is_global=true` Page rows are considered;
- Project Pages are untouched;
- workspace ids on Page, Collection, and Collection-page relation must match;
- private pages are never moved into public General by migration;
- an existing private Collection is never silently converted to public;
- Company Wiki open-read continues to be enforced by existing effective
  permission code, not by Collection bootstrap;
- non-member Home must not call member-only APIs that can leak metadata or
  generate noisy 403s.

The migration is a data-layout normalization, not an ACL migration.

## 10. Implementation delta

Expected code surface is intentionally small.

### Web

Primary files:

```text
apps/web/core/components/wiki/home.tsx
apps/web/core/components/wiki/home-model.ts
apps/web/core/components/wiki/sidebar/*
apps/web/core/components/home/user-greetings.tsx       reuse
apps/web/core/components/home/widgets/recents/*        reuse/extend
apps/web/core/components/stickies/widget.tsx           reuse
```

Expected behavior:

- replace the current browse-style Home body with greeting + Wiki recents +
  stickies;
- add non-member fallback;
- make Home a leaf/system route in sidebar semantics;
- keep Collections/page trees as navigation data.

### API / data

Primary additions:

```text
apps/api/plane/db/migrations/0130_wiki_bootstrap_defaults.py
apps/api/plane/utils/wiki_bootstrap.py                  or equivalent helper
workspace creation flow                                explicit helper call
```

No new database table or column is expected.

## 11. Tests

### 11.1 Migration tests

Cover at least:

1. old workspace, no Wiki data -> creates General + Welcome;
2. old workspace with public root Wiki pages -> moves roots into newly-created
   General and preserves nesting;
3. private Wiki pages -> remain outside public General;
4. archived pages -> remain archived and unassigned by bootstrap;
5. Project Pages -> untouched;
6. existing General, no default -> promoted, not duplicated;
7. existing custom default Collection -> preserved;
8. existing marked Welcome -> reused;
9. exactly one legacy `Welcome to ... Wiki` page -> reused and marked;
10. existing page already assigned to another Collection -> never moved;
11. running migration logic twice -> no duplicates;
12. designated Company Wiki workspace follows the same rules.

### 11.2 Home component tests

Cover:

- member sees greeting, Wiki-only Recents, and stickies;
- Project Page recents do not appear;
- member with no recents gets the Plane empty state;
- non-member open-read user does not trigger stickies/member recents;
- non-member sees only authorized recently-updated Wiki pages;
- Home does not render Favorites/Collection cards/page tree in its body.

### 11.3 Sidebar tests

Cover:

- Home is a leaf navigation destination;
- General appears under Collections;
- a Collection page is not duplicated as an uncollected page;
- private/shared/archive sections preserve existing behavior.

## 12. Acceptance criteria

The change is complete when:

- `/wiki/:workspaceSlug` visually follows the commercial Home interaction
  model without requiring a special Home Page entity;
- every active pre-WikiCE workspace has a usable default Collection and Welcome
  page after migration;
- public legacy root Wiki pages are normalized into newly-created General
  Collections without changing private/shared data;
- newly-created workspaces receive the same defaults;
- re-running bootstrap creates no duplicate data;
- the designated Company/Instance Wiki receives the same migration;
- no existing custom Collection is renamed, deleted, or made public;
- no Project Page is modified;
- Home remains useful to Company Wiki open-read non-members without calling
  member-only APIs;
- no new Wiki schema/model is introduced solely for Home.
