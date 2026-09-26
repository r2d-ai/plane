/**
 * @vitest-environment jsdom
 */
import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import type { TAnalyticsQueryResponseV2, TWorkspaceDashboardWidget } from "@plane/types";

vi.mock("@plane/i18n", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@plane/ui", async () => {
  const { MockCustomSelect, MockUiButton } = await import("../mocks/plane-ui");
  return {
    Button: MockUiButton,
    CustomSelect: MockCustomSelect,
    EModalPosition: { CENTER: "center" },
    EModalWidth: { LG: "lg" },
    ModalCore: ({ children, isOpen }: { children?: ReactNode; isOpen?: boolean }) =>
      isOpen ? <div data-testid="save-modal">{children}</div> : null,
  };
});

vi.mock("@plane/propel/button", async () => {
  const { MockUiButton } = await import("../mocks/plane-ui");
  return { Button: MockUiButton };
});

vi.mock("@plane/propel/toast", () => ({
  TOAST_TYPE: { SUCCESS: "success", ERROR: "error" },
  setToast: vi.fn(),
}));

vi.mock("@/components/chart/utils", () => ({
  generateExtendedColors: (colors: string[], count: number) =>
    Array.from({ length: count }, (_, index) => colors[index] ?? "#6172E8"),
}));

vi.mock("@/components/dashboards/widgets/markdown-placeholder", () => ({
  MarkdownPlaceholderWidget: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

vi.mock("@/components/analytics/v2/use-insight-value-resolver", () => ({
  useInsightValueResolver: () => (_dim: string | null, raw: string | null) => raw ?? "—",
}));

vi.mock("@plane/propel/charts/bar-chart", () => ({
  BarChart: () => <div data-testid="mock-bar-chart" />,
}));

vi.mock("@plane/propel/charts/line-chart", () => ({
  LineChart: (props: { onLineClick?: (payload: { datum: Record<string, unknown>; lineKey: string }) => void }) => (
    <button
      type="button"
      data-testid="mock-line-point"
      onClick={() => props.onLineClick?.({ datum: { __group: "state-1" }, lineKey: "count" })}
    >
      line point
    </button>
  ),
}));

vi.mock("@plane/propel/charts/pie-chart", () => ({
  PieChart: (props: { onPieClick?: (payload: { datum: Record<string, unknown> }) => void }) => (
    <button
      type="button"
      data-testid="mock-pie-slice"
      onClick={() => props.onPieClick?.({ datum: { __group: "state-1" } })}
    >
      pie slice
    </button>
  ),
}));

vi.mock("@plane/propel/empty-state", () => ({
  EmptyStateCompact: ({ title }: { title: string }) => <div data-testid="empty-state">{title}</div>,
}));

vi.mock("@/components/analytics/v2/insight-drilldown", () => ({
  default: () => <div data-testid="insight-drilldown-drawer" />,
}));

vi.mock("@/components/dashboards/widgets/widget-drilldown-drawer", () => ({
  WidgetDrilldownDrawer: () => <div data-testid="dashboard-drilldown-drawer" />,
}));

vi.mock("swr", () => ({
  default: () => ({
    data: [{ id: "dash-1", name: "Ops" }],
    isLoading: false,
    error: null,
  }),
}));

import { DashboardWidgetShell } from "@/components/dashboards/detail/widget-shell";
import { DashboardAnalyticsWidget } from "@/components/dashboards/widgets/analytics-widget";
import SaveInsightToDashboard from "@/components/analytics/v2/save-insight-to-dashboard";

const analyticsQuery = {
  version: 1 as const,
  source: "work_items" as const,
  metrics: [{ key: "work_item_count" as const }],
  dimensions: [{ key: "state" as const }],
};

const analyticsResponse = (overrides: Partial<TAnalyticsQueryResponseV2> = {}): TAnalyticsQueryResponseV2 => ({
  query: analyticsQuery,
  resolved: {
    start: null,
    end: null,
    timezone: "UTC",
    preset: "none",
    visible_project_count: 1,
  },
  schema: { metrics: [], dimensions: [] },
  data: [{ group: "state-1", series: null, value: 3, percentage: null }],
  totals: { work_item_count: 3 },
  warnings: [],
  ...overrides,
});

const widget = (widget_type: TWorkspaceDashboardWidget["widget_type"]): TWorkspaceDashboardWidget => ({
  id: "widget-1",
  title: "Widget",
  widget_type,
  query_config: { schema_version: 1, ...analyticsQuery },
  inherit_time_scope: true,
});

describe("dashboard widget shell — empty and error states (§49.6)", () => {
  test("shows batch error message and retry", () => {
    const onRetry = vi.fn();
    render(
      <DashboardWidgetShell
        widget={widget("bar")}
        batch={{ status: "error", error: { code: "ENGINE_FAILURE", message: "Engine blew up" } }}
        loading={false}
        workspaceSlug="acme"
        dashboardId="dash-1"
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Engine blew up")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "dashboard_shell.widget.retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  test("shows parse error state when batch data is not analytics-shaped", () => {
    render(
      <DashboardWidgetShell
        widget={widget("bar")}
        batch={{ status: "ok", data: { not: "analytics" } }}
        loading={false}
        workspaceSlug="acme"
        dashboardId="dash-1"
      />
    );
    expect(screen.getByText("dashboard_shell.widget.error")).toBeInTheDocument();
  });
});

describe("dashboard analytics widget — on-screen truncation and empty (§49.6)", () => {
  test("renders truncation banner from response warnings", () => {
    render(
      <DashboardAnalyticsWidget
        widget={widget("bar")}
        response={analyticsResponse({
          warnings: [{ code: "RESULT_TRUNCATED", message: "Partial aggregate" }],
        })}
        workspaceSlug="acme"
        dashboardId="dash-1"
      />
    );
    expect(screen.getByTestId("widget-truncation-banner")).toHaveTextContent("Partial aggregate");
  });

  test("renders empty state when there is no data", () => {
    render(
      <DashboardAnalyticsWidget
        widget={widget("number")}
        response={analyticsResponse({ data: [], totals: {} })}
        workspaceSlug="acme"
        dashboardId="dash-1"
      />
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent("dashboard_shell.widget.no_data");
  });

  test("line chart click opens insight drill-down drawer", () => {
    render(
      <DashboardAnalyticsWidget
        widget={widget("line")}
        response={analyticsResponse()}
        workspaceSlug="acme"
        dashboardId="dash-1"
      />
    );
    fireEvent.click(screen.getByTestId("mock-line-point"));
    expect(screen.getByTestId("insight-drilldown-drawer")).toBeInTheDocument();
  });

  test("pie chart click opens insight drill-down drawer", () => {
    render(
      <DashboardAnalyticsWidget
        widget={widget("pie")}
        response={analyticsResponse()}
        workspaceSlug="acme"
        dashboardId="dash-1"
      />
    );
    fireEvent.click(screen.getByTestId("mock-pie-slice"));
    expect(screen.getByTestId("insight-drilldown-drawer")).toBeInTheDocument();
  });
});

describe("save insight to dashboard (§49.6)", () => {
  test("save action is disabled until a query is provided", () => {
    render(<SaveInsightToDashboard query={null} defaultTitle="Insight" />);
    const button = screen.getByRole("button", { name: /save to dashboard/i });
    expect(button).toBeDisabled();
  });

  test("save action is enabled when query is present", () => {
    render(<SaveInsightToDashboard query={analyticsQuery} defaultTitle="Insight" />);
    const button = screen.getByRole("button", { name: /save to dashboard/i });
    expect(button).not.toBeDisabled();
  });
});
