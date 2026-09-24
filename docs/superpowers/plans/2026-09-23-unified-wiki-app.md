# Unified Wiki App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate Workspace Wiki and Company Wiki surfaces with one app-level Wiki shell at `/wiki/:workspaceSlug`, defaulting to the configured Instance Wiki workspace and grouping every ACL-visible workspace in one sidebar.

**Architecture:** Add a global authenticated Wiki route whose `workspaceSlug` parameter drives the existing workspace Page editor, while a new slug-partitioned navigation store caches lightweight page and collection metadata for multiple expanded workspaces. Add backend endpoints that return the user's Wiki scopes and perform ACL-safe aggregate Wiki search; keep existing workspace CRUD, assets, realtime, comments, and versioning unchanged.

**Tech Stack:** React Router 7, React 18, TypeScript strict mode, MobX, SWR, Propel/Plane UI, Django REST Framework, PostgreSQL, pytest, Vitest, pnpm/Turbo.

## Global Constraints

- Canonical routes are `/wiki/:workspaceSlug` and `/wiki/:workspaceSlug/:pageId`; `/wiki` redirects to the configured default workspace slug.
- The configured default workspace is labeled `Instance Wiki` but remains a real workspace identified by `COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG`.
- Ordinary workspace categories include only active memberships; every page and collection remains subject to effective ACL checks.
- Project Pages remain in Work and are not included in the Wiki app.
- The top-navigation search is the only search entry point; remove the duplicate Wiki search button.
- No Plane AI sidecar, fake AI conversation, nullable `Page.workspace`, `InstancePage`, or `instance_page` realtime type is introduced.
- Load the default scope immediately and all other workspace navigation data lazily.
- Preserve old `/company-wiki/*` and `/:workspaceSlug/wiki/*` bookmarks through replace redirects.
- Use strict TypeScript, MobX reactive patterns, existing Plane UI primitives, `workspace:*` internal dependencies, `catalog:` external dependencies, oxfmt, and OxLint.
- Follow test-driven development: add one failing test, run it and confirm the expected failure, add minimal production code, then rerun to green.

---

## File Structure

New focused units:

- `apps/web/core/helpers/wiki-routes.ts` — canonical and legacy Wiki URL construction.
- `apps/web/core/store/wiki/wiki-navigation.store.ts` — slug-partitioned navigation metadata and lazy loading.
- `apps/web/core/hooks/store/use-wiki-navigation.ts` — typed store hook.
- `apps/web/core/services/wiki.service.ts` — global Wiki scopes and aggregate-search HTTP client.
- `apps/web/core/components/wiki/shell.tsx` — persistent desktop/mobile Wiki layout.
- `apps/web/core/components/wiki/sidebar/*` — workspace, collection, and page-tree navigation.
- `apps/web/core/components/wiki/home.tsx` — selected-workspace Home dashboard.
- `apps/web/app/(all)/wiki/*` — global Wiki route layout, Home, detail, and root redirect.
- `apps/api/plane/app/views/search/wiki.py` — authorized Wiki scopes and aggregate Wiki search.
- `apps/api/plane/tests/contract/app/test_unified_wiki_search_app.py` — API security and result-shape contract.

Existing units to adapt:

- `apps/web/core/components/navigation/app-rail-hoc.tsx` — Work and Wiki app-rail entries.
- `packages/constants/src/workspace.ts` and `apps/web/core/components/workspace/sidebar/*` — remove duplicate Work-sidebar Wiki entries.
- `apps/web/app/routes/extended.ts` — canonical global routes and compatibility redirects.
- `apps/web/core/components/power-k/ui/modal/*` — Wiki-aware aggregate search.
- `apps/web/core/store/pages/workspace-page.ts` and `workspace-page.store.ts` — bind mutations to their source workspace and prevent stale scope display.
- `docs/wiki-ce-spec.md` and `docs/wiki-ce-implementation-plan.md` — make the unified route normative.

---

### Task 1: Establish web unit-test support and the Wiki URL contract

**Files:**

- Modify: `apps/web/package.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/core/helpers/wiki-routes.ts`
- Create: `apps/web/tests/wiki/wiki-routes.test.ts`

**Interfaces:**

- Produces: `getWikiHomePath(workspaceSlug: string): string`
- Produces: `getWikiPagePath(workspaceSlug: string, pageId: string): string`
- Produces: `getDefaultWikiPath(defaultWorkspaceSlug: string): string`
- Produces: `resolveLegacyWikiPath(pathname: string, defaultWorkspaceSlug: string): string | null`

- [ ] **Step 1: Add the test command and Vitest configuration**

Add `"test": "vitest run"` and `"test:watch": "vitest"` to `apps/web/package.json`, add `vitest: "catalog:"` to its dev dependencies, and create:

```ts
// apps/web/vitest.config.ts
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./core", import.meta.url)) } },
  test: {
    environment: "node",
    globals: true,
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
});
```

- [ ] **Step 2: Write the failing route-helper tests**

Run `pnpm install --lockfile-only` at the repo root after adding `vitest` so `pnpm-lock.yaml` is updated before the first test.

```ts
// apps/web/tests/wiki/wiki-routes.test.ts
import { describe, expect, test } from "vitest";
import { getDefaultWikiPath, getWikiHomePath, getWikiPagePath, resolveLegacyWikiPath } from "@/helpers/wiki-routes";

describe("Wiki routes", () => {
  test("uses the configured workspace slug for Home and page routes", () => {
    expect(getDefaultWikiPath("home")).toBe("/wiki/home");
    expect(getWikiHomePath("mkt")).toBe("/wiki/mkt");
    expect(getWikiPagePath("mkt", "page-1")).toBe("/wiki/mkt/page-1");
  });

  test("maps legacy company and workspace Wiki URLs", () => {
    expect(resolveLegacyWikiPath("/company-wiki", "home")).toBe("/wiki/home");
    expect(resolveLegacyWikiPath("/company-wiki/page-1", "home")).toBe("/wiki/home/page-1");
    expect(resolveLegacyWikiPath("/mkt/wiki", "home")).toBe("/wiki/mkt");
    expect(resolveLegacyWikiPath("/mkt/wiki/page-2", "home")).toBe("/wiki/mkt/page-2");
  });

  test("rejects empty path segments", () => {
    expect(() => getDefaultWikiPath("")).toThrow("Default Wiki workspace slug is not configured");
    expect(() => getWikiPagePath("mkt", "")).toThrow("Wiki page id is required");
  });
});
```

