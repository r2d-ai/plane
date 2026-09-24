# Unified Wiki App Design

**Status:** Approved design; implementation plan at `docs/superpowers/plans/2026-09-23-unified-wiki-app.md`

**Date:** 2026-09-23

**Repository:** `r2d-ai/plane`

## 1. Summary

Plane CE will expose Wiki as a first-class app-level surface beside Work. All
instance and workspace Wiki content will live in one persistent Wiki shell,
with a navigation sidebar organized by workspace. Selecting Wiki opens the
configured default workspace, which is presented as **Instance Wiki**.

The default workspace remains an ordinary real workspace identified by
`COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG`. There is no instance-level Page
model, nullable workspace, or separate realtime document type.

The canonical route family is:

```text
/wiki/:workspaceSlug
/wiki/:workspaceSlug/:pageId
```

For example:

```text
/wiki/home
/wiki/home/8b75...
/wiki/mkt
/wiki/mkt/921a...
```

`/wiki` redirects to the configured default workspace, such as `/wiki/home`.

## 2. Goals

- Provide one Wiki entry point instead of separate Workspace Wiki and Company
  Wiki navigation items.
- Match the commercial Wiki interaction model: persistent Wiki navigation on
  the left and the selected Home or document in the main content area.
- Open the configured default workspace whenever the user enters Wiki.
- Group accessible Wiki content by workspace without exposing workspaces,
  collections, or pages outside the user's effective permissions.
- Reuse the existing Page model, editor, comments, version history, realtime
  document type, assets, collections, favorites, and sharing capabilities.
- Make the existing top-navigation search the only search entry point and make
  it return Wiki pages across authorized scopes.
- Preserve existing bookmarks through redirects.
- Keep the layout responsive rather than hardcoding the reference viewport.

## 3. Non-goals

- A Plane AI conversational sidecar is not part of this change. The Wiki shell
  will keep an extension boundary for a later AI project.
- This change does not create an `InstancePage`, a nullable `Page.workspace`,
  an instance asset route, or an `instance_page` realtime document type.
- Project Pages remain part of Work and are not moved into the Wiki app.
- The implementation will not load every page and collection for every
  workspace on initial render.
- This change will not imitate the commercial screenshot with fixed pixel
  dimensions or placeholder data.

## 4. App-level navigation

The outer app rail will expose two primary surfaces:

1. **Work** opens the existing workspace/product experience. It returns to the
   user's most recently active workspace.
2. **Wiki** opens `/wiki/{defaultWorkspaceSlug}`.

`Wiki` and `Company Wiki` will be removed from the Work sidebar to avoid two
paths to the same product. Settings remains a separate app-rail destination.
The AI app-rail item is not introduced by this change.

The Wiki route must render inside the authenticated app shell so the top
navigation, app rail, theme, workspace data, command palette, and global modals
continue to work. The `workspaceSlug` route parameter is the active Wiki
scope, allowing existing workspace-scoped editor and API primitives to be
reused without the current `CompanyWikiRouteScope` router override.

## 5. Routing and compatibility

### 5.1 Canonical routes

| Route                          | Behavior                                      |
| ------------------------------ | --------------------------------------------- |
| `/wiki`                        | Redirect to `/wiki/{defaultWorkspaceSlug}`    |
| `/wiki/:workspaceSlug`         | Show Home for the selected Wiki workspace     |
| `/wiki/:workspaceSlug/:pageId` | Show the selected Wiki page in the same shell |

The configured default workspace is displayed as **Instance Wiki**, but its
real slug remains visible in the URL. The default workspace must not appear a
second time in the ordinary workspace list.

### 5.2 Legacy redirects

| Legacy route                   | Destination                            |
| ------------------------------ | -------------------------------------- |
| `/company-wiki`                | `/wiki/{defaultWorkspaceSlug}`         |
| `/company-wiki/:pageId`        | `/wiki/{defaultWorkspaceSlug}/:pageId` |
| `/:workspaceSlug/wiki`         | `/wiki/:workspaceSlug`                 |
| `/:workspaceSlug/wiki/:pageId` | `/wiki/:workspaceSlug/:pageId`         |

Redirects must preserve relevant query parameters and use replace semantics so
browser Back does not bounce between the legacy and canonical URL.

## 6. Wiki shell and responsive layout

The Wiki shell persists across Home and page-detail navigation.

### 6.1 Desktop

- A resizable/collapsible Wiki sidebar, approximately 280px by default.
- A main content region for Home or the Page editor.
- No AI sidecar in this phase; the main content uses the remaining width.
- A shell extension slot allows a future right sidecar without restructuring
  routes or the editor.

### 6.2 Mobile and narrow screens

- The Wiki sidebar becomes a drawer.
- Opening a page closes the drawer and gives the editor the full width.
- The active scope and page remain visible in the header/breadcrumb.
- No fixed assumptions are made about the 1168x854 reference viewport.

## 7. Wiki sidebar information architecture

The sidebar contains:

