/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";
import type { TAnalyticsCell } from "@plane/types";
import {
  buildDrilldownRequest,
  buildInsightChartData,
  buildInsightQuery,
  formatDateBucket,
  formatPercentage,
  formatValue,
  isDateDimension,
  reconcileDisplayNormalization,
  toMetricKey,
  toTimePreset,
} from "@/components/analytics/v2";

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@/hooks/store/use-analytics", () => ({
  useAnalytics: () => ({
    selectedDuration: "last_30_days",
    selectedDateBasis: "created_at",
    selectedProjects: [],
    selectedCycle: null,
    selectedModule: null,
  }),
}));

vi.mock("@/components/analytics/select/analytics-params", () => ({
  AnalyticsSelectParams: () => <div data-testid="analytics-select-params" />,
}));

vi.mock("@/components/analytics/work-items/insight-chart", () => ({
  default: () => <div data-testid="insight-chart" />,
}));

import CustomizedInsights from "@/components/analytics/work-items/customized-insights";

const base = {
  xAxis: ChartXAxisProperty.LABELS,
  yAxis: ChartYAxisMetric.ESTIMATE_POINT_COUNT,
  groupBy: ChartXAxisProperty.ASSIGNEES,
};

const identity = (raw: string | null) => raw ?? "None";

describe("Customized Insights V2 query builder (§18, §11)", () => {
  test("builds the Label x Assignee query (§50.4)", () => {
    const query = buildInsightQuery(base);

    expect(query).not.toBeNull();
    expect(query?.dimensions).toEqual([{ key: "labels" }, { key: "assignees" }]);
    expect(query?.source).toBe("work_items");
    expect(query?.version).toBe(1);
  });

  test("supports Work item count and Estimate points (§50.5)", () => {
    expect(toMetricKey(ChartYAxisMetric.WORK_ITEM_COUNT)).toBe("work_item_count");
    expect(toMetricKey(ChartYAxisMetric.ESTIMATE_POINT_COUNT)).toBe("estimate_points");

    const count = buildInsightQuery({ ...base, yAxis: ChartYAxisMetric.WORK_ITEM_COUNT });
    expect(count?.metrics).toEqual([{ key: "work_item_count" }]);
    const points = buildInsightQuery({ ...base, yAxis: ChartYAxisMetric.ESTIMATE_POINT_COUNT });
    expect(points?.metrics).toEqual([{ key: "estimate_points" }]);
  });

  test("passes the display mode through untouched (§50.6)", () => {
    expect(buildInsightQuery({ ...base, display: "value" })?.display).toBe("value");
    expect(buildInsightQuery({ ...base, display: "percentage" })?.display).toBe("percentage");
    expect(buildInsightQuery({ ...base, display: "value_and_percentage" })?.display).toBe("value_and_percentage");
  });

  test("answers both normalisation questions (§50.7)", () => {
    // "Who contributes to this product?" → per label row.
    expect(buildInsightQuery({ ...base, normalization: "group_total" })?.normalization).toBe("group_total");
    // "Where is this assignee's workload allocated?" → per assignee column.
    expect(buildInsightQuery({ ...base, normalization: "series_total" })?.normalization).toBe("series_total");
    expect(buildInsightQuery({ ...base, normalization: "grand_total" })?.normalization).toBe("grand_total");
  });

  test("sends the selected allocation (§50.8, §15)", () => {
    expect(buildInsightQuery({ ...base, allocation: "split_equal" })?.allocation).toBe("split_equal");
    expect(buildInsightQuery({ ...base, allocation: "full_credit" })?.allocation).toBe("full_credit");
  });

  test("percentage display forces a normalisation base (§17)", () => {
    expect(reconcileDisplayNormalization("percentage", "none")).toEqual({
      display: "percentage",
      normalization: "grand_total",
    });
    expect(reconcileDisplayNormalization("value", "none")).toEqual({ display: "value", normalization: "none" });
    expect(reconcileDisplayNormalization("value_and_percentage", "series_total")).toEqual({
      display: "value_and_percentage",
      normalization: "series_total",
    });

    const query = buildInsightQuery({ ...base, display: "percentage", normalization: "none" });
    expect(query?.normalization).toBe("grand_total");
    expect(query?.display).toBe("percentage");
  });

  test("maps the header time range onto a V2 preset (§9)", () => {
    expect(toTimePreset("yesterday")).toBe("yesterday");
    expect(toTimePreset("last_7_days")).toBe("last_7_days");
    expect(toTimePreset("last_30_days")).toBe("last_30_days");
    // The legacy vocabulary has no `last_90_days`; V2 has no `last_3_months`.
    expect(toTimePreset("last_3_months")).toBe("last_90_days");
    expect(toTimePreset(undefined)).toBe("last_30_days");

    const query = buildInsightQuery({ ...base, duration: "last_3_months" });
    expect(query?.time?.preset).toBe("last_90_days");
  });

  test("sends the selected date basis (§9.1)", () => {
    expect(buildInsightQuery({ ...base, dateBasis: "lifecycle_overlap" })?.time?.basis).toBe("lifecycle_overlap");
    expect(buildInsightQuery({ ...base, dateBasis: "completed_at" })?.time?.basis).toBe("completed_at");
    expect(buildInsightQuery(base)?.time?.basis).toBe("created_at");
  });

  test("date grouping is only sent for a date dimension, and includes quarter (§9.3)", () => {
    expect(buildInsightQuery({ ...base, dateGrouping: "quarter" })?.time?.group).toBeUndefined();

    const byQuarter = buildInsightQuery({
      xAxis: ChartXAxisProperty.CREATED_AT,
      yAxis: ChartYAxisMetric.WORK_ITEM_COUNT,
      dateGrouping: "quarter",
    });
    expect(byQuarter?.dimensions).toEqual([{ key: "created_date" }]);
    expect(byQuarter?.time?.group).toBe("quarter");
    // A calendar axis can exceed the categorical cap but never the §40.1 cap.
    expect(byQuarter?.limit).toBe(100);
    expect(isDateDimension("created_date")).toBe(true);
    expect(isDateDimension("labels")).toBe(false);
  });

  test("categorical queries stay inside the group cap", () => {
    expect(buildInsightQuery(base)?.limit).toBe(50);
  });

  test("carries project scope and cycle/module filters", () => {
    const query = buildInsightQuery({
      ...base,
      projectIds: ["p1", "p2"],
      cycleId: "c1",
      moduleId: "m1",
    });
    expect(query?.project_ids).toEqual(["p1", "p2"]);
    expect(query?.filters).toEqual({ cycle_id: ["c1"], module_id: ["m1"] });
  });

  test("returns null when the selection has no P0 dimension", () => {
    expect(buildInsightQuery({ ...base, xAxis: ChartXAxisProperty.EPICS })).toBeNull();
  });

  test("the query is a self-contained widget config (§18.2 save to dashboard)", () => {
    const query = buildInsightQuery({ ...base, display: "value_and_percentage", allocation: "split_equal" });
    // Everything the renderer needs is in the query itself — no snapshot.
    expect(query).toMatchObject({
      version: 1,
      source: "work_items",
      metrics: [{ key: "estimate_points" }],
      dimensions: [{ key: "labels" }, { key: "assignees" }],
      display: "value_and_percentage",
      allocation: "split_equal",
    });
    expect(Object.keys(query ?? {}).toSorted()).toEqual(
      [
        "allocation",
        "comparison",
        "dimensions",
        "display",
        "filters",
        "limit",
        "metrics",
        "normalization",
        "project_ids",
        "sort",
        "source",
        "time",
        "version",
      ].toSorted()
    );
  });
});