- [ ] **Step 3: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-routes.test.ts`

Expected: FAIL because `@/helpers/wiki-routes` does not exist.

- [ ] **Step 4: Implement the route helpers**

```ts
// apps/web/core/helpers/wiki-routes.ts
const cleanSegment = (value: string): string => value.trim().replace(/^\/+|\/+$/g, "");

export const getWikiHomePath = (workspaceSlug: string): string => {
  const slug = cleanSegment(workspaceSlug);
  if (!slug) throw new Error("Wiki workspace slug is required");
  return `/wiki/${slug}`;
};

export const getDefaultWikiPath = (defaultWorkspaceSlug: string): string => {
  const slug = cleanSegment(defaultWorkspaceSlug);
  if (!slug) throw new Error("Default Wiki workspace slug is not configured");
  return getWikiHomePath(slug);
};

export const getWikiPagePath = (workspaceSlug: string, pageId: string): string => {
  const id = cleanSegment(pageId);
  if (!id) throw new Error("Wiki page id is required");
  return `${getWikiHomePath(workspaceSlug)}/${id}`;
};

export const resolveLegacyWikiPath = (pathname: string, defaultWorkspaceSlug: string): string | null => {
  const companyMatch = pathname.match(/^\/company-wiki(?:\/([^/]+))?\/?$/);
  if (companyMatch) {
    return companyMatch[1]
      ? getWikiPagePath(defaultWorkspaceSlug, companyMatch[1])
      : getDefaultWikiPath(defaultWorkspaceSlug);
  }

  const workspaceMatch = pathname.match(/^\/([^/]+)\/wiki(?:\/([^/]+))?\/?$/);
  if (!workspaceMatch) return null;
  return workspaceMatch[2] ? getWikiPagePath(workspaceMatch[1], workspaceMatch[2]) : getWikiHomePath(workspaceMatch[1]);
};
```

- [ ] **Step 5: Run focused tests and checks**

Run: `pnpm --filter=web test -- tests/wiki/wiki-routes.test.ts`

Expected: 3 tests PASS.

Run: `pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/vitest.config.ts apps/web/core/helpers/wiki-routes.ts apps/web/tests/wiki/wiki-routes.test.ts pnpm-lock.yaml
git commit -m "test(web): establish unified wiki route contract"
```

### Task 2: Add authorized Wiki scopes and aggregate search APIs

**Files:**

- Create: `apps/api/plane/app/views/search/wiki.py`
- Modify: `apps/api/plane/app/views/__init__.py:197-198`
- Modify: `apps/api/plane/app/urls/search.py:7-31`
- Create: `apps/api/plane/tests/contract/app/test_unified_wiki_search_app.py`

**Interfaces:**

- Produces: `GET /api/wiki/scopes/`
- Produces: `GET /api/wiki/search/?query=<text>&limit=<1..100>`
- Produces: `GET /api/wiki/personal/?section=favorites|owned|shared`
- Produces scope rows `{ id, slug, name, is_default, is_member, can_create }`
- Produces search rows `{ page_id, page_name, workspace_slug, workspace_name, logo_props, matched_content_summary }`

- [ ] **Step 1: Write failing scope and search contract tests**

Use the existing `api_client` and `create_user` fixtures from `plane/tests/conftest.py`. Define these local helpers in the test module; `create_user` is a fixture value, not a callable factory:

```py
from plane.db.models import Page, User, Workspace, WorkspaceMember


def make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0])


def make_workspace(name, slug, owner):
    return Workspace.objects.create(name=name, slug=slug, owner=owner)


def add_member(workspace, user):
    return WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)


def make_wiki_page(workspace, owner, name, access=Page.PUBLIC_ACCESS):
    return Page.objects.create(workspace=workspace, owned_by=owner, name=name, access=access, is_global=True)
```

```py
@pytest.mark.django_db
def test_scopes_include_default_and_active_memberships_only(api_client, settings, create_user):
    user = create_user
    default = make_workspace("Instance", "home", user)
    allowed = make_workspace("Marketing", "mkt", user)
    denied = make_workspace("Finance", "fin", user)
    add_member(allowed, user)
    settings.COMPANY_WIKI_WORKSPACE_SLUG = default.slug
    settings.COMPANY_WIKI_OPEN_READ = True
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/wiki/scopes/")

    assert response.status_code == 200
    assert [(row["slug"], row["is_default"], row["is_member"]) for row in response.json()] == [
        ("home", True, False),
        ("mkt", False, True),
    ]
    assert "fin" not in {row["slug"] for row in response.json()}


@pytest.mark.django_db
def test_search_returns_only_effectively_visible_pages(api_client, settings, create_user):
    user = create_user
    owner = make_user("owner@example.com")
    default = make_workspace("Instance", "home", owner)
    allowed = make_workspace("Marketing", "mkt", owner)
    denied = make_workspace("Finance", "fin", owner)
    add_member(allowed, user)
    settings.COMPANY_WIKI_WORKSPACE_SLUG = default.slug
    settings.COMPANY_WIKI_OPEN_READ = True
    public_default = make_wiki_page(default, owner, "Launch handbook", access=Page.PUBLIC_ACCESS)
    public_allowed = make_wiki_page(allowed, owner, "Launch checklist", access=Page.PUBLIC_ACCESS)
    private_denied = make_wiki_page(denied, owner, "Launch payroll", access=Page.PRIVATE_ACCESS)
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/wiki/search/", {"query": "Launch", "limit": 20})

    assert response.status_code == 200
    rows = response.json()["results"]
    assert {row["page_id"] for row in rows} == {str(public_default.id), str(public_allowed.id)}
    assert str(private_denied.id) not in {row["page_id"] for row in rows}
    assert {row["workspace_slug"] for row in rows} == {"home", "mkt"}
