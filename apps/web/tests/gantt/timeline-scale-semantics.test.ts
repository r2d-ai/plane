import { describe, expect, test } from "vitest";
import type { EStartOfTheWeek } from "@plane/types";
import {
  getTimelineDayWidth,
  getTimelinePeriodStart,
  getTimelineTargetDays,
  getTimelineZoomDayWidth,
} from "@/components/gantt-chart/data";

describe("timeline scale semantics", () => {
  test("anchors week to the configured start of week", () => {
    const friday = new Date(2026, 8, 25);

    expect(getTimelinePeriodStart("week", friday, 1 as EStartOfTheWeek)).toEqual(new Date(2026, 8, 21));
    expect(getTimelinePeriodStart("week", friday, 0 as EStartOfTheWeek)).toEqual(new Date(2026, 8, 20));
  });

  test("anchors month and quarter to calendar boundaries", () => {
    const date = new Date(2026, 8, 25);

    expect(getTimelinePeriodStart("month", date)).toEqual(new Date(2026, 8, 1));
    expect(getTimelinePeriodStart("quarter", date)).toEqual(new Date(2026, 6, 1));
  });

  test("uses actual calendar period lengths", () => {
    expect(getTimelineTargetDays("week", new Date(2026, 8, 25))).toBe(7);
    expect(getTimelineTargetDays("month", new Date(2026, 8, 25))).toBe(30);
    expect(getTimelineTargetDays("quarter", new Date(2026, 8, 25))).toBe(92);
  });

  test("fits a semantic period to the available viewport", () => {
    expect(getTimelineDayWidth("week", new Date(2026, 8, 25), 840)).toBe(120);
    expect(getTimelineDayWidth("month", new Date(2026, 8, 25), 900)).toBe(30);
    expect(getTimelineDayWidth("quarter", new Date(2026, 8, 25), 920)).toBe(10);
  });

  test("keeps minimum readable density on narrow viewports", () => {
    expect(getTimelineDayWidth("week", new Date(2026, 8, 25), 320)).toBe(88);
    expect(getTimelineDayWidth("month", new Date(2026, 8, 25), 320)).toBe(24);
    expect(getTimelineDayWidth("quarter", new Date(2026, 8, 25), 320)).toBe(8);
  });

  test("zooms continuously without changing the selected scale", () => {
    expect(getTimelineZoomDayWidth("month", 30, "in")).toBe(34.5);
    expect(getTimelineZoomDayWidth("month", 30, "out")).toBe(26.09);
    expect(getTimelineZoomDayWidth("quarter", 48, "in")).toBe(48);
    expect(getTimelineZoomDayWidth("month", 18, "out")).toBe(18);
  });
});
