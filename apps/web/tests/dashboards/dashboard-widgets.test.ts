import { describe, expect, test } from "vitest";
import type { TAnalyticsCell, TAnalyticsQueryResponseV2 } from "@plane/types";
import {
  aggregateCellsToCsvRows,
  buildMatrixTableModel,
  findTruncationWarning,
  formatDisplayForCell,
  hasTruncatedResult,
  resolveViewerFilterPlaceholders,
  WARNING_RESULT_TRUNCATED,
} from "@/components/dashboards/widgets/analytics-data";

describe("dashboard widget analytics (§49.6)", () => {
  test("percentage display uses cell percentage", () => {
    const cell: TAnalyticsCell = { group: "a", series: null, value: 4, percentage: 0.25, display: "4 · 25.0%" };
    expect(formatDisplayForCell(cell, "percentage")).toBe("25.0%");
    expect(formatDisplayForCell(cell, "value_and_percentage")).toBe("4 · 25.0%");
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