describe("cell → chart data (§17.4, §50.6)", () => {
  const cells: TAnalyticsCell[] = [
    { group: "label-a", series: "alex", value: 18, percentage: 0.429, display: "18 pts · 42.9%" },
    { group: "label-a", series: "bob", value: 8, percentage: 0.19, display: "8 pts · 19.0%" },
    { group: "label-b", series: "alex", value: 10, percentage: 0.238, display: "10 pts · 23.8%" },
  ];

  test("builds one stacked row per group with a series key (§50.4)", () => {
    const data = buildInsightChartData({
      cells,
      metricLabel: "Estimate points",
      hasBreakdown: true,
      display: "value",
      resolveGroup: identity,
      resolveSeries: identity,
    });

    expect(data.schema).toEqual({ alex: "alex", bob: "bob" });
    expect(data.rows.map((row) => row.name)).toEqual(["label-a", "label-b"]);
    expect(data.rows[0]?.alex).toBe(18);
    expect(data.rows[0]?.bob).toBe(8);
    expect(data.rows[0]?.__total).toBe(26);
    expect(data.rows[1]?.bob ?? 0).toBe(0);
  });

  test("value mode plots raw values (§50.6)", () => {
    const data = buildInsightChartData({
      cells,
      metricLabel: "Estimate points",
      hasBreakdown: true,
      display: "value",
      resolveGroup: identity,
      resolveSeries: identity,
    });
    expect(data.rows[0]?.alex).toBe(18);
    expect(data.rows[0]?.__display.alex).toBe("18 pts · 42.9%");
  });

  test("percentage mode plots the normalised share (§50.6)", () => {
    const data = buildInsightChartData({
      cells,
      metricLabel: "Estimate points",
      hasBreakdown: true,
      display: "percentage",
      resolveGroup: identity,
      resolveSeries: identity,
    });
    expect(data.rows[0]?.alex).toBeCloseTo(0.429);
    expect(data.rows[0]?.__raw.alex).toBe(18);
    expect(data.rows[0]?.__pct.alex).toBeCloseTo(0.429);
  });

  test("value + percentage plots the value and keeps both columns", () => {
    const data = buildInsightChartData({
      cells,
      metricLabel: "Estimate points",
      hasBreakdown: true,
      display: "value_and_percentage",
      resolveGroup: identity,
      resolveSeries: identity,
    });
    expect(data.rows[0]?.alex).toBe(18);
    expect(data.rows[0]?.__pct.alex).toBeCloseTo(0.429);
  });

  test("without a breakdown there is a single metric column", () => {
    const data = buildInsightChartData({
      cells: [{ group: "label-a", series: "-", value: 26, percentage: null }],
      metricLabel: "Estimate points",
      hasBreakdown: false,
      display: "value",
      unit: " pts",
      resolveGroup: identity,
      resolveSeries: identity,
    });
    expect(data.hasBreakdown).toBe(false);
    expect(data.seriesKeys).toEqual(["count"]);
    expect(data.schema).toEqual({ count: "Estimate points" });
    expect(data.rows[0]?.count).toBe(26);
    expect(data.rows[0]?.__display.count).toBe("26 pts");
  });

  test("applies the resolved display labels (§50.4)", () => {
    const data = buildInsightChartData({
      cells: [
        {
          group: "11111111-1111-1111-1111-111111111111",
          series: "22222222-2222-2222-2222-222222222222",
          value: 1,
          percentage: null,
        },
      ],
      metricLabel: "Work item count",
      hasBreakdown: true,
      display: "value",
      resolveGroup: () => "Game A",
      resolveSeries: () => "Alex",
    });
    expect(data.rows[0]?.name).toBe("Game A");
    expect(data.schema).toEqual({ "22222222-2222-2222-2222-222222222222": "Alex" });
    // The raw key survives — it is what the drill-down selection needs (§25).
    expect(data.rows[0]?.__group).toBe("11111111-1111-1111-1111-111111111111");
  });

  test("date buckets read chronologically (§9.3)", () => {
    const data = buildInsightChartData({
      cells: [
        { group: "2026-09", series: "-", value: 3, percentage: null },
        { group: "2026-01", series: "-", value: 5, percentage: null },
        { group: "2026-07", series: "-", value: 1, percentage: null },
      ],
      metricLabel: "Work item count",
      hasBreakdown: false,
      display: "value",
      dateGrouping: "month",
      resolveGroup: (raw) => formatDateBucket(raw ?? "", "month"),
      resolveSeries: identity,
    });
    expect(data.rows.map((row) => row.name)).toEqual(["Jan", "Jul", "Sep"]);
  });
});

