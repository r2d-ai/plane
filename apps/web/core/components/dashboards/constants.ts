/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsTimePreset, TDashboardListTab } from "@plane/types";

export const DASHBOARD_GRID_COLUMNS = 12;

export const DEFAULT_WIDGET_LAYOUT = {
  w: 4,
  h: 3,
  minW: 2,
  minH: 2,
} as const;

export const DASHBOARD_LIST_TABS: TDashboardListTab[] = ["all", "mine", "shared", "favorites"];

export const DASHBOARD_TIME_PRESET_OPTIONS: { value: TAnalyticsTimePreset; labelKey: string }[] = [
  { value: "this_quarter", labelKey: "dashboard_shell.time.this_quarter" },
  { value: "last_quarter", labelKey: "dashboard_shell.time.last_quarter" },
  { value: "this_month", labelKey: "dashboard_shell.time.this_month" },
  { value: "last_month", labelKey: "dashboard_shell.time.last_month" },
  { value: "this_week", labelKey: "dashboard_shell.time.this_week" },
  { value: "last_7_days", labelKey: "dashboard_shell.time.last_7_days" },
  { value: "last_30_days", labelKey: "dashboard_shell.time.last_30_days" },
  { value: "none", labelKey: "dashboard_shell.time.none" },
];

import type { TDashboardWidgetQueryConfig } from "@plane/types";

export const MARKDOWN_PLACEHOLDER_QUERY_CONFIG: TDashboardWidgetQueryConfig = {
  schema_version: 1,
  version: 1,
  source: "work_items",
  metrics: [{ key: "work_item_count" }],
  dimensions: [{ key: "project" }],
  time: { preset: "none" },
};
