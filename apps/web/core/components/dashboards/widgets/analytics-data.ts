/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type {
  TAnalyticsCell,
  TAnalyticsDisplay,
  TAnalyticsQueryResponseV2,
  TAnalyticsQueryV2,
  TDashboardBatchDataResponse,
  TWorkspaceDashboardDetail,
  TWorkspaceDashboardWidget,
} from "@plane/types";
import { buildWidgetBatchRequest, normalizeWidgetBatchResults } from "@/components/analytics/v2/batch-composer";
import type { MatrixTableModel } from "@/components/analytics/v2/cells";
import { formatPercentage, formatValue } from "@/components/analytics/v2/cells";
import { AnalyticsService } from "@/services/analytics.service";

/** Re-exported from the analytics namespace so generic renderers can read it (§12.1). */
export {
  WARNING_RESULT_TRUNCATED,
  findTruncationWarning,
  hasTruncatedResult,
} from "@/components/analytics/v2/warnings";
export { VIEWER_FILTER_TOKENS, resolveViewerFilterPlaceholders } from "@/components/analytics/v2/viewer-filters";

/** §12.1 — the matrix model is a generic presentation concern, not a dashboard one. */
export { buildMatrixTableModel, type MatrixTableModel } from "@/components/analytics/v2/cells";

const analyticsService = new AnalyticsService();

/**
 * §32.3 — every card's data in one `POST /analytics/v2/batch/` call.
 *
 * The client composes the entries (scoped project ids, intersected filters,
 * inherited time scope) and the engine answers each one independently, so a
 * single broken card degrades to its own error state instead of blanking the
 * dashboard. Replaces the dashboard-scoped `POST /dashboards/{id}/data/`.
 */
export async function fetchDashboardWidgetBatch(
  workspaceSlug: string,
  dashboard: TWorkspaceDashboardDetail,
  widgets: TWorkspaceDashboardWidget[],
  viewerId: string
): Promise<TDashboardBatchDataResponse> {
  const payload = await analyticsService.postAnalyticsV2Batch(
    workspaceSlug,
    buildWidgetBatchRequest(dashboard, widgets, viewerId)
  );
  return normalizeWidgetBatchResults(dashboard, widgets, payload?.results);
}

export function parseWidgetQuery(widget: TWorkspaceDashboardWidget): TAnalyticsQueryV2 | null {
  const config = widget.query_config;
  if (!config || typeof config !== "object") return null;
  const body = config as Record<string, unknown>;
  if (body.query && typeof body.query === "object") {
    return body.query as TAnalyticsQueryV2;
  }
  const { schema_version: _schema, ...rest } = body;
  if (typeof rest.version !== "number") return null;
  return rest as TAnalyticsQueryV2;
}

export function asAnalyticsResponse(data: unknown): TAnalyticsQueryResponseV2 | null {
  if (!data || typeof data !== "object") return null;
  const candidate = data as TAnalyticsQueryResponseV2;
  if (!Array.isArray(candidate.data)) return null;
  return candidate;
}

export function formatDisplayForCell(cell: TAnalyticsCell | undefined, display: TAnalyticsDisplay, unit = ""): string {
  if (!cell) return "—";
  const raw = cell.value ?? 0;
  if (display === "percentage") return formatPercentage(cell.percentage);
  if (display === "value_and_percentage") {
    return cell.display ?? `${formatValue(raw, unit)} · ${formatPercentage(cell.percentage)}`;
  }
  if (cell.display) return cell.display;
  return formatValue(raw, unit);
}

export { aggregateCellsToCsvRows, downloadCsv, matrixToCsvRows } from "@/components/analytics/v2/csv";
