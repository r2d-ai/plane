import type { IInstanceConfig } from "@plane/types";

/**
 * Instance kill-switch for workspace dashboards (WORKSPACE_DASHBOARDS).
 * Fail closed when config is missing or the flag is unset.
 */
export const isWorkspaceDashboardsEnabled = (config?: IInstanceConfig | null): boolean =>
  config?.is_workspace_dashboards_enabled === true;
