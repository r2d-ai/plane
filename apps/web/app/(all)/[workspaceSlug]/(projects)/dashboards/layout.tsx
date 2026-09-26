/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { loadWorkspaceDashboardsRouteGuard } from "@/helpers/workspace-dashboards-route-guard";
import { WorkspaceDashboardsHeader } from "./header";

export async function clientLoader() {
  return loadWorkspaceDashboardsRouteGuard();
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
