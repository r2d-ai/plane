import { describe, expect, test } from "vitest";
import type { TWorkspaceDashboard, TWorkspaceDashboardWidget } from "@plane/types";
import {
  buildWidgetBatchQuery,
  buildWidgetBatchRequest,
  intersectStructuredFilters,
  normalizeWidgetBatchResults,
} from "@/components/analytics/v2/batch-composer";

const dashboard: TWorkspaceDashboard = {
  id: "dash-1",
  name: "Ops",
  visibility: "workspace",
  projects: ["proj-1", "proj-2"],
  filters: { state: ["open", "in-progress"], priority: ["urgent"] },
  default_time_scope: { preset: "this_quarter", basis: "created_at" },
  comparison: { type: "previous_period" },
};

const filtersOf = (query: unknown): Record<string, unknown> =>
  ((query as { filters?: unknown } | null)?.filters ?? {}) as Record<string, unknown>;

const widget = (overrides: Partial<TWorkspaceDashboardWidget> = {}): TWorkspaceDashboardWidget => ({
  id: "widget-1",
  title: "Widget",
  widget_type: "bar",
  query_config: {
    schema_version: 1,
    version: 1,
    source: "work_items",
    metrics: [{ key: "work_item_count" }],
    dimensions: [{ key: "state" }],
    filters: { state: ["open"] },
  },
  inherit_time_scope: true,
  ...overrides,
});

describe("analytics batch composition (§32.3, RD-479 B.6)", () => {
  test("scopes the card query to the dashboard projects, filters and time", () => {
    const query = buildWidgetBatchQuery(dashboard, widget(), "user-42");
    expect(query).toMatchObject({
      key: "widget-1",
      project_ids: ["proj-1", "proj-2"],
      filters: { state: ["open"], priority: ["urgent"] },
      time: { preset: "this_quarter", basis: "created_at" },
      comparison: { type: "previous_period" },
    });
  });

  test("keeps the widget's own filters and intersects the dashboard ones", () => {
    const query = buildWidgetBatchQuery(dashboard, widget(), "user-42");
    // dashboard wants open|in-progress, the card wants open -> open survives
    expect(filtersOf(query).state).toEqual(["open"]);
    expect(filtersOf(query).priority).toEqual(["urgent"]);
  });

  test("resolves the current_user token to the viewer id", () => {
    const scoped = widget({
      query_config: {
        schema_version: 1,
        version: 1,
        source: "work_items",
        metrics: [{ key: "work_item_count" }],
        dimensions: [{ key: "state" }],
        filters: { assignee_id: ["current_user"] },
      },
    });
    const query = buildWidgetBatchQuery(dashboard, scoped, "user-42");
    expect(filtersOf(query).assignee_id).toEqual(["user-42"]);
  });

  test("a card without inherited scope uses its own time scope", () => {
    const custom = widget({
      inherit_time_scope: false,
      custom_time_scope: { preset: "last_month", basis: "completed_at" },
    });
    expect(buildWidgetBatchQuery(dashboard, custom, "user-42")?.time).toEqual({
      preset: "last_month",
      basis: "completed_at",
    });
  });

  test("text cards never enter the batch and unreadable queries are dropped", () => {
    expect(buildWidgetBatchQuery(dashboard, widget({ widget_type: "markdown" }), "user-42")).toBeNull();
    expect(buildWidgetBatchQuery(dashboard, widget({ query_config: { schema_version: 1 } }), "user-42")).toBeNull();
  });

  test("batch request carries one entry per data card", () => {
    const request = buildWidgetBatchRequest(
      dashboard,
      [widget(), widget({ id: "widget-2" }), widget({ id: "widget-3", widget_type: "markdown" })],
      "user-42"
    );
    expect(request.queries.map((entry) => entry.key)).toEqual(["widget-1", "widget-2"]);
  });

  test("per-entry failure isolation survives normalisation", () => {
    const widgets = [widget(), widget({ id: "widget-2" }), widget({ id: "widget-3", widget_type: "markdown" })];
    const normalized = normalizeWidgetBatchResults(dashboard, widgets, [
      { key: "widget-1", status: "ok", data: { data: [] } },
      { key: "widget-2", status: "error", error: { code: "INVALID_QUERY", message: "Invalid query" } },
    ]);
    expect(normalized.dashboard_id).toBe("dash-1");
    expect(normalized.resolved_time).toEqual({ preset: "this_quarter", basis: "created_at" });
    expect(normalized.widgets["widget-1"]).toEqual({ status: "ok", data: { data: [] } });
    expect(normalized.widgets["widget-2"]?.status).toBe("error");
    // markdown cards are rendered statically, so an error entry is harmless
    expect(normalized.widgets["widget-3"]).toEqual({
      status: "error",
      error: { code: "INVALID_QUERY", message: "Invalid query" },
    });
  });

  test("filter intersection is key-wise", () => {
    expect(intersectStructuredFilters({ a: ["1", "2"], b: ["x"] }, { a: ["2", "3"] })).toEqual({ a: ["2"], b: ["x"] });
    expect(intersectStructuredFilters(undefined, { a: ["1"] })).toEqual({ a: ["1"] });
    expect(intersectStructuredFilters({ a: ["1"] }, undefined)).toEqual({ a: ["1"] });
  });
});
