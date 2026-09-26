/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * RD-482 / C.11 — the v3 route guard.
 *
 * Two refusals, both fail-closed: the instance flag (§22) and workspace access
 * (§14.1 — the dashboard has no ACL of its own, so membership *is* the gate).
 * The companion kill-switch suite still covers the flag half on its own.
 */

import type { IInstanceConfig, IWorkspaceMemberMe } from "@plane/types";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("react-router", () => ({
  redirect: (url: string) => new Response(null, { status: 302, headers: { Location: url } }),
}));

const instanceConfig = vi.hoisted(() => ({ value: undefined as unknown }));
const membership = vi.hoisted(() => ({ value: "unset" as unknown }));

vi.mock("@/services/instance.service", () => ({
  InstanceService: class {
    getInstanceInfo = async () => ({ config: instanceConfig.value });
  },
}));

vi.mock("@/services/workspace.service", () => ({
  WorkspaceService: class {
    workspaceMemberMe = async () => {
      if (membership.value === "reject") throw new Error("network down");
      return membership.value;
    };
  },
}));

import {
  WORKSPACE_DASHBOARDS_DISABLED_PATH,
  WORKSPACE_DASHBOARDS_FORBIDDEN_PATH,
  hasWorkspaceDashboardAccess,
  loadWorkspaceDashboardsRouteGuard,
  resolveWorkspaceDashboardViewerAccess,
} from "@/helpers/workspace-dashboards-route-guard";

/** Only the flag matters to the guard, so the rest of the instance config is noise. */
const config = (is_workspace_dashboards_enabled: boolean) =>
  ({ is_workspace_dashboards_enabled }) as unknown as IInstanceConfig;
const member = { id: "member-1", role: 20 } as unknown as IWorkspaceMemberMe;

const redirectTo = (run: () => unknown): string => {
  try {
    run();
    expect.fail("expected redirect");
  } catch (error) {
    if (!(error instanceof Response)) throw error;
    return error.headers.get("Location") ?? "";
  }
  return "";
};

const redirectToFrom = async (run: () => Promise<unknown>): Promise<string> => {
  try {
    await run();
    expect.fail("expected redirect");
  } catch (error) {
    if (!(error instanceof Response)) throw error;
    return error.headers.get("Location") ?? "";
  }
  return "";
};

beforeEach(() => {
  instanceConfig.value = config(true);
  membership.value = member;
});

describe("workspace dashboard v3 route guard", () => {
  test("§22 — the flag alone still decides availability", () => {
    expect(redirectTo(() => resolveWorkspaceDashboardViewerAccess(config(false), member))).toBe(
      WORKSPACE_DASHBOARDS_DISABLED_PATH
    );
    expect(redirectTo(() => resolveWorkspaceDashboardViewerAccess(undefined, member))).toBe(
      WORKSPACE_DASHBOARDS_DISABLED_PATH
    );
    expect(() => resolveWorkspaceDashboardViewerAccess(config(true), member)).not.toThrow();
  });

  test("§14.1 — a viewer without workspace access is refused", () => {
    expect(redirectTo(() => resolveWorkspaceDashboardViewerAccess(config(true), null))).toBe(
      WORKSPACE_DASHBOARDS_FORBIDDEN_PATH
    );
    expect(redirectTo(() => resolveWorkspaceDashboardViewerAccess(config(true), undefined))).toBe(
      WORKSPACE_DASHBOARDS_FORBIDDEN_PATH
    );
  });

  test("fail closed — an unresolvable membership is a refusal, never a pass", () => {
    expect(hasWorkspaceDashboardAccess(null)).toBe(false);
    expect(hasWorkspaceDashboardAccess(undefined)).toBe(false);
    expect(hasWorkspaceDashboardAccess({} as IWorkspaceMemberMe)).toBe(false);
    expect(hasWorkspaceDashboardAccess(member)).toBe(true);
    expect(redirectTo(() => resolveWorkspaceDashboardViewerAccess(config(true), {} as IWorkspaceMemberMe))).toBe(
      WORKSPACE_DASHBOARDS_FORBIDDEN_PATH
    );
  });

  test("the loader refuses a non-member before the dashboard renders", async () => {
    membership.value = null;
    expect(await redirectToFrom(() => loadWorkspaceDashboardsRouteGuard({ workspaceSlug: "acme" }))).toBe(
      WORKSPACE_DASHBOARDS_FORBIDDEN_PATH
    );
  });

  test("the loader refuses when the membership probe itself fails", async () => {
    membership.value = "reject";
    expect(await redirectToFrom(() => loadWorkspaceDashboardsRouteGuard({ workspaceSlug: "acme" }))).toBe(
      WORKSPACE_DASHBOARDS_FORBIDDEN_PATH
    );
  });

  test("the loader refuses a flag-off instance and never reaches the ACL half", async () => {
    instanceConfig.value = config(false);
    membership.value = member;
    expect(await redirectToFrom(() => loadWorkspaceDashboardsRouteGuard({ workspaceSlug: "acme" }))).toBe(
      WORKSPACE_DASHBOARDS_DISABLED_PATH
    );
  });

  test("the loader lets a member through on a flag-on instance", async () => {
    expect(await loadWorkspaceDashboardsRouteGuard({ workspaceSlug: "acme" })).toBeNull();
    // A loader call with no slug cannot prove membership, so it refuses too.
    expect(await redirectToFrom(() => loadWorkspaceDashboardsRouteGuard())).toBe(WORKSPACE_DASHBOARDS_FORBIDDEN_PATH);
  });
});
