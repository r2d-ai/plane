import { afterEach, expect, test, vi } from "vitest";
import { observable, runInAction } from "mobx";

import type { TPage } from "@plane/types";
import { EPageAccess } from "@plane/constants";

import { WorkspacePageService } from "@/services/page";
import type { CoreRootStore, RootStore } from "@/store/root.store";
import { WorkspacePage } from "@/store/pages/workspace-page";
import { WorkspacePageStore } from "@/store/pages/workspace-page.store";

const homePage = { id: "home-page", name: "Handbook" } as unknown as TPage;
const mktPage = { id: "mkt-page", name: "Campaign" } as unknown as TPage;

type TDeferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

/** A promise whose resolution the test controls, for modeling in-flight responses. */
const createDeferred = <T>(): TDeferred<T> => {
  const deferred = {} as TDeferred<T>;
  deferred.promise = new Promise<T>((resolve) => {
    deferred.resolve = resolve;
  });
  return deferred;
};

/**
 * Minimal fake root store: only the collaborators the page entity and the
 * workspace page store touch (router scope, user, favorites). The router slug
 * is observable so the store's router reaction tracks it like the real store.
 */
const createFakeRootStore = (initialWorkspaceSlug: string) => {
  const router = observable({ workspaceSlug: initialWorkspaceSlug });
  const favorite = {
    entityMap: {} as Record<string, unknown>,
    addFavorite: vi.fn(async (_workspaceSlug: string, _data: unknown) => ({})),
    removeFavoriteEntity: vi.fn(async (_workspaceSlug: string, _entityId: string) => undefined),
    removeFavoriteFromStore: vi.fn((_entityId: string) => undefined),
  };
  const root = {
    router,
    user: {
      data: { id: "user-1" },
      permission: { getWorkspaceRoleByWorkspaceSlug: (_workspaceSlug: string) => undefined },
    },
    favorite,
  };
  return {
    root,
    favorite,
    setWorkspaceSlug: (workspaceSlug: string) =>
      runInAction(() => {
        router.workspaceSlug = workspaceSlug;
      }),
  };
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("page mutations bind to the source workspace slug, not the router scope", async () => {
  vi.useFakeTimers();
  const updateSpy = vi.spyOn(WorkspacePageService.prototype, "update").mockResolvedValue({} as TPage);
  const { root, setWorkspaceSlug } = createFakeRootStore("home");

  // the entity is created while the route is in the wrong scope for it
  setWorkspaceSlug("mkt");
  const page = new WorkspacePage(root as unknown as RootStore, homePage, "home");
  // the router keeps moving afterwards; the entity must stay bound to "home"
  setWorkspaceSlug("ops");

  await page.update({ name: "Updated" });
  // BasePage.update forwards the pre-mutation page snapshot, not the patch
  expect(updateSpy).toHaveBeenNthCalledWith(1, "home", "home-page", expect.anything());
  // the rename then syncs through the debounced title reaction as exactly { name }
  await vi.advanceTimersByTimeAsync(2000);
  expect(updateSpy).toHaveBeenNthCalledWith(2, "home", "home-page", { name: "Updated" });

  page.cleanup();
});

test("activateScope clears stale active data before the new scope resolves", async () => {
  const mktResponse = createDeferred<TPage[]>();
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockImplementation(async (workspaceSlug) => {
    if (workspaceSlug === "home") return [homePage];
    return await mktResponse.promise;
  });
  const { root } = createFakeRootStore("mkt");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  await store.fetchPagesList("home");
  expect(store.getPageById("home-page")).toBeDefined();

  store.updateFilters("searchQuery", "handbook");
  store.activateScope("mkt");
  const mktFetch = store.fetchPagesList("mkt");
  // stale data and filters are gone before the mkt response resolves
  expect(store.getPageById("home-page")).toBeUndefined();
  expect(store.filters.searchQuery).toBe("");
  expect(store.activeWorkspaceSlug).toBe("mkt");

  mktResponse.resolve([mktPage]);
  await mktFetch;
  expect(store.getPageById("mkt-page")).toBeDefined();
});

test("ignores a late response for a scope that is no longer active", async () => {
  const homeResponse = createDeferred<TPage[]>();
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockImplementation(async (workspaceSlug) => {
    if (workspaceSlug === "home") return await homeResponse.promise;
    return [mktPage];
  });
  const { root } = createFakeRootStore("mkt");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  const homeFetch = store.fetchPagesList("home");
  store.activateScope("mkt");
  await store.fetchPagesList("mkt");
  homeResponse.resolve([homePage]);
  await homeFetch;

  expect(store.getPageById("home-page")).toBeUndefined();
  expect(store.getPageById("mkt-page")).toBeDefined();
});

test("favorite mutations use the page's source workspace, not the router scope", async () => {
  const { root, favorite, setWorkspaceSlug } = createFakeRootStore("home");
  setWorkspaceSlug("mkt");
  const page = new WorkspacePage(root as unknown as RootStore, homePage, "home");

  await page.addToFavorites();
  expect(favorite.addFavorite).toHaveBeenCalledWith(
    "home",
    expect.objectContaining({ entity_type: "page", entity_identifier: "home-page" })
  );

  await page.removePageFromFavorites();
  expect(favorite.removeFavoriteEntity).toHaveBeenCalledWith("home", "home-page");

  page.cleanup();
});

test("store page mutations target the active scope, not the router scope", async () => {
  const createdPage = { id: "new-page", name: "New" } as unknown as TPage;
  const createSpy = vi.spyOn(WorkspacePageService.prototype, "create").mockResolvedValue(createdPage);
  const moveSpy = vi.spyOn(WorkspacePageService.prototype, "move").mockResolvedValue({} as TPage);
  const removeSpy = vi.spyOn(WorkspacePageService.prototype, "remove").mockResolvedValue();
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockResolvedValue([homePage]);
  const { root, setWorkspaceSlug } = createFakeRootStore("mkt");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  store.activateScope("home");
  await store.fetchPagesList("home");
  setWorkspaceSlug("mkt");

  await store.createPage({ name: "New" });
  expect(createSpy).toHaveBeenCalledWith("home", { name: "New" });

  await store.movePage({ pageId: "home-page", newParentId: null });
  expect(moveSpy).toHaveBeenCalledWith("home", "home-page", { parent: null });

  await store.removePage({ pageId: "home-page" });
  expect(removeSpy).toHaveBeenCalledWith("home", "home-page");
});

test("store removePage and movePage use the entity's source slug when active scope and router point elsewhere", async () => {
  const moveSpy = vi.spyOn(WorkspacePageService.prototype, "move").mockResolvedValue({} as TPage);
  const removeSpy = vi.spyOn(WorkspacePageService.prototype, "remove").mockResolvedValue();
  const { root, setWorkspaceSlug } = createFakeRootStore("home");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  // a "home" entity can outlive a scope switch (e.g. a create response that
  // lands after the store moved on): seed it while the active scope is "mkt"
  store.activateScope("mkt");
  runInAction(() => {
    store.data["home-page"] = new WorkspacePage(root as unknown as RootStore, homePage, "home");
  });
  setWorkspaceSlug("ops");

  await store.movePage({ pageId: "home-page", newParentId: null });
  expect(moveSpy).toHaveBeenCalledWith("home", "home-page", { parent: null });

  await store.removePage({ pageId: "home-page" });
  expect(removeSpy).toHaveBeenCalledWith("home", "home-page");
});

test("a fetch for another scope implicitly activates it and delivers its response", async () => {
  const mktResponse = createDeferred<TPage[]>();
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockImplementation(async (workspaceSlug) => {
    if (workspaceSlug === "home") return [homePage];
    return await mktResponse.promise;
  });
  const { root } = createFakeRootStore("home");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  await store.fetchPagesList("home");
  store.updateFilters("searchQuery", "handbook");

  // no explicit activateScope: the fetch itself switches the scope
  const mktFetch = store.fetchPagesList("mkt");
  expect(store.activeWorkspaceSlug).toBe("mkt");
  expect(store.getPageById("home-page")).toBeUndefined();
  expect(store.filters.searchQuery).toBe("");

  mktResponse.resolve([mktPage]);
  await mktFetch;
  expect(store.getPageById("mkt-page")).toBeDefined();
});

test("a mid-flight scope switch leaves state owned by the new scope", async () => {
  const homeResponse = createDeferred<TPage[]>();
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockImplementation(async (workspaceSlug) => {
    if (workspaceSlug === "home") return await homeResponse.promise;
    return [mktPage];
  });
  const { root, setWorkspaceSlug } = createFakeRootStore("home");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  setWorkspaceSlug("mkt");
  const homeFetch = store.fetchPagesList("home");
  // the user switches scope mid-flight; the switch is itself a fetch
  await store.fetchPagesList("mkt");
  homeResponse.resolve([homePage]);
  await homeFetch;

  expect(store.activeWorkspaceSlug).toBe("mkt");
  expect(store.getPageById("mkt-page")).toBeDefined();
  expect(store.getPageById("home-page")).toBeUndefined();
  // the ignored response must not leave the active scope stuck loading
  expect(store.loader).toBeUndefined();
});

test("a same-scope refetch keeps existing data and the user's search query", async () => {
  vi.spyOn(WorkspacePageService.prototype, "fetchAll").mockResolvedValue([homePage]);
  const { root } = createFakeRootStore("home");
  const store = new WorkspacePageStore(root as unknown as CoreRootStore);

  await store.fetchPagesList("home");
  store.updateFilters("searchQuery", "handbook");

  await store.fetchPagesList("home");

  expect(store.activeWorkspaceSlug).toBe("home");
  expect(store.getPageById("home-page")).toBeDefined();
  expect(store.filters.searchQuery).toBe("handbook");
});

test("workspace page links use the canonical Wiki route", () => {
  const { root } = createFakeRootStore("mkt");
  const page = new WorkspacePage(root as unknown as RootStore, mktPage, "mkt");
  expect(page.getRedirectionLink()).toBe("/wiki/mkt/mkt-page");
  page.cleanup();
});

test("a server-returned private shared page is readable without an edit role", () => {
  const { root } = createFakeRootStore("mkt");
  const shared = new WorkspacePage(
    root as unknown as RootStore,
    { ...mktPage, access: EPageAccess.PRIVATE, owned_by: "owner-2" },
    "mkt"
  );
  expect(shared.canCurrentUserAccessPage).toBe(true);
  expect(shared.canCurrentUserEditPage).toBe(false);
  shared.cleanup();
});
