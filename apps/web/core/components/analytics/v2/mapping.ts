/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Legacy ⇄ Analytics Engine V2 key mapping for Customized Insights (§18, §35).
 *
 * The existing Customized Insights form is expressed in the legacy
 * `ChartXAxisProperty` / `ChartYAxisMetric` vocabulary (§4). Rather than
 * rewriting every consumer, those selections are translated to the V2 registry
 * keys published by RD-451 — a pure, exhaustively-checked adapter, never a
 * second aggregation path (§3.1).
 */

import { ANALYTICS_DEFAULT_TIME_PRESET, ANALYTICS_DURATION_TO_TIME_PRESET } from "@plane/constants";
import type {
  TAnalyticsDateGrouping,
  TAnalyticsDimensionKey,
  TAnalyticsMetricKey,
  TAnalyticsTimePreset,
} from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";

/** Legacy x-axis → V2 dimension key. `null` = no P0 equivalent (§12). */
export const X_AXIS_TO_DIMENSION: Record<ChartXAxisProperty, TAnalyticsDimensionKey | null> = {
  [ChartXAxisProperty.STATES]: "state",
  [ChartXAxisProperty.STATE_GROUPS]: "state_group",
  [ChartXAxisProperty.LABELS]: "labels",
  [ChartXAxisProperty.ASSIGNEES]: "assignees",
  [ChartXAxisProperty.ESTIMATE_POINTS]: "estimate_point",
  [ChartXAxisProperty.CYCLES]: "cycle",
  [ChartXAxisProperty.MODULES]: "module",
  [ChartXAxisProperty.PRIORITY]: "priority",
  [ChartXAxisProperty.START_DATE]: "start_date",
  [ChartXAxisProperty.TARGET_DATE]: "due_date",
  [ChartXAxisProperty.CREATED_AT]: "created_date",
  [ChartXAxisProperty.COMPLETED_AT]: "completed_date",
  [ChartXAxisProperty.CREATED_BY]: "created_by",
  [ChartXAxisProperty.WORK_ITEM_TYPES]: "work_item_type",
  [ChartXAxisProperty.PROJECTS]: "project",
  [ChartXAxisProperty.EPICS]: null,
};

/**
 * Legacy y-axis → V2 metric key (§13). `EPIC_WORK_ITEM_COUNT` had no
 * dedicated predicate in the legacy engine either — it resolved to a plain
 * count, which is exactly `work_item_count`.
 */
export const Y_AXIS_TO_METRIC: Record<ChartYAxisMetric, TAnalyticsMetricKey> = {
  [ChartYAxisMetric.WORK_ITEM_COUNT]: "work_item_count",
  [ChartYAxisMetric.ESTIMATE_POINT_COUNT]: "estimate_points",
  [ChartYAxisMetric.PENDING_WORK_ITEM_COUNT]: "pending_work_items",
  [ChartYAxisMetric.COMPLETED_WORK_ITEM_COUNT]: "completed_work_items",
  [ChartYAxisMetric.IN_PROGRESS_WORK_ITEM_COUNT]: "in_progress_work_items",
  [ChartYAxisMetric.WORK_ITEM_DUE_THIS_WEEK_COUNT]: "due_this_week",
  [ChartYAxisMetric.WORK_ITEM_DUE_TODAY_COUNT]: "due_today",
  [ChartYAxisMetric.BLOCKED_WORK_ITEM_COUNT]: "blocked_work_items",
  [ChartYAxisMetric.EPIC_WORK_ITEM_COUNT]: "work_item_count",
};

/** V2 dimensions whose values are calendar buckets (§9.3, §12). */
export const DATE_DIMENSIONS: TAnalyticsDimensionKey[] = ["created_date", "completed_date", "start_date", "due_date"];

export const isDateDimension = (dimension: TAnalyticsDimensionKey | null | undefined): boolean =>
  !!dimension && DATE_DIMENSIONS.includes(dimension);

/** §9 — legacy duration key → V2 time preset. */
export const toTimePreset = (duration: string | null | undefined): TAnalyticsTimePreset =>
  (duration && ANALYTICS_DURATION_TO_TIME_PRESET[duration]) || ANALYTICS_DEFAULT_TIME_PRESET;

/** Map a legacy x-axis selection to its V2 dimension, or `null` if unsupported. */
export const toDimensionKey = (xAxis: ChartXAxisProperty | null | undefined): TAnalyticsDimensionKey | null =>
  xAxis ? (X_AXIS_TO_DIMENSION[xAxis] ?? null) : null;

/** Map a legacy y-axis selection to its V2 metric key. */
export const toMetricKey = (yAxis: ChartYAxisMetric | null | undefined): TAnalyticsMetricKey =>
  (yAxis && Y_AXIS_TO_METRIC[yAxis]) || "work_item_count";

/** The metric label shown as the chart/table column header. */
export const METRIC_LABELS: Record<TAnalyticsMetricKey, string> = {
  work_item_count: "Work item count",
  estimate_points: "Estimate points",
  pending_work_items: "Pending work items",
  completed_work_items: "Completed work items",
  in_progress_work_items: "In progress work items",
  due_today: "Due today",
  due_this_week: "Due this week",
  blocked_work_items: "Blocked work items",
  overdue_work_items: "Overdue work items",
  unassigned_work_items: "Unassigned work items",
  allocated_work_item_count: "Allocated work-item count",
  allocated_estimate_points: "Allocated estimate points",
};

/** The metric's display unit, mirroring the engine's `_unit_for_metric`. */
export const metricUnit = (metric: TAnalyticsMetricKey): string =>
  metric === "estimate_points" || metric === "allocated_estimate_points" ? " pts" : "";

/** §9.3 — supported date groupings. */
export const DATE_GROUPINGS: TAnalyticsDateGrouping[] = ["day", "week", "month", "quarter", "year"];
