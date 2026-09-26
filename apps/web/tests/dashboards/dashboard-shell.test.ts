import { describe, expect, test } from "vitest";
import type { TWorkspaceDashboardWidget } from "@plane/types";
import { filterDashboardsByTab } from "@/components/dashboards/list/filter";
import {
  buildLayoutPersistencePayload,
  mobileStackOrder,
  moveGridItem,
  normalizeGridLayout,
  resizeGridItem,
} from "@/components/dashboards/layout";
import { isStaticWidgetType, resolveWidgetTimeScope } from "@/components/dashboards/time-scope";

const widget = (id: string, layout?: { x: number; y: number; w: number; h: number }): TWorkspaceDashboardWidget => ({
  id,
  title: id,
  widget_type: "markdown",
  query_config: { schema_version: 1, version: 1, metrics: [{ key: "work_item_count" }], dimensions: [] },
  inherit_time_scope: true,
  layout_config: layout,
});

describe("dashboard shell layout (§49.6)", () => {
  test("edit/view persistence payload includes layout_config", () => {
    const layout = normalizeGridLayout([
      widget("a", { x: 0, y: 0, w: 4, h: 3 }),
      widget("b", { x: 4, y: 0, w: 4, h: 3 }),
    ]);
    const payload = buildLayoutPersistencePayload(layout);
    expect(payload).toHaveLength(2);
    expect(payload[0]?.layout_config?.w).toBe(4);
  });

  test("drag/resize updates grid coordinates", () => {
    const base = normalizeGridLayout([widget("a", { x: 0, y: 0, w: 4, h: 3 })]);
    const moved = moveGridItem(base, "a", 4, 2);
    expect(moved[0]?.x).toBe(4);
    expect(moved[0]?.y).toBe(2);
    const resized = resizeGridItem(moved, "a", 6, 4);
    expect(resized[0]?.w).toBe(6);
    expect(resized[0]?.h).toBe(4);
  });

  test("mobile stacking preserves deterministic order", () => {
    const layout = normalizeGridLayout([
      widget("bottom", { x: 0, y: 4, w: 4, h: 3 }),
      widget("top", { x: 0, y: 0, w: 4, h: 3 }),
    ]);
    expect(mobileStackOrder(layout)).toEqual(["top", "bottom"]);
  });
});

describe("dashboard time inheritance (§50.3)", () => {
  test("inheriting widgets use dashboard default time scope", () => {
    const scope = resolveWidgetTimeScope(
      { preset: "this_quarter" },
      { inherit_time_scope: true, custom_time_scope: null }
    );
    expect(scope?.preset).toBe("this_quarter");
  });

  test("widget override uses custom_time_scope", () => {
    const scope = resolveWidgetTimeScope(
      { preset: "this_quarter" },
      { inherit_time_scope: false, custom_time_scope: { preset: "last_7_days" } }
    );
    expect(scope?.preset).toBe("last_7_days");
  });
});

describe("dashboard list tabs (§6)", () => {
  test("filters favorites and mine", () => {
    const rows = [
      { id: "1", name: "A", visibility: "private" as const, owner: "u1", is_favorited: true },
      { id: "2", name: "B", visibility: "workspace" as const, owner: "u2", is_favorited: false },
    ];
    expect(filterDashboardsByTab(rows, "mine", "u1")).toHaveLength(1);
    expect(filterDashboardsByTab(rows, "favorites", "u1")).toHaveLength(1);
    expect(filterDashboardsByTab(rows, "shared", "u1")).toHaveLength(1);
  });
});

describe("static widget types", () => {
  test("markdown widgets skip analytics renderer path", () => {
    expect(isStaticWidgetType("markdown")).toBe(true);
    expect(isStaticWidgetType("bar")).toBe(false);
  });
});
