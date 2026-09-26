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
  TAnalyticsWarning,
  TWorkspaceDashboardWidget,
} from "@plane/types";
import { formatPercentage, formatValue } from "@/components/analytics/v2/cells";

export const WARNING_RESULT_TRUNCATED = "RESULT_TRUNCATED";

export const VIEWER_FILTER_TOKENS = new Set(["current_user", "@current_user"]);

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

export function findTruncationWarning(warnings: TAnalyticsWarning[] | undefined): TAnalyticsWarning | undefined {
  return warnings?.find((entry) => entry.code === WARNING_RESULT_TRUNCATED);
}

export function hasTruncatedResult(warnings: TAnalyticsWarning[] | undefined): boolean {
  return !!findTruncationWarning(warnings);
}

/** §22 — substitute viewer tokens for display/tests (server resolves on query). */
export function resolveViewerFilterPlaceholders(
  filters: Record<string, unknown> | undefined,
  viewerId: string
): Record<string, unknown> {
  if (!filters) return {};
  const out: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(filters)) {
    if (raw === null || raw === undefined) continue;
    if (Array.isArray(raw)) {
      out[key] = raw.map((token) => (typeof token === "string" && VIEWER_FILTER_TOKENS.has(token) ? viewerId : token));
    } else if (typeof raw === "string" && VIEWER_FILTER_TOKENS.has(raw)) {
      out[key] = viewerId;
    } else {
      out[key] = raw;
    }
  }
  return out;
}

export type MatrixTableModel = {
  rowKeys: string[];
  colKeys: string[];
  cells: Record<string, Record<string, { raw: number; display: string }>>;
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  grandTotal: number;
};

/** §20 — cross-tab with row/column totals from flat V2 cells. */
export function buildMatrixTableModel(
  cells: TAnalyticsCell[],
  display: TAnalyticsDisplay,
  unit = ""
): MatrixTableModel {
  const rowKeys: string[] = [];
  const colKeys: string[] = [];
  const rowSet = new Set<string>();
  const colSet = new Set<string>();
  const grid = new Map<string, Map<string, TAnalyticsCell>>();

  for (const cell of cells ?? []) {
    const row = cell.group === null || cell.group === undefined ? "" : String(cell.group);
    const col = cell.series === null || cell.series === undefined ? "" : String(cell.series);
    if (!rowSet.has(row)) {
      rowSet.add(row);
      rowKeys.push(row);
    }
    if (!colSet.has(col)) {
      colSet.add(col);
      colKeys.push(col);
    }
    if (!grid.has(row)) grid.set(row, new Map());
    grid.get(row)?.set(col, cell);
  }

  const cellsOut: MatrixTableModel["cells"] = {};
  const rowTotals: Record<string, number> = {};
  const colTotals: Record<string, number> = {};
  let grandTotal = 0;

  for (const row of rowKeys) {
    cellsOut[row] = {};
    let rowSum = 0;
    for (const col of colKeys) {
      const cell = grid.get(row)?.get(col);
      const raw = cell?.value ?? 0;
      rowSum += raw;
      colTotals[col] = (colTotals[col] ?? 0) + raw;
      const displayStr =
        cell?.display ??
        (display === "percentage"
          ? formatPercentage(cell?.percentage)
          : display === "value_and_percentage"
            ? `${formatValue(raw, unit)} · ${formatPercentage(cell?.percentage)}`
            : formatValue(raw, unit));
      cellsOut[row][col] = { raw, display: displayStr };
    }
    rowTotals[row] = rowSum;
    grandTotal += rowSum;
  }

  return { rowKeys, colKeys, cells: cellsOut, rowTotals, colTotals, grandTotal };
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

type CsvRow = Record<string, string | number | null>;

export function aggregateCellsToCsvRows(
  response: TAnalyticsQueryResponseV2,
  options: { includeTruncationNote?: boolean } = {}
): string {
  const display = response.query.display ?? "value";
  const hasPct = display !== "value";
  const headers = ["group", "series", "value"];
  if (hasPct) headers.push("percentage");
  const lines = [headers.join(",")];
  for (const cell of response.data ?? []) {
    const row: CsvRow = {
      group: cell.group,
      series: cell.series,
      value: cell.value,
    };
    if (hasPct) row.percentage = cell.percentage;
    lines.push(headers.map((h) => JSON.stringify(row[h] ?? "")).join(","));
  }
  const warning = findTruncationWarning(response.warnings);
  if (options.includeTruncationNote && warning) {
    lines.push(`"#","${warning.message.replaceAll('"', '""')}"`);
  }
  return `${lines.join("\n")}\n`;
}

export function matrixToCsvRows(model: MatrixTableModel, colLabels: Record<string, string>): string {
  const header = ["", ...model.colKeys.map((k) => colLabels[k] ?? k), "Total"];
  const lines = [header.map((h) => JSON.stringify(h)).join(",")];
  for (const row of model.rowKeys) {
    const cells = model.colKeys.map((col) => model.cells[row]?.[col]?.raw ?? "");
    lines.push([row, ...cells, model.rowTotals[row] ?? 0].map((v) => JSON.stringify(v)).join(","));
  }
  const footer = ["Total", ...model.colKeys.map((col) => model.colTotals[col] ?? 0), model.grandTotal];
  lines.push(footer.map((v) => JSON.stringify(v)).join(","));
  return `${lines.join("\n")}\n`;
}

export function downloadCsv(filename: string, body: string): void {
  const blob = new Blob([body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
