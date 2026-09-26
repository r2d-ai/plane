/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The fixed Workspace Dashboard (spec §4.1, §6, §7).
 *
 * The plural URL stays — spec §4.1 allows it and it keeps existing bookmarks
 * and the sidebar link working — but the route now renders the single v3 shell
 * directly. There is no dashboard list, no builder entry point and no
 * fallback: with the feature flag off the guard in the layout sends the
 * viewer away before this module is ever reached (spec §22).
 */

import { PageHead } from "@/components/core/page-title";
import { WorkspaceDashboardShell } from "@/components/dashboards/v3/dashboard-shell";
import type { Route } from "./+types/page";

function WorkspaceDashboardsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;

  return (
    <>
      <PageHead title="Dashboard" />
      <div className="relative h-full w-full overflow-hidden">
        <WorkspaceDashboardShell workspaceSlug={workspaceSlug} />
      </div>
    </>
  );
}

export default WorkspaceDashboardsPage;
