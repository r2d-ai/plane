/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * FROZEN -- legacy dashboard-builder surface, scheduled for deletion in Phase D of RD-475.
 * Product spec: docs/workspace-dashboards-analytics-v2-spec.md
 * Do not add features, extend behaviour, or wire up new consumers here. The fixed
 * Workspace Dashboard replaces this surface; see RD-475 for the migration table.
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
