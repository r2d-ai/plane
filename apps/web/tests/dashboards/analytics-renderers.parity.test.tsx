/**
 * @vitest-environment jsdom
 */
/**
 * Render-equality guard for the `analytics/v2/renderers` extraction (RD-479 /
 * spec §12.1).
 *
 * `__fixtures__/renderer-baseline.json` was captured from the pre-extraction
 * `DashboardAnalyticsWidget` — the single `analytics-widget.tsx` module that
 * held every renderer primitive inline. Re-run with
 * `CAPTURE_RENDER_BASELINE=1` to regenerate it; the committed file is the
 * evidence that the move changed nothing but file location.
 *
 * Each case records:
 *  - `html` — the whole widget shell (header, truncation banner, body);
 *  - `body` — the renderer output only, so the extracted primitives can also be
 *    asserted one-by-one against the same bytes.
 *
 * RD-483 deleted the builder, so the shell itself is gone and the `html` slice
 * can no longer be re-rendered. What survives is the half that matters: every
 * extracted primitive still mounts standalone and emits the same bytes the
 * builder emitted, so the v3 card calls into an unchanged renderer contract.
 */

import { render, screen } from "@testing-library/react";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ReactNode } from "react";
import { describe, expect, test, vi } from "vitest";
import type { TAnalyticsQueryResponseV2, TAnalyticsWarning, TWorkspaceDashboardWidget } from "@plane/types";

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@plane/propel/button", async () => {
  const { MockUiButton } = await import("../mocks/plane-ui");
  return { Button: MockUiButton };
});