```

Add separate tests with the same fixture helpers for owner-private pages, direct shares, private collection boundaries, archived pages, a disabled `COMPANY_WIKI_OPEN_READ`, an empty query returning 400, and `limit=101` returning 400. Assert exact returned page-id sets for visibility cases and HTTP 400 for invalid input.

Add personal-section tests proving `favorites` returns only the caller's page favorites, `owned` returns only pages owned by the caller, `shared` returns only active direct shares, every row includes its source workspace, and none of the three sections leaks an unauthorized private collection subtree.

- [ ] **Step 2: Run the contract file and confirm RED**

Run: `docker compose -f docker-compose-test.yml run --rm api-tests pytest plane/tests/contract/app/test_unified_wiki_search_app.py -q`

Expected: FAIL with 404 for `/api/wiki/scopes/`, `/api/wiki/search/`, and `/api/wiki/personal/`.

- [ ] **Step 3: Implement the three endpoints**

Implement `UnifiedWikiScopesEndpoint(BaseAPIView)`, `UnifiedWikiSearchEndpoint(BaseAPIView)`, and `UnifiedWikiPersonalPagesEndpoint(BaseAPIView)` in `views/search/wiki.py`. Build the authorized workspace set from active `WorkspaceMember` rows plus the configured default workspace when `company_wiki_open_read(default_workspace)` is true. An active member still sees that workspace when open-read is disabled. For each authorized workspace, combine `page_visibility_q(request.user, workspace)` into one workspace-qualified `Q`, collect `hidden_page_ids`, and issue one final Page query:

```py
name_or_content = Q(name__icontains=query) | Q(description_stripped__icontains=query)
pages = (
    Page.objects.filter(
        name_or_content,
        visibility,
        is_global=True,
        archived_at__isnull=True,
        deleted_at__isnull=True,
    )
    .exclude(id__in=hidden_ids)
    .select_related("workspace")
    .order_by("-updated_at")[:limit]
)
```

Serialize search rows without returning full document HTML. Use at most 160 characters from `description_stripped` for `matched_content_summary`. Scope ordering is default first, then case-insensitive workspace name. Cap total results at 100 and each workspace at 20 with deterministic `-updated_at, id` ordering. If a single SQL query cannot enforce both limits clearly, issue one bounded query per workspace and merge those bounded results. Use `page_visibility_q` and `hidden_page_ids` once per workspace to avoid per-page permission queries.

The personal endpoint validates `section` against `favorites`, `owned`, and `shared`, starts from the same authorized/visible Page queryset, then applies exactly one of these filters:

```py
if section == "favorites":
    queryset = queryset.filter(
        id__in=UserFavorite.objects.filter(
            user=request.user,
            entity_type="page",
            deleted_at__isnull=True,
        ).values("entity_identifier")
    )
elif section == "owned":
    queryset = queryset.filter(owned_by=request.user)
else:
    queryset = queryset.filter(shares__member=request.user, shares__deleted_at__isnull=True)
```

Return lightweight page metadata and workspace identity, never document HTML.

Register:

```py
path("wiki/scopes/", UnifiedWikiScopesEndpoint.as_view(), name="unified-wiki-scopes"),
path("wiki/search/", UnifiedWikiSearchEndpoint.as_view(), name="unified-wiki-search"),
path("wiki/personal/", UnifiedWikiPersonalPagesEndpoint.as_view(), name="unified-wiki-personal"),
```

- [ ] **Step 4: Run the contract tests and existing Wiki security tests**

Run: `docker compose -f docker-compose-test.yml run --rm api-tests pytest plane/tests/contract/app/test_unified_wiki_search_app.py plane/tests/contract/app/test_workspace_page_app.py plane/tests/contract/app/test_page_share_app.py -q`

Expected: PASS with no private-title or cross-workspace leakage.

- [ ] **Step 5: Commit**

```bash
git add apps/api/plane/app/views/search/wiki.py apps/api/plane/app/views/__init__.py apps/api/plane/app/urls/search.py apps/api/plane/tests/contract/app/test_unified_wiki_search_app.py
git commit -m "feat(api): add authorized unified wiki discovery"
```

### Task 3: Add frontend Wiki API types and a slug-partitioned navigation store

**Files:**

- Create: `packages/types/src/page/wiki-navigation.ts`
- Modify: `packages/types/src/page/index.ts`
- Create: `apps/web/core/services/wiki.service.ts`
- Create: `apps/web/core/store/wiki/wiki-navigation.store.ts`
- Create: `apps/web/core/hooks/store/use-wiki-navigation.ts`
- Modify: `apps/web/core/store/root.store.ts:80-150`
- Create: `apps/web/tests/wiki/wiki-navigation.store.test.ts`

**Interfaces:**

- Produces: `TWikiScope`, `TWikiSearchResult`, `TWikiNavigationScopeState`
- Produces: `WikiService.fetchScopes()` and `WikiService.search(query, limit)`
- Produces: `IWikiNavigationStore.fetchScope(workspaceSlug)` and `fetchCollectionPages(workspaceSlug, collectionId)`
- Produces: `new WikiNavigationStore(services?: TWikiNavigationServices)` for production defaults and test fakes

- [ ] **Step 1: Write failing store-isolation tests**

Use injected fake page and collection services and assert:

```ts
test("keeps two loaded workspace scopes isolated", async () => {
  const store = new WikiNavigationStore({
    pageService: {
      fetchAll: async (slug) =>
        slug === "home"
          ? ([{ id: "home-page", name: "Handbook" }] as TPage[])
          : ([{ id: "mkt-page", name: "Campaign" }] as TPage[]),
    },
    collectionService: {
      fetchAll: async (slug) =>
        slug === "home"
          ? ([{ id: "home-col", name: "Policies" }] as TPageCollection[])
          : ([{ id: "mkt-col", name: "Brand" }] as TPageCollection[]),
      fetchPages: async () => [],
    },
  });

  await store.fetchScope("home");
  await store.fetchScope("mkt");

  expect(store.getScope("home").pageIds).toEqual(["home-page"]);
  expect(store.getScope("mkt").pageIds).toEqual(["mkt-page"]);
  expect(store.getScope("home").collectionIds).toEqual(["home-col"]);
});

