/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PageHead } from "@/components/core/page-title";
import { WorkspaceDashboardListRoot } from "@/components/dashboards/list/dashboard-list-root";
import type { Route } from "./+types/page";

function WorkspaceDashboardsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;

  return (
    <>
      <PageHead title="Dashboards" />
      <div className="relative h-full w-full overflow-hidden overflow-y-auto">
        <WorkspaceDashboardListRoot workspaceSlug={workspaceSlug} />
      </div>
    </>
  );
}

export default WorkspaceDashboardsPage;
