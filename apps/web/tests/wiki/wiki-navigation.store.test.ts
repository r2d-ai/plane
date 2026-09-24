import { expect, test, vi } from "vitest";

import type { TPage, TPageCollection } from "@plane/types";

import { WikiNavigationStore } from "@/store/wiki/wiki-navigation.store";

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

test("refetching a loaded scope applies the fresh list without hiding the old one", async () => {
  let calls = 0;
  const store = new WikiNavigationStore({
    pageService: {
      fetchAll: async () => {
        calls += 1;
        return calls === 1 ? ([{ id: "first" }] as TPage[]) : ([{ id: "second" }] as TPage[]);
      },
    },
    collectionService: { fetchAll: async () => [], fetchPages: async () => [] },
  });

  await store.fetchScope("home");
  const refresh = store.fetchScope("home");
  // a silent refresh keeps the loaded snapshot visible instead of flashing
  expect(store.getScope("home").status).toBe("loaded");
  await refresh;

  expect(calls).toBe(2);
  expect(store.getScope("home").pageIds).toEqual(["second"]);
  expect(store.getScope("home").status).toBe("loaded");
});

test("invalidating a loaded scope silently refreshes it", async () => {
  let calls = 0;
  const store = new WikiNavigationStore({
    pageService: {
      fetchAll: async () => {
        calls += 1;
        return calls === 1 ? ([{ id: "old-page" }] as TPage[]) : ([{ id: "new-page" }] as TPage[]);
      },
    },
    collectionService: { fetchAll: async () => [], fetchPages: async () => [] },
  });

  await store.fetchScope("home");
  await store.invalidateScope("home");

  expect(store.getScope("home").pageIds).toEqual(["new-page"]);
  expect(store.getScope("home").status).toBe("loaded");
});

test("invalidating a scope that was never loaded does nothing", async () => {
  const fetchAll = vi.fn(async () => [] as TPage[]);
  const store = new WikiNavigationStore({
    pageService: { fetchAll },
    collectionService: { fetchAll: async () => [], fetchPages: async () => [] },
  });

  await store.invalidateScope("home");

  expect(fetchAll).not.toHaveBeenCalled();
  expect(store.getScope("home").status).toBe("idle");
});
