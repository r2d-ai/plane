/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TChartData } from "./charts";

export enum ChartXAxisProperty {
  STATES = "STATES",
  STATE_GROUPS = "STATE_GROUPS",
  LABELS = "LABELS",
  ASSIGNEES = "ASSIGNEES",
  ESTIMATE_POINTS = "ESTIMATE_POINTS",
  CYCLES = "CYCLES",
  MODULES = "MODULES",
  PRIORITY = "PRIORITY",
  START_DATE = "START_DATE",
  TARGET_DATE = "TARGET_DATE",
  CREATED_AT = "CREATED_AT",
  COMPLETED_AT = "COMPLETED_AT",
  CREATED_BY = "CREATED_BY",
  WORK_ITEM_TYPES = "WORK_ITEM_TYPES",
  PROJECTS = "PROJECTS",
  EPICS = "EPICS",
}

export enum ChartYAxisMetric {
  WORK_ITEM_COUNT = "WORK_ITEM_COUNT",
  ESTIMATE_POINT_COUNT = "ESTIMATE_POINT_COUNT",
  PENDING_WORK_ITEM_COUNT = "PENDING_WORK_ITEM_COUNT",
  COMPLETED_WORK_ITEM_COUNT = "COMPLETED_WORK_ITEM_COUNT",
  IN_PROGRESS_WORK_ITEM_COUNT = "IN_PROGRESS_WORK_ITEM_COUNT",
  WORK_ITEM_DUE_THIS_WEEK_COUNT = "WORK_ITEM_DUE_THIS_WEEK_COUNT",
  WORK_ITEM_DUE_TODAY_COUNT = "WORK_ITEM_DUE_TODAY_COUNT",
  BLOCKED_WORK_ITEM_COUNT = "BLOCKED_WORK_ITEM_COUNT",
  EPIC_WORK_ITEM_COUNT = "EPIC_WORK_ITEM_COUNT",
}

export type TAnalyticsTabsBase = "overview" | "work-items";
export type TAnalyticsGraphsBase = "projects" | "work-items" | "custom-work-items";
export interface AnalyticsTab {
  key: TAnalyticsTabsBase;
  label: string;
  content: React.FC;
  isDisabled: boolean;
}
export type TAnalyticsFilterParams = {
  project_ids?: string;
  cycle_id?: string;
  module_id?: string;
};

// service types

export interface IAnalyticsResponse {
  [key: string]: any;
}

export interface IAnalyticsResponseFields {
  count: number;
  filter_count: number;
}

// chart types

export interface IChartResponse {
  schema: Record<string, string>;
  data: TChartData<string, string>[];
}

// table types

export interface WorkItemInsightColumns {
  project_id?: string;
  project__name?: string;
  cancelled_work_items: number;
  completed_work_items: number;
  backlog_work_items: number;
  un_started_work_items: number;
  started_work_items: number;
  // in case of peek view, we will display the display_name instead of project__name
  display_name?: string;
  avatar_url?: string;
  assignee_id?: string;
}

export type AnalyticsTableDataMap = {
  "work-items": WorkItemInsightColumns;
};

export interface IAnalyticsParams {
  x_axis: ChartXAxisProperty;
  y_axis: ChartYAxisMetric;
  group_by?: ChartXAxisProperty;
}

// ---------------------------------------------------------------------------
// Analytics Engine V2 (RD-451). Additive — legacy exports above are preserved.
// ---------------------------------------------------------------------------

export type TAnalyticsMetricKey =
  | "work_item_count"
  | "estimate_points"
  | "pending_work_items"
  | "completed_work_items"
  | "in_progress_work_items"
  | "due_today"
  | "due_this_week"
  | "blocked_work_items"
  | "overdue_work_items"
  | "unassigned_work_items"
  | "allocated_work_item_count"
  | "allocated_estimate_points";

export type TAnalyticsDimensionKey =
  | "state"
  | "state_group"
  | "project"
  | "priority"
  | "assignees"
  | "created_by"
  | "labels"
  | "cycle"
  | "module"
  | "work_item_type"
  | "estimate_point"
  | "created_date"
  | "completed_date"
  | "start_date"
  | "due_date";

