/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// types
import type { WeekMonthDataType, ChartDataType, TGanttViews } from "@plane/types";
import { EStartOfTheWeek } from "@plane/types";

// constants
export const generateWeeks = (startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY): WeekMonthDataType[] => [
  ...weeks.slice(startOfWeek),
  ...weeks.slice(0, startOfWeek),
];

export const weeks: WeekMonthDataType[] = [
  { key: 0, shortTitle: "sun", title: "sunday", abbreviation: "Su" },
  { key: 1, shortTitle: "mon", title: "monday", abbreviation: "M" },
  { key: 2, shortTitle: "tue", title: "tuesday", abbreviation: "T" },
  { key: 3, shortTitle: "wed", title: "wednesday", abbreviation: "W" },
  { key: 4, shortTitle: "thurs", title: "thursday", abbreviation: "Th" },
  { key: 5, shortTitle: "fri", title: "friday", abbreviation: "F" },
  { key: 6, shortTitle: "sat", title: "saturday", abbreviation: "Sa" },
];

export const months: WeekMonthDataType[] = [
  { key: 0, shortTitle: "jan", title: "january", abbreviation: "Jan" },
  { key: 1, shortTitle: "feb", title: "february", abbreviation: "Feb" },
  { key: 2, shortTitle: "mar", title: "march", abbreviation: "Mar" },
  { key: 3, shortTitle: "apr", title: "april", abbreviation: "Apr" },
  { key: 4, shortTitle: "may", title: "may", abbreviation: "May" },
  { key: 5, shortTitle: "jun", title: "june", abbreviation: "Jun" },
  { key: 6, shortTitle: "jul", title: "july", abbreviation: "Jul" },
  { key: 7, shortTitle: "aug", title: "august", abbreviation: "Aug" },
  { key: 8, shortTitle: "sept", title: "september", abbreviation: "Sept" },
  { key: 9, shortTitle: "oct", title: "october", abbreviation: "Oct" },
  { key: 10, shortTitle: "nov", title: "november", abbreviation: "Nov" },
  { key: 11, shortTitle: "dec", title: "december", abbreviation: "Dec" },
];

export const quarters: WeekMonthDataType[] = [
  { key: 0, shortTitle: "Q1", title: "Jan - Mar", abbreviation: "Q1" },
  { key: 1, shortTitle: "Q2", title: "Apr - Jun", abbreviation: "Q2" },
  { key: 2, shortTitle: "Q3", title: "Jul - Sept", abbreviation: "Q3" },
  { key: 3, shortTitle: "Q4", title: "Oct - Dec", abbreviation: "Q4" },
];

export const charCapitalize = (word: string) => `${word.charAt(0).toUpperCase()}${word.substring(1)}`;

export const bindZero = (value: number) => (value > 9 ? `${value}` : `0${value}`);

export const timePreview = (date: Date) => {
  let hours = date.getHours();
  const amPm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12;
  hours = hours ? hours : 12;

  let minutes: number | string = date.getMinutes();
  minutes = bindZero(minutes);

  return `${bindZero(hours)}:${minutes} ${amPm}`;
};

export const datePreview = (date: Date, includeTime: boolean = false) => {
  const day = date.getDate();
  let month: number | WeekMonthDataType = date.getMonth();
  month = months[month];
  const year = date.getFullYear();

  return `${charCapitalize(month?.shortTitle)} ${day}, ${year}${includeTime ? `, ${timePreview(date)}` : ``}`;
};

const SCALE_FALLBACK_DAY_WIDTH: Record<TGanttViews, number> = {
  day: 160,
  week: 100,
  month: 28,
  quarter: 9,
};

const SCALE_MIN_DAY_WIDTH: Record<TGanttViews, number> = {
  day: 120,
  week: 88,
  month: 24,
  quarter: 8,
};

const SCALE_MAX_DAY_WIDTH: Record<TGanttViews, number> = {
  day: 240,
  week: 180,
  month: 64,
  quarter: 24,
};

const SCALE_ZOOM_MIN_DAY_WIDTH: Record<TGanttViews, number> = {
  day: 64,
  week: 32,
  month: 18,
  quarter: 4,
};

const SCALE_ZOOM_MAX_DAY_WIDTH: Record<TGanttViews, number> = {
  day: 320,
  week: 240,
  month: 120,
  quarter: 48,
};

