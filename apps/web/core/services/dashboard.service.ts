/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type {
  TDashboardWidgetPayload,
  THomeDashboardResponse,
  TWidget,
  TWidgetStatsResponse,
  TWidgetStatsRequestParams,
  TWorkspaceDashboard,
} from "@plane/types";
import { APIService } from "@/services/api.service";
// helpers
// types

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

  /**
   * §33 — `POST /api/workspaces/{slug}/dashboards/{id}/widgets`.
   * The widget stores the AnalyticsQuery V2 configuration, never a snapshot of
   * the current results (§18.2).
   */
  async createDashboardWidget(
    workspaceSlug: string,
    dashboardId: string,
    payload: TDashboardWidgetPayload
  ): Promise<TWidget> {
    return this.post(`/api/workspaces/${workspaceSlug}/dashboards/${dashboardId}/widgets/`, payload)
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
