/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type {
  IAnalyticsResponse,
  TAnalyticsTabsBase,
  TAnalyticsGraphsBase,
  TAnalyticsFilterParams,
  TAnalyticsDrilldownRequestV2,
  TAnalyticsDrilldownResponseV2,
  TAnalyticsQueryResponseV2,
  TAnalyticsQueryV2,
} from "@plane/types";
// services
import { APIService } from "./api.service";
import type { TAnalyticsBatchRequest, TAnalyticsBatchResponse } from "@/components/analytics/v2/batch-composer";

export class AnalyticsService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getAdvanceAnalytics<T extends IAnalyticsResponse>(
    workspaceSlug: string,
    tab: TAnalyticsTabsBase,
    params?: TAnalyticsFilterParams,
    isPeekView?: boolean
  ): Promise<T> {
    return this.get(this.processUrl<TAnalyticsTabsBase>("advance-analytics", workspaceSlug, tab, params, isPeekView), {
      params: {
        tab,
        ...params,
      },
    })
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async getAdvanceAnalyticsStats<T>(
    workspaceSlug: string,
    tab: Exclude<TAnalyticsTabsBase, "overview">,
    params?: TAnalyticsFilterParams,
    isPeekView?: boolean
  ): Promise<T> {
    const processedUrl = this.processUrl<Exclude<TAnalyticsTabsBase, "overview">>(
      "advance-analytics-stats",
      workspaceSlug,
      tab,
      params,
      isPeekView
    );
    return this.get(processedUrl, {
      params: {
        type: tab,
        ...params,
      },
    })
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  async getAdvanceAnalyticsCharts<T>(
    workspaceSlug: string,
    tab: TAnalyticsGraphsBase,
    params?: TAnalyticsFilterParams,
    isPeekView?: boolean
  ): Promise<T> {
    const processedUrl = this.processUrl<TAnalyticsGraphsBase>(
      "advance-analytics-charts",
      workspaceSlug,
      tab,
      params,
      isPeekView
    );
    return this.get(processedUrl, {
      params: {
        type: tab,
        ...params,
      },
    })
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  /**
   * Analytics Engine V2 (RD-451) — `POST /analytics/v2/query`.
   *
   * This is the single aggregation path for Customized Insights V2 (§3.1):
   * the client never re-aggregates locally.
   */
  async postAnalyticsV2Query(workspaceSlug: string, query: TAnalyticsQueryV2): Promise<TAnalyticsQueryResponseV2> {
    return this.post(`/api/workspaces/${workspaceSlug}/analytics/v2/query/`, query)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  /**
   * Analytics Engine V2 (RD-451) — `POST /analytics/v2/drilldown` (§25, §32.2).
   * The drill-down derives from the exact resolved aggregate query; the client
   * only supplies the selected dimension values.
   */
  async postAnalyticsV2Drilldown(
    workspaceSlug: string,
    payload: TAnalyticsDrilldownRequestV2
  ): Promise<TAnalyticsDrilldownResponseV2> {
    return this.post(`/api/workspaces/${workspaceSlug}/analytics/v2/drilldown/`, payload)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  /**
   * The last dashboard-scoped analytics call, inherited from the builder
   * service that RD-483 deleted. Only `WidgetDrilldownDrawer` still calls it,
   * and the fixed Workspace Dashboard never reaches that drawer (it opens
   * `postAnalyticsV2Drilldown` through `onOpenWorkItems` instead). It goes away
   * with the drill-down route in E.1.
   */
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
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  /**
   * Analytics Engine V2 (RD-451) — `POST /analytics/v2/batch` (§32.3, §40.2).
   *
   * `{"queries": [{key, ...query}]}` — each entry is executed independently, so
   * one malformed card query answers `status: "error"` while its neighbours
   * still return data.
   */
  async postAnalyticsV2Batch(workspaceSlug: string, payload: TAnalyticsBatchRequest): Promise<TAnalyticsBatchResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/analytics/v2/batch/`, payload)
      .then((res) => res?.data)
      .catch((err) => {
        throw err?.response?.data;
      });
  }

  processUrl<_T extends string>(
    endpoint: string,
    workspaceSlug: string,
    tab: TAnalyticsGraphsBase | TAnalyticsTabsBase,
    params?: TAnalyticsFilterParams,
    isPeekView?: boolean
  ) {
    let processedUrl = `/api/workspaces/${workspaceSlug}`;
    if (isPeekView && (tab === "work-items" || tab === "custom-work-items")) {
      const projectIds = params?.project_ids;
      if (typeof projectIds !== "string" || !projectIds.trim()) {
        throw new Error("project_ids parameter is required for peek view of work items");
      }
      const projectId = projectIds.split(",")[0];
      if (!projectId) {
        throw new Error("Invalid project_ids format - no project ID found");
      }
      processedUrl += `/projects/${projectId}`;
    }
    return `${processedUrl}/${endpoint}`;
  }
}
