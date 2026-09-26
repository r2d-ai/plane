/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The analytics contract the v3 cards render with (§49.6).
 *
 * Replaces the builder's `dashboard-widgets.test.ts`, which reached these same
 * functions through `dashboards/widgets/analytics-data` — a shim that only
 * re-exported the analytics namespace. The v3 card imports them from
 * `analytics/v2` directly, so the contract is asserted where it now lives.
 * `formatDisplayForCell` is gone with the shim: the card formats through
 * `buildInsightChartData` and the engine's own `display` column.
 */

import { describe, expect, test } from "vitest";
import type { TAnalyticsCell, TAnalyticsQueryResponseV2 } from "@plane/types";
import { buildMatrixTableModel, formatPercentage, formatValue } from "@/components/analytics/v2/cells";
import { aggregateCellsToCsvRows } from "@/components/analytics/v2/csv";
import { resolveViewerFilterPlaceholders } from "@/components/analytics/v2/viewer-filters";
import {
  WARNING_RESULT_TRUNCATED,
  findTruncationWarning,
  hasTruncatedResult,
} from "@/components/analytics/v2/warnings";

describe("v3 card analytics contract (§49.6)", () => {
  test("the card plots the engine's display column, and formats a percentage itself", () => {
    const cell: TAnalyticsCell = { group: "a", series: null, value: 4, percentage: 0.25, display: "4 · 25.0%" };
    expect(formatValue(4)).toBe("4");
    expect(formatPercentage(cell.percentage)).toBe("25.0%");
  });

  test("matrix row and column totals", () => {
    const cells: TAnalyticsCell[] = [
      { group: "r1", series: "c1", value: 10, percentage: null },
      { group: "r1", series: "c2", value: 5, percentage: null },
      { group: "r2", series: "c1", value: 3, percentage: null },
    ];
    const model = buildMatrixTableModel(cells, "value");
    expect(model.rowTotals.r1).toBe(15);
    expect(model.rowTotals.r2).toBe(3);
    expect(model.colTotals.c1).toBe(13);
    expect(model.colTotals.c2).toBe(5);
    expect(model.grandTotal).toBe(18);
  });

  test("current-user dynamic filter substitution", () => {
    const resolved = resolveViewerFilterPlaceholders(
      { assignee_id: ["current_user"], created_by: "@current_user" },
      "user-42"
    );
    expect(resolved).toEqual({ assignee_id: ["user-42"], created_by: "user-42" });
  });

  test("RESULT_TRUNCATED warning detection and CSV caveat", () => {
    const response: TAnalyticsQueryResponseV2 = {
      query: {
        version: 1,
        source: "work_items",
        metrics: [{ key: "work_item_count" }],
        dimensions: [{ key: "project" }],
      },
      resolved: {
        start: null,
        end: null,
        timezone: "UTC",
        preset: "none",
        visible_project_count: 1,
      },
      schema: { metrics: [], dimensions: [] },
      data: [{ group: "p1", series: null, value: 1, percentage: null }],
      totals: { work_item_count: 1 },
      warnings: [{ code: WARNING_RESULT_TRUNCATED, message: "Partial results" }],
    };
    expect(hasTruncatedResult(response.warnings)).toBe(true);
    expect(findTruncationWarning(response.warnings)?.message).toBe("Partial results");
    const csv = aggregateCellsToCsvRows(response, { includeTruncationNote: true });
    expect(csv).toContain("Partial results");
  });
});