export type TTimelineZoomDirection = "in" | "out";

export const getTimelineZoomDayWidth = (
  view: TGanttViews,
  currentDayWidth: number,
  direction: TTimelineZoomDirection
): number => {
  const factor = direction === "in" ? 1.15 : 1 / 1.15;
  const nextWidth = currentDayWidth * factor;
  const clamped = Math.min(SCALE_ZOOM_MAX_DAY_WIDTH[view], Math.max(SCALE_ZOOM_MIN_DAY_WIDTH[view], nextWidth));

  return Math.round(clamped * 100) / 100;
};

/**
 * Returns the calendar boundary that should be anchored at the left edge when
 * a scale is selected. This keeps "Month" looking like a calendar month and
 * "Quarter" looking like an actual calendar quarter instead of a rolling range.
 */
export const getTimelinePeriodStart = (
  view: TGanttViews,
  date: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
): Date => {
  const periodStart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  periodStart.setHours(0, 0, 0, 0);

  if (view === "week") {
    const diff = (periodStart.getDay() + 7 - startOfWeek) % 7;
    periodStart.setDate(periodStart.getDate() - diff);
  } else if (view === "month") {
    periodStart.setDate(1);
  } else if (view === "quarter") {
    periodStart.setMonth(Math.floor(periodStart.getMonth() / 3) * 3, 1);
  }

  return periodStart;
};

export const getTimelineTargetDays = (
  view: TGanttViews,
  date: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
): number => {
  if (view === "day") return 5;
  if (view === "week") return 7;
  if (view === "month") return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();

  const quarterStart = getTimelinePeriodStart("quarter", date, startOfWeek);
  const nextQuarterStart = new Date(quarterStart.getFullYear(), quarterStart.getMonth() + 3, 1);
  return Math.round(
    (Date.UTC(nextQuarterStart.getFullYear(), nextQuarterStart.getMonth(), nextQuarterStart.getDate()) -
      Date.UTC(quarterStart.getFullYear(), quarterStart.getMonth(), quarterStart.getDate())) /
      86_400_000
  );
};

/**
 * Computes day width from the available timeline viewport so each scale shows
 * approximately one semantic period:
 * - Week: 7 days
 * - Month: one calendar month
 * - Quarter: one calendar quarter
 *
 * Minimums keep columns readable on small screens; maximums avoid oversized
 * cells on ultra-wide displays.
 */
export const getTimelineDayWidth = (
  view: TGanttViews,
  date: Date,
  viewportWidth: number,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
): number => {
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) return SCALE_FALLBACK_DAY_WIDTH[view];

  const targetDays = getTimelineTargetDays(view, date, startOfWeek);
  const calculatedWidth = viewportWidth / targetDays;

  return Math.min(SCALE_MAX_DAY_WIDTH[view], Math.max(SCALE_MIN_DAY_WIDTH[view], calculatedWidth));
};

// context data
export const VIEWS_LIST: ChartDataType[] = [
  {
    key: "day",
    i18n_title: "common.day",
    data: {
      startDate: new Date(),
      currentDate: new Date(),
      endDate: new Date(),
      approxFilterRange: 1,
      dayWidth: 160,
    },
  },
  {
    key: "week",
    i18n_title: "common.week",
    data: {
      startDate: new Date(),
      currentDate: new Date(),
      endDate: new Date(),
      approxFilterRange: 1, // buffer month on each side; visible viewport is one semantic week
      dayWidth: 100,
    },
  },
  {
    key: "month",
    i18n_title: "common.month",
    data: {
      startDate: new Date(),
      currentDate: new Date(),
      endDate: new Date(),
      approxFilterRange: 2, // render buffer only; visible viewport is one calendar month
      dayWidth: 28,
    },
  },
  {
    key: "quarter",
    i18n_title: "common.quarter",
    data: {
      startDate: new Date(),
      currentDate: new Date(),
      endDate: new Date(),
      approxFilterRange: 3, // render buffer only; visible viewport is one calendar quarter
      dayWidth: 9,
    },
  },
];

export const currentViewDataWithView = (view: TGanttViews = "month") =>
  VIEWS_LIST.find((_viewData) => _viewData.key === view);
