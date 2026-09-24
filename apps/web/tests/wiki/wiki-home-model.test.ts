import { describe, expect, test } from "vitest";
import { buildWikiHomeModel } from "../../core/components/wiki/home-model";
import type { TPage, TWikiScope } from "@plane/types";

const scope: TWikiScope = {
  id: "1",
  slug: "mkt",
  name: "Marketing",
  is_default: false,
  is_member: false,
  can_create: false,
};

const page = (id: string, workspace: string, updated_at: string, extra: Partial<TPage> = {}): TPage =>
  ({
    id,
    workspace,
    name: id,
    created_at: updated_at,
    updated_at,
    ...extra,
  }) as TPage;

describe("Wiki Home model", () => {
  test("returns only active pages from the selected scope, newest first", () => {
    const model = buildWikiHomeModel({
      scope,
      pages: [
        page("old", "1", "2026-09-20T00:00:00Z"),
        page("new", "1", "2026-09-24T00:00:00Z"),
        page("other", "2", "2026-09-25T00:00:00Z"),
        page("archived", "1", "2026-09-26T00:00:00Z", { archived_at: "2026-09-26" }),
      ],
    });

    expect(model.recentlyUpdated.map((item) => item.id)).toEqual(["new", "old"]);
  });

  test("caps the recently updated fallback", () => {
    const model = buildWikiHomeModel({
      scope,
      pages: [
        page("a", "1", "2026-09-24T04:00:00Z"),
        page("b", "1", "2026-09-24T03:00:00Z"),
        page("c", "1", "2026-09-24T02:00:00Z"),
      ],
      limit: 2,
    });

    expect(model.recentlyUpdated.map((item) => item.id)).toEqual(["a", "b"]);
  });

  test("sorts pages with Date timestamps", () => {
    const model = buildWikiHomeModel({
      scope,
      pages: [
        page("old", "1", "2026-09-20T00:00:00Z", { updated_at: new Date("2026-09-20T00:00:00Z") }),
        page("new", "1", "2026-09-24T00:00:00Z", { updated_at: new Date("2026-09-24T00:00:00Z") }),
      ],
    });

    expect(model.recentlyUpdated.map((item) => item.id)).toEqual(["new", "old"]);
  });
});