test("retains a successful scope when another scope fails", async () => {
  const store = new WikiNavigationStore({
    pageService: {
      fetchAll: async (slug) => {
        if (slug === "mkt") throw new Error("mkt failed");
        return [{ id: "home-page", name: "Handbook" }] as TPage[];
      },
    },
    collectionService: {
      fetchAll: async () => [],
      fetchPages: async () => [],
    },
  });
  await store.fetchScope("home");
  await expect(store.fetchScope("mkt")).rejects.toThrow("mkt failed");
  expect(store.getScope("home").status).toBe("loaded");
  expect(store.getScope("mkt").status).toBe("error");
});
```

- [ ] **Step 2: Run the store test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-navigation.store.test.ts`

Expected: FAIL because the Wiki navigation store and types do not exist.

- [ ] **Step 3: Add API types and service**

Define:

```ts
export type TWikiScope = {
  id: string;
  slug: string;
  name: string;
  is_default: boolean;
  is_member: boolean;
  can_create: boolean;
};

export type TWikiSearchResult = {
  page_id: string;
  page_name: string;
  workspace_slug: string;
  workspace_name: string;
  logo_props: TLogoProps | null;
  matched_content_summary: string;
};

export type TWikiSearchResponse = { results: TWikiSearchResult[] };

export type TWikiPersonalSection = "favorites" | "owned" | "shared";
export type TWikiPersonalPage = Pick<
  TWikiSearchResult,
  "page_id" | "page_name" | "workspace_slug" | "workspace_name" | "logo_props"
>;
```

`WikiService` calls `/api/wiki/scopes/`, `/api/wiki/search/`, and `/api/wiki/personal/` through `APIService`. Expose `fetchPersonalPages(section: TWikiPersonalSection)` so the sidebar can render personal sections without eagerly loading every workspace tree.

- [ ] **Step 4: Implement the partitioned store**

Define `TWikiNavigationServices` as two narrow service contracts: `pageService.fetchAll(workspaceSlug)` and `collectionService.fetchAll(workspaceSlug)`/`fetchPages(workspaceSlug, collectionId)`. The constructor uses real `WorkspacePageService` and `WorkspacePageCollectionService` defaults when no services are supplied.

Store each scope under `scopes[workspaceSlug]` with `pagesById`, `pageIds`, `collectionsById`, `collectionIds`, `collectionPagesById`, `status`, and `error`. `fetchScope` must `Promise.all` the workspace page and collection list calls, update only the requested slug inside one MobX action, and return cached data when status is already `loaded`. `fetchCollectionPages` updates only `scopes[slug].collectionPagesById[collectionId]`.

Expose it from `CoreRootStore` as `wikiNavigation` and through `useWikiNavigation()`.

- [ ] **Step 5: Run focused tests and type checking**

Run: `pnpm --filter=web test -- tests/wiki/wiki-navigation.store.test.ts`

Expected: PASS.

Run: `pnpm --filter=@plane/types check:types && pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/types/src/page/wiki-navigation.ts packages/types/src/page/index.ts apps/web/core/services/wiki.service.ts apps/web/core/store/wiki/wiki-navigation.store.ts apps/web/core/hooks/store/use-wiki-navigation.ts apps/web/core/store/root.store.ts apps/web/tests/wiki/wiki-navigation.store.test.ts
git commit -m "feat(web): add scoped wiki navigation state"
```

### Task 4: Make Workspace Page mutations scope-safe

**Files:**

- Modify: `apps/web/core/store/pages/workspace-page.ts:20-190`
- Modify: `apps/web/core/store/pages/workspace-page.store.ts:205-390`
- Create: `apps/web/tests/wiki/workspace-page-scope.test.ts`

**Interfaces:**

- Changes: `new WorkspacePage(store, page, sourceWorkspaceSlug)`
- Produces: every page mutation uses immutable `sourceWorkspaceSlug`
- Produces: `WorkspacePageStore.activateScope(workspaceSlug)` clears stale active data atomically

- [ ] **Step 1: Write the failing source-scope test**

Spy on `WorkspacePageService.prototype.update`, construct a `WorkspacePage` with source slug `home`, change the fake root router slug to `mkt`, call `update({ name: "Updated" })`, and assert the spy received `("home", page.id, { name: "Updated" })` rather than `mkt`.

Also load `home`, call `activateScope("mkt")`, and assert `getPageById("home-page")` is undefined before the `mkt` response resolves.

