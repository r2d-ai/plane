import { describe, expect, test } from "vitest";
import type { RouteConfigEntry } from "@react-router/dev/routes";
import { GROUPED_WORKSPACE_SETTINGS } from "@plane/constants";
import { coreRoutes } from "../../app/routes/core";

const paths = (routes: RouteConfigEntry[]): string[] =>
  routes.flatMap((route) => [route.path, ...paths(route.children ?? [])].filter((path): path is string => !!path));

describe("Workspace settings", () => {
  test("does not expose Plane billing in navigation or routes", () => {
    expect(
      Object.values(GROUPED_WORKSPACE_SETTINGS)
        .flat()
        .map((item) => item.key)
    ).not.toContain("billing-and-plans");
    expect(paths(coreRoutes)).not.toContain(":workspaceSlug/settings/billing");
  });
});
