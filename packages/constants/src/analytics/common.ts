/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TAnalyticsAllocation,
  TAnalyticsDateBasis,
  TAnalyticsDateGrouping,
  TAnalyticsDisplay,
  TAnalyticsNormalization,
  TAnalyticsTabsBase,
  TAnalyticsTimePreset,
} from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";

export interface IInsightField {
  key: string;
  i18nKey: string;
  i18nProps?: {
    entity?: string;
    entityPlural?: string;
    prefix?: string;
    suffix?: string;
    [key: string]: unknown;
  };
}

export const ANALYTICS_INSIGHTS_FIELDS: Record<TAnalyticsTabsBase, IInsightField[]> = {
  overview: [
    {
      key: "total_users",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.users",
      },
    },
    {
      key: "total_admins",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.admins",
      },
    },
    {
      key: "total_members",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.members",
      },
    },
    {
      key: "total_guests",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.guests",
      },
    },
    {
      key: "total_projects",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.projects",
      },
    },
    {
      key: "total_work_items",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.work_items",
      },
    },
    {
      key: "total_cycles",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.cycles",
      },
    },
    {
      key: "total_intake",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "sidebar.intake",
      },
    },
  ],
  "work-items": [
    {
      key: "total_work_items",
      i18nKey: "workspace_analytics.total",
    },
    {
      key: "started_work_items",
      i18nKey: "workspace_analytics.started_work_items",
    },
    {
      key: "backlog_work_items",
      i18nKey: "workspace_analytics.backlog_work_items",
    },
    {
      key: "un_started_work_items",
      i18nKey: "workspace_analytics.un_started_work_items",
    },
    {
      key: "completed_work_items",
      i18nKey: "workspace_analytics.completed_work_items",
    },
  ],
};

export const ANALYTICS_DURATION_FILTER_OPTIONS = [
  {
    name: "Yesterday",
    value: "yesterday",
  },
  {
    name: "Last 7 days",
    value: "last_7_days",
  },
  {
    name: "Last 30 days",
    value: "last_30_days",
  },
  {
    name: "Last 3 months",
    value: "last_3_months",
  },
];

export const ANALYTICS_X_AXIS_VALUES: { value: ChartXAxisProperty; label: string }[] = [
  {
    value: ChartXAxisProperty.STATES,
    label: "State name",
  },
  {
    value: ChartXAxisProperty.STATE_GROUPS,
    label: "State group",
  },
  {
    value: ChartXAxisProperty.PRIORITY,
    label: "Priority",
  },
  {
    value: ChartXAxisProperty.LABELS,
    label: "Label",
  },
  {
    value: ChartXAxisProperty.ASSIGNEES,
    label: "Assignee",
  },
  {
    value: ChartXAxisProperty.ESTIMATE_POINTS,
    label: "Estimate point",
  },
  {
    value: ChartXAxisProperty.CYCLES,
    label: "Cycle",
  },
  {
    value: ChartXAxisProperty.MODULES,
    label: "Module",
  },
  {
    value: ChartXAxisProperty.COMPLETED_AT,
    label: "Completed date",
  },
  {
    value: ChartXAxisProperty.TARGET_DATE,
    label: "Due date",
  },
  {
    value: ChartXAxisProperty.START_DATE,
    label: "Start date",
  },
  {
    value: ChartXAxisProperty.CREATED_AT,
    label: "Created date",
  },
  {
    value: ChartXAxisProperty.PROJECTS,
    label: "Project",
  },
  {
    value: ChartXAxisProperty.CREATED_BY,
    label: "Created by",
  },
  {
    value: ChartXAxisProperty.WORK_ITEM_TYPES,
    label: "Work item type",
  },
];

export const ANALYTICS_Y_AXIS_VALUES: { value: ChartYAxisMetric; label: string }[] = [
  {
    value: ChartYAxisMetric.WORK_ITEM_COUNT,
    label: "Work item",
  },
  {
    value: ChartYAxisMetric.ESTIMATE_POINT_COUNT,
    label: "Estimate",
  },
  {
    value: ChartYAxisMetric.EPIC_WORK_ITEM_COUNT,
    label: "Epic",
  },
];

export const ANALYTICS_V2_DATE_KEYS = ["completed_at", "target_date", "start_date", "created_at"];

// ---------------------------------------------------------------------------
// Analytics V2 (RD-454) — Customized Insights control options (§18, §9, §15,
// §17). Values are wire keys consumed by the Analytics Engine V2.
// ---------------------------------------------------------------------------

/** Workspace Analytics header, §9.1 date basis. */
export const ANALYTICS_DATE_BASIS_OPTIONS: { value: TAnalyticsDateBasis; label: string }[] = [
  { value: "created_at", label: "Created date" },
  { value: "completed_at", label: "Completed date" },
  { value: "start_date", label: "Start date" },
  { value: "target_date", label: "Due date" },
  { value: "lifecycle_overlap", label: "Lifecycle overlap" },
];

export const ANALYTICS_DEFAULT_DATE_BASIS: TAnalyticsDateBasis = "created_at";

/** §9.3 date grouping for date dimensions. */
export const ANALYTICS_DATE_GROUPING_OPTIONS: { value: TAnalyticsDateGrouping; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
  { value: "year", label: "Year" },
];

/** §17.4 display mode. */
export const ANALYTICS_DISPLAY_OPTIONS: { value: TAnalyticsDisplay; label: string }[] = [
  { value: "value", label: "Value" },
  { value: "percentage", label: "Percentage" },
  { value: "value_and_percentage", label: "Value + Percentage" },
];

/** §17 percentage normalization bases. */
export const ANALYTICS_NORMALIZATION_OPTIONS: { value: TAnalyticsNormalization; label: string }[] = [
  { value: "none", label: "None" },
  { value: "group_total", label: "Group total" },
  { value: "series_total", label: "Series / assignee total" },
  { value: "grand_total", label: "Grand total" },
];

/** §15 multi-assignee allocation. */
export const ANALYTICS_ALLOCATION_OPTIONS: { value: TAnalyticsAllocation; label: string }[] = [
  { value: "full_credit", label: "Full credit" },
  { value: "split_equal", label: "Split equally" },
];

/**
 * Legacy duration key (§4 baseline, also used by the ``date_filter`` query
 * param of the legacy advance-analytics endpoints) → Analytics V2 time preset
 * (§9). The two vocabularies are deliberately separate: the legacy backend only
 * understands four values, V2 understands the full preset set.
 */
export const ANALYTICS_DURATION_TO_TIME_PRESET: Record<string, TAnalyticsTimePreset> = {
  yesterday: "yesterday",
  last_7_days: "last_7_days",
  last_30_days: "last_30_days",
  last_3_months: "last_90_days",
};

export const ANALYTICS_DEFAULT_TIME_PRESET: TAnalyticsTimePreset = "last_30_days";
