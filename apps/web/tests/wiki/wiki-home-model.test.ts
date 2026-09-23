import { describe, expect, test } from "vitest";
import { buildWikiHomeModel } from "../../core/components/wiki/home-model";
import type { TActivityEntityData, TPage, TPageCollection, TWikiScope } from "@plane/types";

const scope: TWikiScope = {
  id: "1",
  slug: "mkt",
  name: "Marketing",
  is_default: false,
  is_member: true,
  can_create: true,
};
const page = (id: string, workspace: string, favorite = false): TPage =>
  ({ id, workspace, name: id, is_favorite: favorite }) as TPage;
const collection = (id: string, sort_order: number): TPageCollection =>
  ({ id, name: id, sort_order }) as TPageCollection;
const recent = (id: string): TActivityEntityData =>
  ({
    id,
    entity_name: "workspace_page",
    entity_identifier: id,
    entity_data: { id, name: id },
    visited_at: "2026-09-24",
  }) as TActivityEntityData;

describe("Wiki Home model", () => {
  test("filters recents and favorites to the selected workspace", () => {
    const model = buildWikiHomeModel({
      scope,
      pages: [page("a", "1", true), page("b", "2", true)],
      collections: [],
      recents: [recent("a"), recent("b")],
    });
    expect(model.favorites.map((item) => item.id)).toEqual(["a"]);
    expect(model.recents.map((item) => item.entity_identifier)).toEqual(["a"]);
  });

  test("sorts collections and gates creation", () => {
    const model = buildWikiHomeModel({
      scope: { ...scope, can_create: false },
      pages: [],
      collections: [collection("late", 3), collection("early", 1)],
      recents: [],
    });
    expect(model.collections.map((item) => item.id)).toEqual(["early", "late"]);
    expect(model.canCreate).toBe(false);
  });

  test("shows empty state only when no selected-scope content is visible", () => {
    expect(buildWikiHomeModel({ scope, pages: [], collections: [], recents: [] }).isEmpty).toBe(true);
    expect(buildWikiHomeModel({ scope, pages: [page("a", "1")], collections: [], recents: [] }).isEmpty).toBe(false);
  });
});
