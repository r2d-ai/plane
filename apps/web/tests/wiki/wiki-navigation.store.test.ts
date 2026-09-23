import { expect, test } from "vitest";

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
