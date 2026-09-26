/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * CSV serialisation for Analytics V2 results (spec §12.2, §18).
 *
 * Generic: it serialises whatever the engine returned, under the same ACL
 * scope, so an export can never widen what the viewer can see. Shared by the
 * Workspace Dashboard and Customized Insights.
 */

import type { TAnalyticsQueryResponseV2 } from "@plane/types";
import { findTruncationWarning } from "./warnings";
import type { MatrixTableModel } from "./cells";

type CsvRow = Record<string, string | number | null>;

/** §17.4 — the export carries the same columns the card shows. */
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
    const row: CsvRow = { group: cell.group, series: cell.series, value: cell.value };
    if (hasPct) row.percentage = cell.percentage;
    lines.push(headers.map((header) => JSON.stringify(row[header] ?? "")).join(","));
  }
  const warning = findTruncationWarning(response.warnings);
  if (options.includeTruncationNote && warning) {
    lines.push(`"#","${warning.message.replaceAll('"', '""')}"`);
  }
  return `${lines.join("\n")}\n`;
}

export function matrixToCsvRows(model: MatrixTableModel, colLabels: Record<string, string>): string {
  const header = ["", ...model.colKeys.map((key) => colLabels[key] ?? key), "Total"];
  const lines = [header.map((value) => JSON.stringify(value)).join(",")];
  for (const row of model.rowKeys) {
    const cells = model.colKeys.map((col) => model.cells[row]?.[col]?.raw ?? "");
    lines.push([row, ...cells, model.rowTotals[row] ?? 0].map((value) => JSON.stringify(value)).join(","));
  }
  const footer = ["Total", ...model.colKeys.map((col) => model.colTotals[col] ?? 0), model.grandTotal];
  lines.push(footer.map((value) => JSON.stringify(value)).join(","));
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
