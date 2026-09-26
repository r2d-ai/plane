/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Legacy builder route (spec §4.1, §23.3).
 *
 * `/:workspaceSlug/dashboards/:dashboardId` addressed a user-authored
 * dashboard row. The v3 dashboard is a workspace-level view with no ids, so
 * every legacy link — saved bookmarks, a stale Slack paste, an old
 * save-insight-to-dashboard deep link — lands on the single dashboard instead
 * of a 404. The route stays registered until RD-483 removes the builder
 * surface and its links for good.
 */

import { redirect } from "react-router";
import type { Route } from "./+types/page";

export const clientLoader = ({ params }: Route.ClientLoaderArgs) => {
  const { workspaceSlug } = params;
  throw redirect(`/${workspaceSlug}/dashboards/`);
};

export default function WorkspaceDashboardDetailPage() {
  return null;
}
