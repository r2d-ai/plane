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
 * of a 404.
 *
 * RD-483 deleted the builder surface, but kept this redirect: the alternative
 * is a 404 for every link anyone ever saved, which is strictly worse than a
 * route that quietly lands on the one dashboard that now exists. The route
 * goes when the bookmark tail is judged dead, which is a product call.
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
