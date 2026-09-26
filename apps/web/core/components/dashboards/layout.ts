/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * FROZEN -- legacy dashboard-builder surface, scheduled for deletion in Phase D of RD-475.
 * Product spec: docs/workspace-dashboards-analytics-v2-spec.md
 * Do not add features, extend behaviour, or wire up new consumers here. The fixed
 * Workspace Dashboard replaces this surface; see RD-475 for the migration table.
 */

import type { CSSProperties } from "react";
import type {
  TDashboardLayoutUpdateEntry,
  TDashboardWidgetLayoutConfig,
  TWorkspaceDashboardWidget,
} from "@plane/types";

import { DASHBOARD_GRID_COLUMNS, DEFAULT_WIDGET_LAYOUT } from "./constants";

export type TDashboardGridItem = TDashboardWidgetLayoutConfig & { id: string };

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function defaultLayoutForIndex(index: number): TDashboardWidgetLayoutConfig {
  const row = Math.floor(index / 3);
  const col = (index % 3) * DEFAULT_WIDGET_LAYOUT.w;
  return {
    x: col,
    y: row * DEFAULT_WIDGET_LAYOUT.h,
    w: DEFAULT_WIDGET_LAYOUT.w,
    h: DEFAULT_WIDGET_LAYOUT.h,
    minW: DEFAULT_WIDGET_LAYOUT.minW,
    minH: DEFAULT_WIDGET_LAYOUT.minH,
  };
}

export function normalizeGridLayout(widgets: TWorkspaceDashboardWidget[]): TDashboardGridItem[] {
  const sorted = [...widgets].toSorted((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0));
  return sorted.map((widget, index) => {
    const layout = widget.layout_config ?? defaultLayoutForIndex(index);
    return {
      id: widget.id,
      x: layout.x ?? 0,
      y: layout.y ?? 0,
      w: layout.w ?? DEFAULT_WIDGET_LAYOUT.w,
      h: layout.h ?? DEFAULT_WIDGET_LAYOUT.h,
      minW: layout.minW ?? DEFAULT_WIDGET_LAYOUT.minW,
      minH: layout.minH ?? DEFAULT_WIDGET_LAYOUT.minH,
    };
  });
}

export function moveGridItem(
  layout: TDashboardGridItem[],
  widgetId: string,
  nextX: number,
  nextY: number
): TDashboardGridItem[] {
  return layout.map((item) => {
    if (item.id !== widgetId) return item;
    const maxX = DASHBOARD_GRID_COLUMNS - item.w;
    return {
      ...item,
      x: clamp(nextX, 0, maxX),
      y: Math.max(0, nextY),
    };
  });
}

export function resizeGridItem(
  layout: TDashboardGridItem[],
  widgetId: string,
  nextW: number,
  nextH: number
): TDashboardGridItem[] {
  return layout.map((item) => {
    if (item.id !== widgetId) return item;
    const minW = item.minW ?? DEFAULT_WIDGET_LAYOUT.minW;
    const minH = item.minH ?? DEFAULT_WIDGET_LAYOUT.minH;
    const w = clamp(nextW, minW, DASHBOARD_GRID_COLUMNS);
    const h = clamp(nextH, minH, 12);
    const maxX = DASHBOARD_GRID_COLUMNS - w;
    return {
      ...item,
      w,
      h,
      x: clamp(item.x, 0, maxX),
    };
  });
}

export function buildLayoutPersistencePayload(layout: TDashboardGridItem[]): TDashboardLayoutUpdateEntry[] {
  return layout.map((item, index) => ({
    id: item.id,
    sort_order: index,
    layout_config: {
      x: item.x,
      y: item.y,
      w: item.w,
      h: item.h,
      minW: item.minW,
      minH: item.minH,
    },
  }));
}

/** §7 — deterministic mobile ordering: sort by row then column. */
export function mobileStackOrder(layout: TDashboardGridItem[]): string[] {
  return [...layout]
    .toSorted((a, b) => {
      if (a.y === b.y) return a.x - b.x;
      return a.y - b.y;
    })
    .map((item) => item.id);
}

export function gridItemStyle(item: TDashboardGridItem, mobileStack: boolean): CSSProperties {
  if (mobileStack) {
    return { gridColumn: "1 / -1" };
  }
  return {
    gridColumn: `${item.x + 1} / span ${item.w}`,
    gridRow: `span ${item.h}`,
  };
}