```text
New page

Instance Wiki                 (configured default workspace)
  Home
  Collections
    Collection A
      Page
      Child page
  Pages

Workspaces
  Marketing
    Collections
    Pages
  Engineering
    Collections
    Pages

Favorites
My pages
Shared with me
```

Rules:

- Instance Wiki is always first when its policy allows the current user to
  read it.
- Ordinary workspace categories include only active workspace memberships for
  the current user.
- A workspace category is lazy-loaded when expanded or directly selected.
- Collections and nested pages use the existing sort order and hierarchy.
- The active workspace and page are highlighted.
- Expanded workspace and collection state is retained while navigating inside
  the Wiki app.
- Favorites, My pages, and Shared with me aggregate visible Wiki pages across
  authorized scopes and show each page's workspace label.
- Archived pages do not appear in the primary tree. Archive management remains
  reachable from an explicit menu/view.
- Creation controls are shown only when the current user can create in the
  selected workspace.

## 8. Workspace Home and default bootstrap

`/wiki/:workspaceSlug` renders a **system Home dashboard**, not a flat list and
not a special editable Page.

Home is intentionally separate from durable Wiki content:

- member view: existing Plane greeting, Wiki-only recents
  (`workspace_page`), and workspace stickies;
- Company Wiki open-read non-members: greeting plus an authorized
  recently-updated fallback; member-only recents/stickies APIs are not called;
- Favorites, Collections, Shared, Private, Archived, and the page hierarchy
  stay in navigation and are not duplicated in the Home body;
- Home is a leaf navigation destination and never owns child pages.

Every Wiki scope gets a durable starting point in the content hierarchy:

```text
Collections
  General
    Welcome to ...
```

For fresh workspaces, `General` is a public default Collection and the Welcome
document is an ordinary editable Workspace Wiki Page. Existing installations
are normalized by a one-time idempotent data migration: every active
pre-WikiCE workspace receives defaults, legacy uncollected **public root** Wiki
pages are attached to a newly-created General Collection, while private,
shared, archived, Project Page, and already-collected data is preserved.

No `entry_page_id` or special Home Page entity is introduced.

The normative Home/bootstrap/migration rules are specified in
[Wiki Home, Default Collection, and Legacy Bootstrap Design](./2026-09-24-wiki-home-bootstrap-design.md).

## 9. Page view

`/wiki/:workspaceSlug/:pageId` reuses the existing Workspace Page editor and
associated capabilities:

- collaborative editing and syncing;
- page title/icon editing;
- breadcrumbs and hierarchy;
- comments;
- favorites;
- access and sharing controls;
- locking, archive/restore, duplicate, export, and version history;
- editor asset handling and `workspace_page` realtime documents.

Switching workspace scope must dispose the previous editor/realtime lifecycle
before connecting to the next page. Page state from one workspace must never
be displayed while another workspace is active.

## 10. Search

The `Search pages Command-F` button currently rendered in Wiki headers will be
removed. The top-navigation search is the only search entry point.

When invoked in the Wiki app, search covers Instance Wiki plus every workspace
the user is authorized to search. Results are grouped or labeled by workspace
and include enough routing metadata to open:

```text
/wiki/:workspaceSlug/:pageId
```

The backend provides the aggregate search. The browser must not fetch every
workspace and filter locally.

A result contains at least:

```text
page_id
page_name
workspace_slug
workspace_name
logo_props
matched_content_summary (optional)
```

Search applies the same effective page visibility rules as direct navigation:
workspace membership or the configured Instance Wiki read policy, page owner
access, direct shares, collection membership/inheritance, archive state, and
private collection boundaries. Unauthorized titles and content must never be
returned.

Outside the Wiki app, the existing workspace/project search behavior remains
unchanged, but workspace-wide searches must also return visible Workspace Wiki
pages for that workspace.

## 11. State and component boundaries

### 11.1 Components

- `WikiAppLayout`: authentication, app shell, active scope, and persistent
  layout.
- `WikiSidebar`: workspace/category navigation and lazy-loading boundaries.
- `WikiHome`: selected-scope dashboard.
- `WikiPageView`: active Page editor surface.
- `WikiLegacyRedirect`: compatibility routing.
- `WikiSearchResults`: Wiki-specific grouping and routing in the existing
  command/search surface.

Each component consumes an explicit `workspaceSlug`; it must not infer a
different workspace from stale global state.

### 11.2 Navigation metadata store

The existing Workspace Page and Collection stores cannot represent several
expanded Wiki workspaces safely:

- Workspace Page data is currently held in one unscoped map.
- Collection fetch replaces the whole collection map.
- Workspace Page entities capture the router slug when constructed; a page
  constructed under the wrong route scope keeps that wrong slug for mutations.

Introduce a Wiki navigation state boundary partitioned by `workspaceSlug`:

```text
scope[workspaceSlug]
  pages
  collections
  collectionPages
  loading/error state
  loadedAt
```

The navigation store holds lightweight metadata only. Active editor data may
continue using the existing Workspace Page store after it is made scope-safe:
it must either partition active data or reset atomically before a new scope is
rendered. Mutation handlers must bind to the page's source workspace rather
than reading a later router value.

