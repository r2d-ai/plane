/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { layout, route } from "@react-router/dev/routes";
import type { RouteConfigEntry } from "@react-router/dev/routes";

export const workspaceDashboardRoutePaths = [
  ":workspaceSlug/dashboards",
  ":workspaceSlug/dashboards/:dashboardId",
] as const;

/** Workspace dashboards (§6, §7) — gated at runtime via dashboards layout clientLoader. */
export const workspaceDashboardRoutes: RouteConfigEntry[] = [
  layout("./(all)/[workspaceSlug]/(projects)/dashboards/layout.tsx", [
    route(":workspaceSlug/dashboards", "./(all)/[workspaceSlug]/(projects)/dashboards/page.tsx"),
    route(
      ":workspaceSlug/dashboards/:dashboardId",
      "./(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/page.tsx"
    ),
  ]),
];