- [ ] **Step 2: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/workspace-page-scope.test.ts`

Expected: FAIL because the constructor does not accept an explicit source slug and `activateScope` does not exist. The current constructor captures the router slug once, so an entity created under the wrong route scope retains that wrong slug.

- [ ] **Step 3: Bind entity services to the source slug**

Add a private constructor field. Preserve the current `page.id` guard in every service callback; replace the captured router slug source with `sourceWorkspaceSlug`:

```ts
constructor(store: RootStore, page: TPage, private readonly sourceWorkspaceSlug: string) {
  super(store, page, {
    update: async (payload) => {
      if (!page.id) throw new Error("Missing required fields.");
      return await workspacePageService.update(sourceWorkspaceSlug, page.id, payload);
    },
    updateDescription: async (document) => {
      if (!page.id) throw new Error("Missing required fields.");
      await workspacePageService.updateDescription(sourceWorkspaceSlug, page.id, document);
    },
    updateAccess: async (payload) => {
      if (!page.id) throw new Error("Missing required fields.");
      await workspacePageService.updateAccess(sourceWorkspaceSlug, page.id, payload);
    },
    lock: async () => {
      if (!page.id) throw new Error("Missing required fields.");
      await workspacePageService.lock(sourceWorkspaceSlug, page.id);
    },
    unlock: async () => {
      if (!page.id) throw new Error("Missing required fields.");
      await workspacePageService.unlock(sourceWorkspaceSlug, page.id);
    },
    archive: async () => {
      if (!page.id) throw new Error("Missing required fields.");
      return await workspacePageService.archive(sourceWorkspaceSlug, page.id);
    },
    restore: async () => {
      if (!page.id) throw new Error("Missing required fields.");
      await workspacePageService.restore(sourceWorkspaceSlug, page.id);
    },
    duplicate: async () => {
      if (!page.id) throw new Error("Missing required fields.");
      return await workspacePageService.duplicate(sourceWorkspaceSlug, page.id);
    },
  });
}
```

Pass the fetched `workspaceSlug` whenever `WorkspacePageStore` creates an entity. Track `activeWorkspaceSlug`; `activateScope` clears `data`, resets filters, and updates the active slug in one `runInAction` before a new fetch. Ignore a late response if its slug differs from `activeWorkspaceSlug`. Use `sourceWorkspaceSlug` for the entity permission lookup and `getRedirectionLink`; audit inherited `BasePage` favorite/move actions for router-scope reads.

- [ ] **Step 4: Run focused tests**

Run: `pnpm --filter=web test -- tests/wiki/workspace-page-scope.test.ts`

Expected: PASS.

Run: `pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/store/pages/workspace-page.ts apps/web/core/store/pages/workspace-page.store.ts apps/web/tests/wiki/workspace-page-scope.test.ts
git commit -m "fix(wiki): bind page mutations to source workspace"
```

### Task 5: Split the app rail into Work and Wiki and remove duplicate Work-sidebar entries

**Files:**

- Modify: `apps/web/core/components/navigation/app-rail-hoc.tsx:7-43`
- Modify: `apps/web/core/components/navigation/app-rail-root.tsx:22-84`
- Create: `apps/web/core/components/navigation/app-rail-items.ts`
- Modify: `packages/constants/src/workspace.ts:275-305`
- Modify: `apps/web/core/components/workspace/sidebar/sidebar-item.tsx:38-76`
- Create: `apps/web/tests/navigation/app-rail-items.test.ts`
- Modify: `packages/i18n/src/locales/en/navigation.json`

**Interfaces:**

- Produces: `buildAppRailItems({ workWorkspaceSlug, wikiWorkspaceSlug, pathname })`
- Consumes: `getDefaultWikiPath()` from Task 1

- [ ] **Step 1: Write failing app-rail model tests**

```ts
test("builds independent Work and Wiki destinations", () => {
  expect(
    buildAppRailItems({ workWorkspaceSlug: "test", wikiWorkspaceSlug: "home", pathname: "/wiki/home" }).map(
      ({ label, href, isActive }) => ({ label, href, isActive })
    )
  ).toEqual([
    { label: "Work", href: "/test/", isActive: false },
    { label: "Wiki", href: "/wiki/home", isActive: true },
  ]);
});
```

Add a second test proving `/test/projects` activates Work and not Wiki.

- [ ] **Step 2: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/navigation/app-rail-items.test.ts`

Expected: FAIL because `buildAppRailItems` does not exist.

- [ ] **Step 3: Implement Work/Wiki rail entries**

Extract the pure builder, render Work with the existing Plane icon, render Wiki with `WikiIcon`, and resolve the Work href from the user's last/fallback workspace rather than the active Wiki route parameter. Use the configured default Wiki slug for the Wiki href.

Remove `company-wiki` from `WORKSPACE_SIDEBAR_STATIC_NAVIGATION_ITEMS_LINKS` and `wiki` from `WORKSPACE_SIDEBAR_STATIC_PINNED_NAVIGATION_ITEMS_LINKS`. Remove both from `SidebarItemBase.staticItems` so user preferences cannot resurrect duplicate entries.

- [ ] **Step 4: Run focused tests and checks**

Run: `pnpm --filter=web test -- tests/navigation/app-rail-items.test.ts`

Expected: PASS.

Run: `pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/components/navigation/app-rail-hoc.tsx apps/web/core/components/navigation/app-rail-root.tsx packages/constants/src/workspace.ts apps/web/core/components/workspace/sidebar/sidebar-item.tsx apps/web/tests/navigation/app-rail-items.test.ts packages/i18n/src/locales/en/navigation.json
git commit -m "feat(navigation): separate Work and Wiki apps"
```

### Task 6: Register canonical Wiki routes, access boundary, and legacy redirects

**Files:**

- Modify: `apps/web/app/routes/extended.ts`
- Create: `apps/web/app/(all)/wiki/layout.tsx`
- Create: `apps/web/app/(all)/wiki/redirect.tsx`
- Create: `apps/web/app/(all)/wiki/[workspaceSlug]/page.tsx`
- Create: `apps/web/app/(all)/wiki/[workspaceSlug]/[pageId]/page.tsx`
- Create: `apps/web/app/(all)/wiki/legacy-redirect.tsx`
- Create: `apps/web/core/layouts/auth-layout/wiki-wrapper.tsx`
- Create: `apps/web/tests/wiki/wiki-access.test.ts`

**Interfaces:**

- Consumes: `TWikiScope[]` from `WikiService.fetchScopes()`
- Produces: `WikiAuthWrapper({ workspaceSlug, children })`
- Produces canonical route parameters named `workspaceSlug` and `pageId`

- [ ] **Step 1: Write failing access-resolution tests**

Extract and test `resolveWikiScopeAccess(scopes, requestedSlug)`:

