import { redirect } from "react-router";
import type { IInstanceConfig } from "@plane/types";
import { isWorkspaceDashboardsEnabled } from "@/helpers/workspace-dashboards-access";
import { InstanceService } from "@/services/instance.service";

const instanceService = new InstanceService();

/** Used by dashboards layout clientLoader; exported for tests. */
export const resolveWorkspaceDashboardsRouteAccess = (config?: IInstanceConfig | null): void => {
  if (!isWorkspaceDashboardsEnabled(config)) {
    throw redirect("/__workspace_dashboards_disabled__");
  }
};

export const loadWorkspaceDashboardsRouteGuard = async (): Promise<null> => {
  const { config } = await instanceService.getInstanceInfo();
  resolveWorkspaceDashboardsRouteAccess(config);
  return null;
};
