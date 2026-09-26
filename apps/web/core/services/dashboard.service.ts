/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TDashboardCreatePayload,
  TDashboardLayoutUpdateEntry,
  TDashboardWidgetPayload,
  TAnalyticsDrilldownResponseV2,
  THomeDashboardResponse,
  TWidget,
  TWidgetStatsResponse,
  TWidgetStatsRequestParams,
  TWorkspaceDashboard,
  TWorkspaceDashboardDetail,
  TWorkspaceDashboardWidget,
} from "@plane/types";
import { APIService } from "@/services/api.service";

export class DashboardService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  /**
   * §33 — `GET /api/workspaces/{slug}/dashboards`.
   * Backs the "Save to dashboard" picker (§18.2).
   */
  async getWorkspaceDashboards(workspaceSlug: string): Promise<TWorkspaceDashboard[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/dashboards/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkspaceDashboard(workspaceSlug: string, dashboardId: string): Promise<TWorkspaceDashboardDetail> {
    return this.get(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkspaceDashboard(
    workspaceSlug: string,
    payload: TDashboardCreatePayload
  ): Promise<TWorkspaceDashboardDetail> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkspaceDashboard(
    workspaceSlug: string,
    dashboardId: string,
    payload: Partial<TDashboardCreatePayload>
  ): Promise<TWorkspaceDashboardDetail> {
    return this.patch(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkspaceDashboard(workspaceSlug: string, dashboardId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async duplicateWorkspaceDashboard(workspaceSlug: string, dashboardId: string): Promise<TWorkspaceDashboardDetail> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/duplicate/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async favoriteWorkspaceDashboard(workspaceSlug: string, dashboardId: string): Promise<void> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/favorite/`, {})
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async unfavoriteWorkspaceDashboard(workspaceSlug: string, dashboardId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/favorite/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * §33 — `POST /api/workspaces/{slug}/dashboards/{id}/widgets`.
   * The widget stores the AnalyticsQuery V2 configuration, never a snapshot of
   * the current results (§18.2).
   */
  async createDashboardWidget(
    workspaceSlug: string,
    dashboardId: string,
    payload: TDashboardWidgetPayload
  ): Promise<TWorkspaceDashboardWidget> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkspaceDashboardWidget(
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    payload: Partial<TDashboardWidgetPayload>
  ): Promise<TWorkspaceDashboardWidget> {
    return this.patch(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/${widgetId}/`, payload)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkspaceDashboardWidget(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/${widgetId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateDashboardLayout(
    workspaceSlug: string,
    dashboardId: string,
    widgets: TDashboardLayoutUpdateEntry[]
  ): Promise<TWorkspaceDashboardWidget[]> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/layout/`, { widgets })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** §25 / §33 — widget drill-down under dashboard ACL scope. */
  async postDashboardWidgetDrilldown(
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    payload: { selection: Record<string, string | string[] | null>; page?: number; page_size?: number }
  ): Promise<TAnalyticsDrilldownResponseV2> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/${widgetId}/drilldown/`,
      payload
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getHomeDashboardWidgets(workspaceSlug: string): Promise<THomeDashboardResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/dashboard/`, {
      params: {
        dashboard_type: "home",
      },
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWidgetStats(
    workspaceSlug: string,
    dashboardId: string,
    params: TWidgetStatsRequestParams
  ): Promise<TWidgetStatsResponse> {
    return this.get(`/api/workspaces/${workspaceSlug}/dashboard/${dashboardId}/`, {
      params,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getDashboardDetails(dashboardId: string): Promise<TWidgetStatsResponse> {
    return this.get(`/api/dashboard/${dashboardId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateDashboardWidget(dashboardId: string, widgetId: string, data: Partial<TWidget>): Promise<TWidget> {
    return this.patch(`/api/dashboard/${dashboardId}/widgets/${widgetId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
