/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PageHead } from "@/components/core/page-title";
import { WorkspaceDashboardDetailRoot } from "@/components/dashboards/detail/dashboard-detail-root";
import type { Route } from "./+types/page";

function WorkspaceDashboardDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, dashboardId } = params;

  return (
    <>
      <PageHead title="Dashboard" />
      <div className="relative h-full w-full overflow-hidden">
        <WorkspaceDashboardDetailRoot workspaceSlug={workspaceSlug} dashboardId={dashboardId} />
      </div>
    </>
  );
}

export default WorkspaceDashboardDetailPage;