describe("drill-down selection (§25)", () => {
  const query = buildInsightQuery(base)!;

  test("targets the clicked cell only", () => {
    const request = buildDrilldownRequest(
      { query, primaryKey: "labels", groupValue: "label-a", seriesValue: "alex" },
      { seriesKey: "assignees" }
    );
    expect(request?.selection).toEqual({ labels: "label-a", assignees: "alex" });
    expect(request?.query).toEqual(query);
    expect(request?.page).toBe(1);
    expect(request?.page_size).toBe(25);
  });

  test("without a breakdown only the primary dimension is sent", () => {
    const request = buildDrilldownRequest(
      { query, primaryKey: "labels", groupValue: "label-a", seriesValue: null },
      { seriesKey: null }
    );
    expect(request?.selection).toEqual({ labels: "label-a" });
  });

  test("refuses cells with no value instead of widening the result set", () => {
    expect(
      buildDrilldownRequest(
        { query, primaryKey: "labels", groupValue: null, seriesValue: "alex" },
        { seriesKey: "assignees" }
      )
    ).toBeNull();
    expect(
      buildDrilldownRequest(
        { query, primaryKey: "labels", groupValue: "", seriesValue: "alex" },
        { seriesKey: "assignees" }
      )
    ).toBeNull();
    expect(
      buildDrilldownRequest(
        { query, primaryKey: "labels", groupValue: "label-a", seriesValue: "" },
        { seriesKey: "assignees" }
      )
    ).toBeNull();
  });

  test("paginates", () => {
    const request = buildDrilldownRequest(
      { query, primaryKey: "labels", groupValue: "label-a" },
      { page: 3, pageSize: 50 }
    );
    expect(request?.page).toBe(3);
    expect(request?.page_size).toBe(50);
  });
});