```ts
test("allows only slugs returned by the server ACL endpoint", () => {
  const scopes = [
    { id: "1", slug: "home", name: "Instance", is_default: true, is_member: false, can_create: false },
    { id: "2", slug: "mkt", name: "Marketing", is_default: false, is_member: true, can_create: true },
  ];
  expect(resolveWikiScopeAccess(scopes, "home")?.is_default).toBe(true);
  expect(resolveWikiScopeAccess(scopes, "mkt")?.can_create).toBe(true);
  expect(resolveWikiScopeAccess(scopes, "finance")).toBeUndefined();
});
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-access.test.ts`

Expected: FAIL because the Wiki access resolver does not exist.

- [ ] **Step 3: Implement route registration and redirects**

Replace the old Wiki declarations in `extended.ts` with routes under `./(all)/layout.tsx`:

```ts
layout("./(all)/wiki/layout.tsx", [
  route("wiki", "./(all)/wiki/redirect.tsx"),
  route("wiki/:workspaceSlug", "./(all)/wiki/[workspaceSlug]/page.tsx"),
  route("wiki/:workspaceSlug/:pageId", "./(all)/wiki/[workspaceSlug]/[pageId]/page.tsx"),
]),
route("company-wiki", "./(all)/wiki/legacy-redirect.tsx"),
route("company-wiki/:pageId", "./(all)/wiki/legacy-redirect.tsx"),
route(":workspaceSlug/wiki", "./(all)/wiki/legacy-redirect.tsx"),
route(":workspaceSlug/wiki/:pageId", "./(all)/wiki/legacy-redirect.tsx"),
```

The root redirect uses `replace(getDefaultWikiPath(COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG))`. The legacy redirect uses `resolveLegacyWikiPath(pathname, defaultSlug)` and preserves `location.search`.

`WikiAuthWrapper` fetches `/api/wiki/scopes/`, resolves the requested slug, shows the existing not-authorized state when absent, and renders children when present. It must not infer authorization only from the client workspace list. When `scope.is_member` is true, mount the existing workspace permission/member preload path needed by sharing and page actions. When it is false, allow only the configured default open-read scope and keep all mutation controls disabled.

When the default slug is empty or absent from the scopes response, `/wiki` renders a `Wiki is not configured` state. Show the configured-slug hint only when the current user is an instance administrator; do not let `getDefaultWikiPath` throw into the route error boundary.

- [ ] **Step 4: Run tests, route generation, and types**

Run: `pnpm --filter=web test -- tests/wiki/wiki-access.test.ts tests/wiki/wiki-routes.test.ts`

Expected: PASS.

Run: `pnpm --filter=web check:types`

Expected: React Router type generation and TypeScript PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/routes/extended.ts apps/web/app/'(all)'/wiki apps/web/core/layouts/auth-layout/wiki-wrapper.tsx apps/web/tests/wiki/wiki-access.test.ts
git commit -m "feat(wiki): add canonical global routes"
```

### Task 7: Build the persistent Wiki shell and ACL-scoped sidebar

**Files:**

- Create: `apps/web/core/components/wiki/shell.tsx`
- Create: `apps/web/core/components/wiki/sidebar/root.tsx`
- Create: `apps/web/core/components/wiki/sidebar/workspace-section.tsx`
- Create: `apps/web/core/components/wiki/sidebar/page-tree.tsx`
- Create: `apps/web/core/components/wiki/sidebar/personal-sections.tsx`
- Create: `apps/web/core/components/wiki/index.ts`
- Modify: `apps/web/app/(all)/wiki/layout.tsx`
- Create: `apps/web/tests/wiki/wiki-sidebar-model.test.ts`
- Modify: `packages/i18n/src/locales/en/wiki.json`

**Interfaces:**

- Consumes: `TWikiScope[]` and `IWikiNavigationStore`
- Produces: `buildWikiSidebarModel(scopes, defaultSlug, activeSlug, activePageId)`
- Produces: `WikiShell({ children })`

- [ ] **Step 1: Write the failing sidebar-model tests**

Assert that the default scope is first and labeled `Instance Wiki`, is excluded from the ordinary workspace group, unauthorized slugs cannot appear because the model consumes only server scopes, and page links use `/wiki/:workspaceSlug/:pageId`.

Also assert that expanding `mkt` calls `fetchScope("mkt")` once and keeps already loaded `home` data.

- [ ] **Step 2: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-sidebar-model.test.ts`

Expected: FAIL because the sidebar model does not exist.

- [ ] **Step 3: Implement the shell and sidebar**

`WikiShell` renders a resizable desktop sidebar and a Headless UI drawer on narrow screens. The sidebar renders New page, default Instance Wiki, the Workspaces disclosure, and aggregated Favorites/My pages/Shared with me sections. Personal sections call `WikiService.fetchPersonalPages` rather than loading every workspace tree. Each workspace disclosure calls `fetchScope(slug)` on first expansion; collection disclosures call `fetchCollectionPages(slug, collectionId)`.

Use buttons with `aria-expanded`, active-row text plus background treatment, keyboard-focus rings, and icon labels. Persist expanded workspace and collection ids in component state for the lifetime of the shell. Close the mobile drawer after a page link is selected and return focus to the drawer trigger. Render stable skeleton rows while loading and an isolated Retry action when a workspace or collection request fails. Apply reduced-motion variants to drawer and disclosure transitions.

- [ ] **Step 4: Run tests and type checking**

Run: `pnpm --filter=web test -- tests/wiki/wiki-sidebar-model.test.ts tests/wiki/wiki-navigation.store.test.ts`

Expected: PASS.

Run: `pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/core/components/wiki apps/web/app/'(all)'/wiki/layout.tsx apps/web/tests/wiki/wiki-sidebar-model.test.ts packages/i18n/src/locales/en/wiki.json
git commit -m "feat(wiki): add persistent multi-workspace sidebar"
```

### Task 8: Implement Workspace Home and canonical page detail

**Files:**