Lazy loads are cached per scope. Expanding one workspace must not replace or
invalidate another workspace's navigation data.

## 12. Backend and ACL

Existing workspace-scoped CRUD APIs remain the source of truth for pages and
collections. They continue enforcing workspace, page, share, and collection
permissions.

The Wiki app adds an authenticated aggregate-search endpoint. Its authorized
scope set is:

1. the configured default workspace when the Instance Wiki open-read policy
   permits it, or when the user is a member; and
2. ordinary workspaces where the user has an active membership.

Within every scope, results are filtered by centralized effective Page access.
The endpoint must avoid per-result permission queries and must cap total and
per-workspace results.

Direct navigation to `/wiki/:workspaceSlug` must be authorized server-side.
Hiding a category in React is not an access control. A workspace that the user
cannot access produces the existing not-found/not-authorized behavior without
revealing its Wiki structure.

## 13. Loading and error states

- Missing or invalid default workspace configuration shows a Wiki-unavailable
  screen. Administrators receive a configuration hint; ordinary users do not
  receive internal configuration details.
- A failed lazy load is isolated to its workspace category and offers Retry.
- A page that is deleted or becomes inaccessible while open returns to the
  selected workspace Home.
- Search failure does not unmount the Wiki shell or editor and offers Retry in
  the search surface.
- Editor sync failures continue using the existing sync/error indicator.
- Navigation uses skeletons with stable dimensions to avoid sidebar layout
  jumps.

## 14. Accessibility and interaction requirements

- Sidebar disclosures expose expanded state and keyboard controls.
- Every icon-only action has an accessible label.
- Active workspace/page state is conveyed without relying only on color.
- Focus returns predictably when the mobile drawer closes.
- Tree navigation supports keyboard movement consistent with existing Plane
  navigation primitives.
- Reduced-motion preferences are respected for drawer and sidebar transitions.

## 15. Testing strategy

### 15.1 Backend contract tests

- Aggregate search includes the configured default scope when policy permits.
- Aggregate search includes only active workspace memberships.
- Public, owner-private, directly shared, and collection-inherited visibility
  are covered explicitly.
- Private pages and private collection subtrees never leak to unauthorized
  users.
- Archived, deleted, and cross-workspace pages are excluded.
- Result records contain the correct workspace slug and canonical Wiki URL
  inputs.
- Direct requests for unauthorized scopes return 403/404 without metadata
  leakage.

### 15.2 Store and unit tests

- Loading two workspace categories retains both datasets without collision.
- A failed scope load does not clear successful scopes.
- Mutating a page uses its source workspace slug after navigation changes.
- Default workspace resolution and canonical URL builders cover empty and
  configured states.
- Legacy redirect builders preserve page ids and relevant query parameters.

### 15.3 Component and route tests

- App rail renders Work and Wiki as independent destinations.
- Work sidebar no longer renders Wiki or Company Wiki.
- Wiki entry opens the configured default workspace Home.
- Workspace categories respect the user's membership list and lazy-load once.
- Active workspace/page highlighting follows the URL.
- Home and page detail share one persistent Wiki shell.
- The duplicate Wiki search trigger is absent.
- Search results open the correct canonical route.
- Desktop sidebar and mobile drawer behavior are covered.

### 15.4 Manual acceptance

Verify at 1168x854 and a mobile viewport:

1. Click Wiki and land on the configured default workspace Home.
2. Expand two accessible workspaces and confirm both trees remain populated.
3. Open and edit pages in different workspaces without stale content or
   realtime crossover.
4. Create, favorite, share, archive, and restore a page subject to permissions.
5. Search for Wiki content and verify workspace labels and canonical routes.
6. Confirm unauthorized workspaces and private content never appear.
7. Follow every legacy URL form and verify its canonical redirect.
8. Return to Work and confirm the previous Work workspace is retained.

Run focused tests first, followed by formatting, lint, type checking, relevant
backend contract tests, and the web build.

## 16. Documentation updates required during implementation

The existing `docs/wiki-ce-spec.md` and
`docs/wiki-ce-implementation-plan.md` describe `/company-wiki` as the canonical
route. Implementation must update those documents to make the unified
`/wiki/:workspaceSlug` model normative and describe `/company-wiki` only as a
compatibility redirect.

## 17. Acceptance criteria

The feature is complete when:

- Wiki is an app-level destination beside Work.
- Clicking Wiki opens Home for the configured default workspace.
- The Wiki sidebar groups only authorized scopes and keeps their navigation
  data isolated.
- Home and page detail render in one persistent responsive shell.
- Workspace Wiki and Company Wiki duplicates are removed from Work navigation.
- Global Wiki search returns visible Wiki pages with correct workspace routing.
- Legacy Wiki links redirect without breaking bookmarks.
- No AI sidecar or fake AI conversation UI is included.
- Automated and manual acceptance checks pass with no known cross-workspace
  data or permission leakage.
