/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TDashboardListTab, TWorkspaceDashboard } from "@plane/types";

export function filterDashboardsByTab(
  dashboards: TWorkspaceDashboard[],
  tab: TDashboardListTab,
  currentUserId?: string | null
): TWorkspaceDashboard[] {
  switch (tab) {
    case "mine":
      return dashboards.filter((d) => d.owner === currentUserId);
    case "shared":
      return dashboards.filter((d) => d.owner !== currentUserId && d.visibility === "workspace");
    case "favorites":
      return dashboards.filter((d) => d.is_favorited);
    case "all":
    default:
      return dashboards;
  }
}