- Create: `apps/web/core/components/wiki/home.tsx`
- Create: `apps/web/core/components/wiki/header.tsx`
- Modify: `apps/web/app/(all)/wiki/[workspaceSlug]/page.tsx`
- Modify: `apps/web/app/(all)/wiki/[workspaceSlug]/[pageId]/page.tsx`
- Modify: `apps/web/app/(all)/[workspaceSlug]/(projects)/wiki/(detail)/[pageId]/page.tsx` by extracting reusable `WorkspaceWikiPageView`
- Modify: `apps/web/core/components/home/widgets/recents/page.tsx:29-91`
- Create: `apps/web/tests/wiki/wiki-home-model.test.ts`

**Interfaces:**

- Produces: `buildWikiHomeModel({ scope, pages, collections, recents })`
- Produces: reusable `WorkspaceWikiPageView({ workspaceSlug, pageId, buildPageHref })`
- Consumes: canonical route helpers from Task 1

- [ ] **Step 1: Write failing Home-model tests**

Test that recents and favorites are filtered to the selected workspace, collections are sorted by `sort_order`, create actions are omitted when `scope.can_create` is false, and the empty state appears only when the selected scope has no visible content.

- [ ] **Step 2: Run the test and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-home-model.test.ts`

Expected: FAIL because `buildWikiHomeModel` does not exist.

- [ ] **Step 3: Implement Home**

Fetch the selected scope through `wikiNavigation.fetchScope(workspaceSlug)` and workspace recents through the existing recents service when `scope.is_member` is true. Render compact Recently viewed, Favorites, and Collections sections, with Templates and New page actions gated by `scope.can_create`. For default open-read users who are not members, omit personalized recents. Use `getWikiPagePath` for every link.

Add an Archived entry in the Home overflow menu that sets `?view=archived` and renders the selected scope's existing archived-page list. Archived pages remain absent from the primary sidebar tree but still have an explicit management path.

Fix workspace Wiki recent links so pages without `project_id` route to `/wiki/:workspaceSlug/:pageId`, not `/:workspaceSlug/pages/:pageId`.

- [ ] **Step 4: Extract and mount the canonical page view**

Move the existing workspace Wiki editor body into `WorkspaceWikiPageView`. Keep its `WorkspacePageService`, versions service, asset handlers, comments, and `workspace_page` webhook parameters. Before fetching details, call `workspacePageStore.activateScope(workspaceSlug)`. Build all page, parent, delete, and error-state links with the canonical route helper.

The new route page passes route params directly. The old route file remains only until Task 10 converts it to a redirect.

- [ ] **Step 5: Run focused tests and types**

Run: `pnpm --filter=web test -- tests/wiki/wiki-home-model.test.ts tests/wiki/workspace-page-scope.test.ts`

Expected: PASS.

Run: `pnpm --filter=web check:types`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/core/components/wiki/home.tsx apps/web/core/components/wiki/header.tsx apps/web/app/'(all)'/wiki/'[workspaceSlug]' apps/web/app/'(all)'/'[workspaceSlug]'/'(projects)'/wiki/'(detail)'/'[pageId]'/page.tsx apps/web/core/components/home/widgets/recents/page.tsx apps/web/tests/wiki/wiki-home-model.test.ts
git commit -m "feat(wiki): add workspace Home and canonical page view"
```

### Task 9: Integrate aggregate Wiki search and remove the duplicate Wiki search control

**Files:**

- Modify: `apps/web/core/components/power-k/ui/modal/search-menu.tsx:23-116`
- Modify: `apps/web/core/components/power-k/ui/modal/search-results.tsx:17-70`
- Modify: `apps/web/core/components/power-k/ui/modal/search-results-map.tsx:19-116`
- Delete: `apps/web/core/components/pages/list/wiki-global-search-trigger.tsx`
- Modify: `apps/web/app/(all)/[workspaceSlug]/(projects)/wiki/(list)/header.tsx:19-93`
- Modify: `apps/web/app/(all)/company-wiki/(list)/header.tsx:19-88`
- Modify: `apps/api/plane/app/views/search/base.py:169-213`
- Create: `apps/web/tests/wiki/wiki-search-map.test.ts`
- Add tests: `apps/api/plane/tests/contract/app/test_unified_wiki_search_app.py`

**Interfaces:**

- Consumes: `WikiService.search(query, limit)`
- Produces: Wiki search result group labeled with workspace names
- Preserves: existing Work/project Power-K search behavior

- [ ] **Step 1: Add failing frontend mapping tests**

Test that `isWikiPath("/wiki/home/page-1")` selects aggregate search, that a result for workspace `mkt` maps to `/wiki/mkt/page-1`, and that ordinary project Page results retain their project route outside the Wiki app.

- [ ] **Step 2: Add a failing backend regression test for workspace global search**

Add a test proving `/api/workspaces/mkt/search/?search=Handbook&workspace_search=true` returns a visible Workspace Wiki page whose `project_ids` is empty. This reproduces the current bug where `filter_pages` requires a `ProjectPage` membership join.

- [ ] **Step 3: Run both tests and confirm RED**

Run: `pnpm --filter=web test -- tests/wiki/wiki-search-map.test.ts`

Expected: FAIL because Wiki-aware result mapping does not exist.

Run: `docker compose -f docker-compose-test.yml run --rm api-tests pytest plane/tests/contract/app/test_unified_wiki_search_app.py -q`

Expected: the workspace global-search regression test FAILS because the Wiki page is absent.

- [ ] **Step 4: Implement search switching and secure workspace search**

In Power-K, detect `/wiki/` and call `WikiService.search`; render a Pages group whose secondary text is `workspace_name` and whose route is `getWikiPagePath(workspace_slug, page_id)`. Retain the existing `WorkspaceService.searchWorkspace` path everywhere else.

Update `GlobalSearchEndpoint.filter_pages` to OR the existing project-page filter with the workspace Wiki visibility filter already used by entity search. Reuse `searchable_page_q`, `hidden_page_ids`, and active membership checks; return empty `project_ids` and `project_identifiers` for Workspace Wiki results.