describe("display formatting (§17.4, §9.3)", () => {
  test("formats values with the metric unit", () => {
    expect(formatValue(18, " pts")).toBe("18 pts");
    expect(formatValue(18.5, " pts")).toBe("18.50 pts");
    expect(formatValue(4)).toBe("4");
  });

  test("formats percentages to one decimal", () => {
    expect(formatPercentage(0.429)).toBe("42.9%");
    expect(formatPercentage(0)).toBe("0.0%");
    expect(formatPercentage(null)).toBe("—");
    expect(formatPercentage(undefined)).toBe("—");
  });

  test("formats every date grouping including quarter (§9.3)", () => {
    expect(formatDateBucket("2019-07-12", "day")).toBe("Jul 12, 2019");
    expect(formatDateBucket("2019-07", "month")).toBe("Jul, 2019");
    expect(formatDateBucket("2026-Q3", "quarter")).toBe("Q3 2026");
    expect(formatDateBucket("2026-Q1", "quarter")).toBe("Q1 2026");
    expect(formatDateBucket("2026", "year")).toBe("2026");
    expect(formatDateBucket("nonsense", "month")).toBe("nonsense");
  });
});

describe("Customized Insights V2 — the builder action is gone (§18.1, RD-483)", () => {
  test("renders the chart and the query controls with no Save-to-dashboard control", () => {
    render(<CustomizedInsights />);

    expect(screen.getByTestId("insight-chart")).toBeTruthy();
    expect(screen.getByTestId("analytics-select-params")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /save to dashboard/i })).toBeNull();
  });

  test("a peek-view render carries no builder affordance either", () => {
    render(<CustomizedInsights peekView isEpic />);
    expect(screen.queryByRole("button", { name: /save to dashboard/i })).toBeNull();
  });
});
