/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { loadWorkspaceDashboardsRouteGuard } from "@/helpers/workspace-dashboards-route-guard";
import type { Route } from "./+types/layout";
import { WorkspaceDashboardsHeader } from "./header";

/**
 * One gate in front of both dashboard routes (spec §22, §14.1): the flag must
 * be on and the viewer must be a member of the workspace. Because the guard
 * lives in the layout, the legacy `/:dashboardId` redirect below it is
 * unreachable for a viewer who is not allowed to be here at all.
 */
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  return loadWorkspaceDashboardsRouteGuard({ workspaceSlug: params.workspaceSlug });
}

export default function WorkspaceDashboardsLayout() {
  return (
    <>
      <AppHeader header={<WorkspaceDashboardsHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
