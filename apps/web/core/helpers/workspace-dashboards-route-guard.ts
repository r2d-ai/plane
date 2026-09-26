/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { redirect } from "react-router";
import type { IInstanceConfig, IWorkspaceMemberMe } from "@plane/types";
import { isWorkspaceDashboardsEnabled } from "@/helpers/workspace-dashboards-access";
import { InstanceService } from "@/services/instance.service";
import { WorkspaceService } from "@/services/workspace.service";

const instanceService = new InstanceService();
const workspaceService = new WorkspaceService();

/** Where a viewer lands when WORKSPACE_DASHBOARDS is off (spec §22, fail-closed). */
export const WORKSPACE_DASHBOARDS_DISABLED_PATH = "/__workspace_dashboards_disabled__";
/** Where a viewer lands when they may not see the workspace at all (spec §14.1). */
export const WORKSPACE_DASHBOARDS_FORBIDDEN_PATH = "/";

type RouteGuardArgs = { workspaceSlug?: string };

/**
 * Feature-flag half of the guard; unchanged since the kill switch landed and
 * still exported for the existing regression test.
 */
export const resolveWorkspaceDashboardsRouteAccess = (config?: IInstanceConfig | null): void => {
  if (!isWorkspaceDashboardsEnabled(config)) {
    throw redirect(WORKSPACE_DASHBOARDS_DISABLED_PATH);
  }
};

/**
 * §14.1 — the Workspace Dashboard has no sharing ACL of its own; its visibility
 * *is* workspace access. Anything that is not an active membership record is
 * refused, including a membership probe that failed, so an unreachable or
 * erroring endpoint can never open the surface.
 */
export const hasWorkspaceDashboardAccess = (membership?: IWorkspaceMemberMe | null): boolean =>
  !!membership && typeof membership.id === "string";

/** The v3 guard: flag on *and* the viewer is a member of the workspace. */
export const resolveWorkspaceDashboardViewerAccess = (
  config?: IInstanceConfig | null,
  membership?: IWorkspaceMemberMe | null
): void => {
  resolveWorkspaceDashboardsRouteAccess(config);
  if (!hasWorkspaceDashboardAccess(membership)) {
    throw redirect(WORKSPACE_DASHBOARDS_FORBIDDEN_PATH);
  }
};

export const loadWorkspaceDashboardsRouteGuard = async ({ workspaceSlug }: RouteGuardArgs = {}): Promise<null> => {
  const { config } = await instanceService.getInstanceInfo();
  // Check the flag first: a disabled instance must not spend a request on the
  // membership probe, and the disabled redirect is the correct answer there.
  resolveWorkspaceDashboardsRouteAccess(config);

  const membership = workspaceSlug ? await workspaceService.workspaceMemberMe(workspaceSlug).catch(() => null) : null;

  resolveWorkspaceDashboardViewerAccess(config, membership);
  return null;
};
