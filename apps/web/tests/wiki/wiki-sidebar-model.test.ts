import { describe, expect, test, vi } from "vitest";
import {
  buildWikiSidebarModel,
  expandWikiWorkspace,
  getCollectionSubtreePages,
  getCreatableWikiScopes,
  getLooseWikiPages,
} from "../../core/components/wiki/sidebar/model";
import { WikiNavigationStore } from "../../core/store/wiki/wiki-navigation.store";

const scopes = [
  {
    id: "1",
    slug: "home",
    name: "Home",
    is_default: true,
    is_member: false,
    can_create: false,
    can_manage_collections: false,
  },
  {
    id: "2",
    slug: "mkt",
    name: "Marketing",
    is_default: false,
    is_member: true,
    can_create: true,
    can_manage_collections: false,
  },
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

  test("new-page scope choices include only creatable visible scopes with the instance first", () => {
    const choices = getCreatableWikiScopes([
      { ...scopes[0], can_create: true },
      scopes[1],
      {
        id: "3",
        slug: "ops",
        name: "Operations",
        is_default: false,
        is_member: true,
        can_create: true,
        can_manage_collections: false,
      },
      {
        id: "4",
        slug: "finance",
        name: "Finance",
        is_default: false,
        is_member: false,
        can_create: true,
        can_manage_collections: false,
      },
      {
        id: "5",
        slug: "readonly",
        name: "Read only",
        is_default: false,
        is_member: true,
        can_create: false,
        can_manage_collections: false,
      },
    ]);

    expect(choices.map((scope) => scope.slug)).toEqual(["home", "mkt", "ops"]);
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

test("collection helpers keep inherited descendants out of the loose tree", () => {
  const pages = [
    { id: "root", parent: null },
    { id: "child", parent: "root" },
    { id: "loose", parent: null },
  ] as any[];
  const associations = [{ page: "root" }] as any[];

  expect(getCollectionSubtreePages(pages, associations).map((page) => page.id)).toEqual(["root", "child"]);
  expect(getLooseWikiPages(pages, { general: associations }).map((page) => page.id)).toEqual(["loose"]);
});
