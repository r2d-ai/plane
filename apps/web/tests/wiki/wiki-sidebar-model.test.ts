import { describe, expect, test, vi } from "vitest";
import { buildWikiSidebarModel, expandWikiWorkspace } from "../../core/components/wiki/sidebar/model";
import { WikiNavigationStore } from "../../core/store/wiki/wiki-navigation.store";

const scopes = [
  { id: "1", slug: "home", name: "Home", is_default: true, is_member: false, can_create: false },
  { id: "2", slug: "mkt", name: "Marketing", is_default: false, is_member: true, can_create: true },
];

describe("Wiki sidebar model", () => {
  test("places the default workspace first and labels it with the workspace name", () => {
    const model = buildWikiSidebarModel(scopes, "home", "mkt", "page-1");
    expect(model.defaultScope?.label).toBe("Home");
    expect(model.defaultScope?.href).toBe("/wiki/home");
    expect(model.workspaces.map((scope) => scope.slug)).toEqual(["mkt"]);
    expect(model.workspaces[0].active).toBe(true);
    expect(model.pageHref("mkt", "page-1")).toBe("/wiki/mkt/page-1");
  });

  test("contains only server-returned scopes", () => {
    const model = buildWikiSidebarModel(scopes, "home", "finance");
    expect(model.workspaces.find((scope) => scope.slug === "finance")).toBeUndefined();
  });

  test("expanding a workspace loads it once without clearing another scope", async () => {
    const fetchAll = vi.fn(async (_slug: string) => []);
    const store = new WikiNavigationStore({
      pageService: { fetchAll },
      collectionService: { fetchAll: async () => [], fetchPages: async () => [] },
    });
    await store.fetchScope("home");
    await expandWikiWorkspace(store, "mkt");
    await expandWikiWorkspace(store, "mkt");
    expect(fetchAll.mock.calls.map(([slug]) => slug)).toEqual(["home", "mkt"]);
    expect(store.getScope("home").status).toBe("loaded");
  });
});