Remove `WikiGlobalSearchTrigger` imports/usages and delete the file. Do not add another search box to the Wiki shell.

- [ ] **Step 5: Run frontend and backend search tests**

Run: `pnpm --filter=web test -- tests/wiki/wiki-search-map.test.ts`

Expected: PASS.

Run: `docker compose -f docker-compose-test.yml run --rm api-tests pytest plane/tests/contract/app/test_unified_wiki_search_app.py plane/tests/contract/app/test_workspace_page_app.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/core/components/power-k apps/web/app/'(all)'/'[workspaceSlug]'/'(projects)'/wiki/'(list)'/header.tsx apps/web/app/'(all)'/company-wiki/'(list)'/header.tsx apps/web/tests/wiki/wiki-search-map.test.ts apps/api/plane/app/views/search/base.py apps/api/plane/tests/contract/app/test_unified_wiki_search_app.py
git rm apps/web/core/components/pages/list/wiki-global-search-trigger.tsx
git commit -m "fix(wiki): unify search across authorized scopes"
```

### Task 10: Convert legacy surfaces, update normative docs, and run acceptance gates

**Files:**

- Modify: `apps/web/app/(all)/[workspaceSlug]/(projects)/wiki/(list)/page.tsx`
- Modify: `apps/web/app/(all)/[workspaceSlug]/(projects)/wiki/(detail)/[pageId]/page.tsx`
- Modify: `apps/web/app/(all)/company-wiki/(list)/page.tsx`
- Modify: `apps/web/app/(all)/company-wiki/(detail)/[pageId]/page.tsx`
- Delete when unreferenced: old Wiki list/detail layouts and headers under those route folders
- Modify: `docs/wiki-ce-spec.md`
- Modify: `docs/wiki-ce-implementation-plan.md`
- Modify: `docs/superpowers/specs/2026-09-23-unified-wiki-app-design.md` only if implementation reveals a reviewed constraint that must be recorded

**Interfaces:**

- Consumes: canonical redirect and page-view interfaces from Tasks 1, 6, and 8
- Produces: no live non-canonical Wiki UI routes

- [ ] **Step 1: Convert remaining old route files to redirects and remove dead components**

Ensure the route graph no longer mounts old list/detail layouts. Keep only the compatibility route component registered in Task 6. Use `rg` to prove there are no live imports of `WikiPagesListRoot`, `CompanyWikiRouteScope`, or `WikiGlobalSearchTrigger`; remove files only when unreferenced by project Pages or other surfaces.

Run: `rg -n "CompanyWikiRouteScope|WikiGlobalSearchTrigger|WikiPagesListRoot" apps/web`

Expected: no `CompanyWikiRouteScope` or `WikiGlobalSearchTrigger` references; `WikiPagesListRoot` is absent or used only by a deliberately retained non-canonical component documented in the commit.

- [ ] **Step 2: Update Wiki documentation**

Change `docs/wiki-ce-spec.md` and `docs/wiki-ce-implementation-plan.md` so `/wiki/:workspaceSlug` is normative, the configured default workspace is labeled Instance Wiki, `/company-wiki` is a redirect only, app rail contains Work and Wiki, search is aggregated, and AI sidecar is excluded.

- [ ] **Step 3: Run focused automated suites**

Run:

```bash
pnpm --filter=web test
pnpm --filter=web check:format
pnpm --filter=web check:lint
pnpm --filter=web check:types
pnpm --filter=web build
docker compose -f docker-compose-test.yml run --rm api-tests pytest \
  plane/tests/contract/app/test_unified_wiki_search_app.py \
  plane/tests/contract/app/test_workspace_page_app.py \
  plane/tests/contract/app/test_page_collection_app.py \
  plane/tests/contract/app/test_page_share_app.py \
  plane/tests/contract/app/test_page_comment_moderation_app.py -q
```

Expected: all commands PASS. Report focused green tests separately from any unrelated full-suite failures.

- [ ] **Step 4: Run manual desktop acceptance at 1168x854**

Using `http://localhost:3000/test/wiki/` as the legacy entry:

1. Verify replace redirect to `/wiki/{defaultSlug}` and Home is selected.
2. Verify app rail contains Work and Wiki, while Work sidebar contains neither Wiki nor Company Wiki.
3. Expand two ACL-visible workspaces and confirm both trees remain loaded.
4. Open pages in both scopes and verify canonical URLs, correct content, comments, and realtime sync.
5. Search a Wiki title and content phrase; verify workspace labels and canonical result links.
6. Verify unauthorized/private collection content is absent.
7. Return to Work and verify the previously active Work workspace is restored.

- [ ] **Step 5: Run mobile acceptance**

At a 390x844 viewport, verify the Wiki sidebar is a drawer, focus returns to its trigger on close, selecting a page closes the drawer, and editor/Home content uses the full width.

- [ ] **Step 6: Commit final integration and docs**

```bash
git add apps/web docs/wiki-ce-spec.md docs/wiki-ce-implementation-plan.md docs/superpowers/specs/2026-09-23-unified-wiki-app-design.md
git commit -m "docs(wiki): finalize unified app migration"
```

## Final Verification

- [ ] `git status --short` shows no unintended files.
- [ ] `git diff --check HEAD~10..HEAD` reports no whitespace errors.
- [ ] Every new behavior was introduced after its focused test failed for the expected reason.
- [ ] Backend ACL tests cover default open-read, membership, owner-private, direct share, private collection, archived, deleted, and unauthorized cross-workspace cases.
- [ ] The old Wiki search trigger and duplicate Work-sidebar entries are absent.
- [ ] `/wiki`, `/wiki/:workspaceSlug`, `/wiki/:workspaceSlug/:pageId`, `/company-wiki/*`, and `/:workspaceSlug/wiki/*` all satisfy the approved routing contract.
- [ ] No AI sidecar or fake AI conversation UI was added.