export type TAnalyticsTimePreset =
  | "today"
  | "yesterday"
  | "this_week"
  | "last_week"
  | "last_7_days"
  | "last_30_days"
  | "this_month"
  | "last_month"
  | "this_quarter"
  | "last_quarter"
  | "last_90_days"
  | "this_year"
  | "last_year"
  | "custom"
  | "none";

export type TAnalyticsDateBasis = "created_at" | "completed_at" | "start_date" | "target_date" | "lifecycle_overlap";

export type TAnalyticsComparison =
  | "none"
  | "previous_period"
  | "previous_week"
  | "previous_month"
  | "previous_quarter"
  | "previous_year";

export type TAnalyticsAllocation = "full_credit" | "split_equal" | "none";

export type TAnalyticsNormalization = "none" | "group_total" | "series_total" | "grand_total";

export type TAnalyticsDisplay = "value" | "percentage" | "value_and_percentage";

export interface TAnalyticsMetric {
  key: TAnalyticsMetricKey;
  allocation?: TAnalyticsAllocation;
}

export interface TAnalyticsDimension {
  key: TAnalyticsDimensionKey;
}

export interface TAnalyticsTimeScope {
  preset: TAnalyticsTimePreset;
  basis?: TAnalyticsDateBasis;
  timezone?: string;
  group?: "day" | "week" | "month" | "quarter" | "year";
  start?: string; // ISO date for ``custom``
  end?: string;
}

export interface TAnalyticsComparisonBlock {
  type: TAnalyticsComparison;
}

export interface TAnalyticsSort {
  metric: TAnalyticsMetricKey;
  direction: "asc" | "desc";
}

export interface TAnalyticsQueryV2 {
  version: 1;
  source: "work_items";
  project_ids?: string[];
  metrics: TAnalyticsMetric[];
  dimensions: TAnalyticsDimension[];
  filters?: Record<string, string | string[] | null>;
  time?: TAnalyticsTimeScope;
  comparison?: TAnalyticsComparisonBlock;
  normalization?: TAnalyticsNormalization;
  display?: TAnalyticsDisplay;
  allocation?: TAnalyticsAllocation;
  sort?: TAnalyticsSort[];
  limit?: number;
}

export interface TAnalyticsResolvedScope {
  start: string | null;
  end: string | null;
  timezone: string;
  preset: TAnalyticsTimePreset;
  visible_project_count: number;
  comparison?: {
    type: TAnalyticsComparison;
    start: string;
    end: string;
    current_total: number;
    previous_total: number;
    delta: number;
    percentage_change: number | null;
  };
}

export interface TAnalyticsCell {
  group: string | null;
  series: string | null;
  value: number;
  percentage: number | null;
  display?: string;
}

export interface TAnalyticsWarning {
  code: string;
  message: string;
}

export interface TAnalyticsQueryResponseV2 {
  query: TAnalyticsQueryV2;
  resolved: TAnalyticsResolvedScope;
  schema: {
    metrics: { key: TAnalyticsMetricKey; category: string }[];
    dimensions: { key: TAnalyticsDimensionKey; category: string }[];
  };
  data: TAnalyticsCell[];
  totals: Record<string, number>;
  warnings: TAnalyticsWarning[];
}

export interface TAnalyticsDrilldownRequestV2 {
  query: TAnalyticsQueryV2;
  selection: Record<TAnalyticsDimensionKey, string | string[] | null>;
  page?: number;
  page_size?: number;
}

export interface TAnalyticsDrilldownRowV2 {
  id: string;
  sequence_id: number;
  project_id: string;
  name: string;
  priority: string;
  state_id: string | null;
  state_group: string | null;
  estimate_point: number | null;
  start_date: string | null;
  target_date: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface TAnalyticsDrilldownResponseV2 {
  query: TAnalyticsQueryV2;
  resolved: TAnalyticsResolvedScope;
  selection: Record<TAnalyticsDimensionKey, string | string[] | null>;
  total: number;
  page: number;
  page_size: number;
  rows: TAnalyticsDrilldownRowV2[];
  contributions: Record<string, number>;
}

export interface TAnalyticsBatchResultV2 {
  key: string;
  status: "ok" | "error";
  data?: TAnalyticsQueryResponseV2;
  error?: { code: string; message: string };
}

export interface TAnalyticsBatchResponseV2 {
  workspace_slug: string;
  results: TAnalyticsBatchResultV2[];
}
