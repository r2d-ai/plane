import { describe, expect, test } from "vitest";
import type { RouteConfigEntry } from "@react-router/dev/routes";
import { coreRoutes } from "../../app/routes/core";
import { workspaceDashboardRoutePaths } from "../../app/routes/workspace-dashboards";
import { isWorkspaceDashboardsEnabled } from "@/helpers/workspace-dashboards-access";
import { resolveWorkspaceDashboardsRouteAccess } from "@/helpers/workspace-dashboards-route-guard";

const paths = (routes: RouteConfigEntry[]): string[] =>
  routes.flatMap((route) => [route.path, ...paths(route.children ?? [])].filter((path): path is string => !!path));

describe("workspace dashboards kill-switch", () => {
  test("isWorkspaceDashboardsEnabled fails closed when config is missing or flag unset", () => {
    expect(isWorkspaceDashboardsEnabled(undefined)).toBe(false);
    expect(isWorkspaceDashboardsEnabled(null)).toBe(false);
    expect(isWorkspaceDashboardsEnabled({} as Parameters<typeof isWorkspaceDashboardsEnabled>[0])).toBe(false);
    expect(isWorkspaceDashboardsEnabled({ is_workspace_dashboards_enabled: false })).toBe(false);
  });

  test("isWorkspaceDashboardsEnabled is true only when instance config enables the flag", () => {
    expect(isWorkspaceDashboardsEnabled({ is_workspace_dashboards_enabled: true })).toBe(true);
  });

  test("route guard redirects when dashboards are disabled", () => {
    for (const config of [undefined, { is_workspace_dashboards_enabled: false }]) {
      try {
        resolveWorkspaceDashboardsRouteAccess(config);
        expect.fail("expected redirect");
      } catch (error) {
        expect(error).toBeInstanceOf(Response);
      }
    }
  });

  test("route guard allows access when dashboards are enabled", () => {
    expect(() => resolveWorkspaceDashboardsRouteAccess({ is_workspace_dashboards_enabled: true })).not.toThrow();
  });

  test("dashboard paths stay registered but are runtime-gated via layout clientLoader", () => {
    const registered = paths(coreRoutes);
    for (const path of workspaceDashboardRoutePaths) {
      expect(registered).toContain(path);
    }
  });
});
