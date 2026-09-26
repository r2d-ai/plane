/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsTimeScope, TWorkspaceDashboardWidget } from "@plane/types";

export function resolveWidgetTimeScope(
  dashboardDefault: Record<string, unknown> | undefined,
  widget: Pick<TWorkspaceDashboardWidget, "inherit_time_scope" | "custom_time_scope">
): TAnalyticsTimeScope | undefined {
  if (widget.inherit_time_scope) {
    return (dashboardDefault as TAnalyticsTimeScope | undefined) ?? undefined;
  }
  if (widget.custom_time_scope) {
    return widget.custom_time_scope as TAnalyticsTimeScope;
  }
  return (dashboardDefault as TAnalyticsTimeScope | undefined) ?? undefined;
}

export function dashboardTimeScopeFromPreset(preset: string, basis?: string): Record<string, unknown> {
  return {
    preset,
    basis: basis ?? "lifecycle_overlap",
  };
}

export function isStaticWidgetType(widgetType: string): boolean {
  return widgetType === "text" || widgetType === "markdown";
}