vi.mock("@/components/chart/utils", () => ({
  generateExtendedColors: (colors: string[], count: number) =>
    Array.from({ length: count }, (_, index) => colors[index] ?? "#6172E8"),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

vi.mock("@/components/analytics/v2/use-insight-value-resolver", () => ({
  useInsightValueResolver: () => (_dim: string | null, raw: string | null) => raw ?? "—",
}));

/**
 * Chart mocks serialise the config they are handed into the DOM so the golden
 * bytes cover the computed `data` / `bars` / `lines` / `cells` props too — not
 * just the fact that a chart was mounted. `vi.mock` factories are hoisted, so
 * the digest is repeated inside each of them.
 */
/* oxlint-disable eslint-plugin-unicorn/consistent-function-scoping */
vi.mock("@plane/propel/charts/bar-chart", () => {
  const digest = (props: Record<string, unknown>) =>
    JSON.stringify(props, (_key, value) => (typeof value === "function" ? "[fn]" : value));
  return {
    BarChart: (props: Record<string, unknown>) => <div data-testid="mock-bar-chart">{digest(props)}</div>,
  };
});

vi.mock("@plane/propel/charts/line-chart", () => {
  const digest = (props: Record<string, unknown>) =>
    JSON.stringify(props, (_key, value) => (typeof value === "function" ? "[fn]" : value));
  return {
    LineChart: (props: Record<string, unknown>) => <div data-testid="mock-line-chart">{digest(props)}</div>,
  };
});

vi.mock("@plane/propel/charts/pie-chart", () => {
  const digest = (props: Record<string, unknown>) =>
    JSON.stringify(props, (_key, value) => (typeof value === "function" ? "[fn]" : value));
  return {
    PieChart: (props: Record<string, unknown>) => <div data-testid="mock-pie-chart">{digest(props)}</div>,
  };
});

vi.mock("@plane/propel/empty-state", () => ({
  EmptyStateCompact: ({ title }: { title: string }) => <div data-testid="empty-state">{title}</div>,
}));

vi.mock("@/components/analytics/v2/insight-drilldown", () => ({
  default: () => <div data-testid="insight-drilldown-drawer" />,
}));
/* oxlint-enable eslint-plugin-unicorn/consistent-function-scoping */

import { CHART_COLOR_PALETTES } from "@plane/constants";
import { buildInsightChartData, buildMatrixTableModel } from "@/components/analytics/v2/cells";
import { METRIC_LABELS, metricUnit } from "@/components/analytics/v2/mapping";
import {
  AggregateTableRenderer,
  BarRenderer,
  DonutRenderer,
  GaugeRenderer,
  LineRenderer,
  MatrixRenderer,
  NumberRenderer,
  PieRenderer,
  WidgetTruncationBanner,
  WorkItemTableRenderer,
} from "@/components/analytics/v2/renderers";

const BASELINE_PATH = join(dirname(fileURLToPath(import.meta.url)), "__fixtures__", "renderer-baseline.json");

type ParityCase = {
  name: string;
  widget_type: TWorkspaceDashboardWidget["widget_type"];
  style?: Record<string, unknown>;
  warnings?: TAnalyticsWarning[];
};

/** Widget kinds that route through a distinct renderer primitive. */
const CASES: ParityCase[] = [
  { name: "number", widget_type: "number" },
  { name: "counter", widget_type: "counter" },
  { name: "statistics", widget_type: "statistics" },
  { name: "gauge", widget_type: "gauge" },
  { name: "bar", widget_type: "bar" },
  { name: "line", widget_type: "line" },
  { name: "pie", widget_type: "pie" },
  { name: "donut", widget_type: "donut" },
  { name: "donut-progress", widget_type: "donut", style: { donut_variant: "progress" } },
  { name: "matrix", widget_type: "matrix" },
  { name: "table", widget_type: "table" },
  { name: "bar-stacked", widget_type: "bar", style: { bar_mode: "stacked" } },
  {
    name: "bar-truncated",
    widget_type: "bar",
    warnings: [{ code: "RESULT_TRUNCATED", message: "Partial aggregate" }],
  },
  { name: "unsupported", widget_type: "text" },
];

const query = {
  version: 1 as const,
  source: "work_items" as const,
  metrics: [{ key: "work_item_count" as const }],
  dimensions: [{ key: "state" as const }, { key: "assignee" as const }],
  time: { preset: "this_quarter" as const, basis: "created_at" as const },
  comparison: { type: "none" as const },
  normalization: "none" as const,
  display: "value" as const,
  filters: {},
};

const response: TAnalyticsQueryResponseV2 = {
  query: query as TAnalyticsQueryResponseV2["query"],
  resolved: { start: null, end: null, timezone: "UTC", preset: "this_quarter", visible_project_count: 2 },
  schema: { metrics: [], dimensions: [] },
  data: [
    { group: "state-1", series: "user-a", value: 12, percentage: 0.6, display: "12" },
    { group: "state-1", series: "user-b", value: 8, percentage: 0.4, display: "8" },
    { group: "state-2", series: "user-a", value: 5, percentage: null, display: "5" },
    { group: "state-2", series: "user-b", value: 0, percentage: null, display: "0" },
  ],
  totals: { work_item_count: 25, completed_work_items: 10 },
  warnings: [],
};

type Baseline = Record<string, { html: string; body: string }>;

const baseline: Baseline = existsSync(BASELINE_PATH)
  ? (JSON.parse(readFileSync(BASELINE_PATH, "utf8")) as Baseline)
  : ({} as Baseline);

if (process.env.CAPTURE_RENDER_BASELINE === "1") {
  // The fixture is frozen history captured from the pre-move builder. With the
  // shell deleted there is nothing left to re-render, so it is not regenerable.
  console.warn(`renderer baseline is frozen pre-move history; not regenerable after RD-483`);
}

describe("analytics renderers — the frozen baseline covers every renderer kind (RD-479, §12.1)", () => {
  test("baseline fixture covers every renderer kind", () => {
    expect(Object.keys(baseline).toSorted()).toEqual(CASES.map((entry) => entry.name).toSorted());
  });

  test("every baseline case recorded a non-empty renderer body", () => {
    for (const entry of CASES) {
      expect(baseline[entry.name]?.body.length ?? 0, entry.name).toBeGreaterThan(0);
    }
  });
});

/*
 * Mounting each extracted primitive on its own against the frozen baseline
 * proves the v3 card can call them directly and get the very same bytes the
 * builder produced before the move.
 */
const METRIC_KEY = "work_item_count" as const;
const UNIT = metricUnit(METRIC_KEY);
const RESOLVE = (_dim: string | null, raw: string | null) => raw ?? "—";

const chartData = buildInsightChartData({
  cells: response.data ?? [],
  metricLabel: METRIC_LABELS[METRIC_KEY] ?? METRIC_KEY,
  hasBreakdown: true,
  display: "value",
  unit: UNIT,
  resolveGroup: (raw) => RESOLVE(null, raw),
  resolveSeries: (raw) => RESOLVE(null, raw),
});

const matrixModel = buildMatrixTableModel(response.data ?? [], "value", UNIT);
const baseColors = CHART_COLOR_PALETTES[0]?.light ?? [];
const noop = () => undefined;

const DIRECT: { name: string; element: ReactNode; baseline: string }[] = [
  {
    name: "number",
    element: <NumberRenderer value={response.totals?.[METRIC_KEY] ?? 0} unit={UNIT} />,
    baseline: "number",
  },
  {
    name: "aggregate-table",
    element: <AggregateTableRenderer totals={response.totals ?? {}} />,
    baseline: "statistics",
  },
  {
    name: "gauge",
    element: <GaugeRenderer response={response} metricKey={METRIC_KEY} unit={UNIT} />,
    baseline: "gauge",
  },
  {
    name: "bar",
    element: (
      <BarRenderer
        chartData={chartData}
        barMode="stacked"
        baseColors={baseColors}
        onBarClick={noop}
        canDrilldown={true}
      />
    ),
    baseline: "bar",
  },
  {
    name: "line",
    element: (
      <LineRenderer
        chartData={chartData}
        baseColors={baseColors}
        hasBreakdown={true}
        canDrilldown={true}
        onPointClick={noop}
      />
    ),
    baseline: "line",
  },
  {
    name: "pie",
    element: <PieRenderer chartData={chartData} baseColors={baseColors} canDrilldown={true} onSliceClick={noop} />,
    baseline: "pie",
  },
  {
    name: "donut",
    element: (
      <DonutRenderer
        chartData={chartData}
        progress={false}
        baseColors={baseColors}
        canDrilldown={true}
        onSliceClick={noop}
      />
    ),
    baseline: "donut",
  },
  {
    name: "donut (progress variant)",
    element: (
      <DonutRenderer
        chartData={chartData}
        progress={true}
        baseColors={baseColors}
        canDrilldown={true}
        onSliceClick={noop}
      />
    ),
    baseline: "donut-progress",
  },
  {
    name: "matrix",
    element: (
      <MatrixRenderer
        model={matrixModel}
        resolveRow={(key) => RESOLVE(null, key)}
        resolveCol={(key) => RESOLVE(null, key)}
        onCellClick={noop}
        canDrilldown={true}
      />
    ),
    baseline: "matrix",
  },
  {
    name: "work-item-table",
    element: (
      <WorkItemTableRenderer
        workspaceSlug="acme"
        dashboardId="dash-parity"
        widgetId="widget-parity"
        chartData={chartData}
        canDrilldown={true}
        onDrilldown={noop}
      />
    ),
    baseline: "table",
  },
];

describe("analytics renderers — each primitive mounts standalone with unchanged output (RD-479)", () => {
  for (const entry of DIRECT) {
    test(`${entry.name} reproduces the pre-move bytes`, () => {
      const { container } = render(entry.element);
      expect(container.innerHTML).toBe(baseline[entry.baseline]?.body);
    });
  }
});

/*
 * The banner is the one primitive whose bytes legitimately changed in D.8: its
 * default copy moved from the deleted `dashboard_shell.widget.truncated` to
 * `dashboard_v3.card.truncated`. It still renders inside the same wrapper, and
 * an explicit engine message still wins over the default.
 */
describe("truncation banner (RD-483 D.8)", () => {
  test("falls back to the v3 copy when the engine sends no message", () => {
    render(<WidgetTruncationBanner warnings={[{ code: "RESULT_TRUNCATED", message: "" }]} />);
    expect(screen.getByTestId("widget-truncation-banner").textContent).toContain("dashboard_v3.card.truncated");
  });

  test("its wrapper markup is still byte-identical to the frozen baseline", () => {
    const { container } = render(
      <WidgetTruncationBanner warnings={[{ code: "RESULT_TRUNCATED", message: "Partial aggregate" }]} />
    );
    const recorded = baseline["bar-truncated"]?.html ?? "";
    const wrapper = recorded.match(/<div class="flex items-start gap-2[^]*?<\/span><\/div>/)?.[0] ?? "";
    expect(wrapper).not.toBe("");
    expect(container.innerHTML).toBe(wrapper);
  });

  test("an explicit engine message still wins over the default copy", () => {
    render(<WidgetTruncationBanner warnings={[{ code: "RESULT_TRUNCATED", message: "Partial aggregate" }]} />);
    expect(screen.getByTestId("widget-truncation-banner").textContent).toContain("Partial aggregate");
  });
});
