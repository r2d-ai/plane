import { describe, expect, test } from "vitest";
import type { RouteConfigEntry } from "@react-router/dev/routes";
import { coreRoutes } from "../../app/routes/core";
import { extendedRoutes } from "../../app/routes/extended";
import { mergeRoutes } from "../../app/routes/helper";

const collectPaths = (routes: RouteConfigEntry[]): string[] =>
  routes.flatMap((route) =>
    [route.path, ...collectPaths(route.children ?? [])].filter((path): path is string => !!path)
  );

describe("Wiki route registration", () => {
  test("keeps every legacy redirect after route merging", () => {
    const paths = collectPaths(mergeRoutes(coreRoutes, extendedRoutes));
    expect(paths).toEqual(
      expect.arrayContaining([
        "wiki/personal/:section",
        "company-wiki",
        "company-wiki/:pageId",
        ":workspaceSlug/wiki",
        ":workspaceSlug/wiki/:pageId",
      ])
    );
  });
});
