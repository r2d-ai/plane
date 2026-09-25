/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { cloneDeep, uniqBy } from "lodash-es";
// plane imports
import type { ChartDataType } from "@plane/types";
import { EStartOfTheWeek } from "@plane/types";
// local imports
import { months } from "../data";
import { getNumberOfDaysBetweenTwoDates, getNumberOfDaysInMonth } from "./helpers";
import type { IWeekBlock } from "./week-view";
import { getWeeksBetweenTwoDates } from "./week-view";

export interface IMonthBlock {
  today: boolean;
  month: number;
  days: number;
  monthData: {
    key: number;
    shortTitle: string;
    title: string;
  };
  title: string;
  year: number;
}

export interface IMonthView {
  months: IMonthBlock[];
  weeks: IWeekBlock[];
}

/**
 * Generate Month Chart data
 * @param monthPayload
 * @param side
 * @returns
 */
const generateMonthChart = (
  monthPayload: ChartDataType,
  side: null | "left" | "right",
  targetDate?: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
) => {
  let renderState = cloneDeep(monthPayload);

  const range: number = renderState.data.approxFilterRange || 2;
  let filteredDates: IMonthView = { months: [], weeks: [] };
  let minusDate: Date = new Date();
  let plusDate: Date = new Date();

  let startDate = new Date();
  let endDate = new Date();

  // if side is null generate months on both side of current date
  if (side === null) {
    const currentDate = renderState.data.currentDate;

    minusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - range, 1);
    plusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + range + 1, 0);

    if (minusDate && plusDate) filteredDates = getMonthsViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    const firstMonth = filteredDates.months[0];
    const lastMonth = filteredDates.months[filteredDates.months.length - 1];
    startDate = new Date(firstMonth.year, firstMonth.month, 1);
    endDate = new Date(lastMonth.year, lastMonth.month + 1, 0);
    renderState = {
      ...renderState,
      data: {
        ...renderState.data,
        startDate,
        endDate,
      },
    };
  }
  // When side is left, generate more months on the left side of the start date
  else if (side === "left") {
    const chartStartDate = renderState.data.startDate;
    const currentDate = targetDate ? targetDate : chartStartDate;

    minusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - range, 1);
    plusDate = new Date(chartStartDate.getFullYear(), chartStartDate.getMonth(), chartStartDate.getDate() - 1);

    if (minusDate && plusDate) filteredDates = getMonthsViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    const firstMonth = filteredDates.months[0];
    startDate = new Date(firstMonth.year, firstMonth.month, 1);
    endDate = new Date(chartStartDate.getFullYear(), chartStartDate.getMonth(), chartStartDate.getDate() - 1);
    renderState = {
      ...renderState,
      data: { ...renderState.data, startDate },
    };
  }
  // When side is right, generate more months on the right side of the end date
  else if (side === "right") {
    const chartEndDate = renderState.data.endDate;
    const currentDate = targetDate ? targetDate : chartEndDate;

    minusDate = new Date(chartEndDate.getFullYear(), chartEndDate.getMonth(), chartEndDate.getDate() + 1);
    plusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + range, 1);

    if (minusDate && plusDate) filteredDates = getMonthsViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    const lastMonth = filteredDates.months[filteredDates.months.length - 1];
    startDate = new Date(chartEndDate.getFullYear(), chartEndDate.getMonth(), chartEndDate.getDate() + 1);
    endDate = new Date(lastMonth.year, lastMonth.month + 1, 0);
    renderState = {
      ...renderState,
      data: { ...renderState.data, endDate },
    };
  }

  const days = Math.abs(getNumberOfDaysBetweenTwoDates(startDate, endDate)) + 1;
  const scrollWidth = days * monthPayload.data.dayWidth;

  return { state: renderState, payload: filteredDates, scrollWidth: scrollWidth };
};

/**
 * Get Month View data between two dates, i.e., Months and Weeks between two dates
 * @param startDate
 * @param endDate
 * @returns
 */
const getMonthsViewBetweenTwoDates = (
  startDate: Date,
  endDate: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
): IMonthView => ({
  months: getMonthsBetweenTwoDates(startDate, endDate),
  weeks: getWeeksBetweenTwoDates(startDate, endDate, false, startOfWeek),
});

/**
 * generate array of months between two dates
 * @param startDate
 * @param endDate
 * @returns
 */
export const getMonthsBetweenTwoDates = (startDate: Date, endDate: Date): IMonthBlock[] => {
  const monthBlocks = [];

  const startYear = startDate.getFullYear();
  const startMonth = startDate.getMonth();

  const today = new Date();
  const todayMonth = today.getMonth();
  const todayYear = today.getFullYear();

  const currentDate = new Date(startYear, startMonth);

  while (currentDate <= endDate) {
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth();

    monthBlocks.push({
      year: currentYear,
      month: currentMonth,
      monthData: months[currentMonth],
      title: `${months[currentMonth].title} ${currentYear}`,
      days: getNumberOfDaysInMonth(currentMonth, currentYear),
      today: todayMonth === currentMonth && todayYear === currentYear,
    });

    currentDate.setMonth(currentDate.getMonth() + 1);
  }

  return monthBlocks;
};

/**
 * Merge two MonthView data payloads
 * @param a
 * @param b
 * @returns
 */
const mergeMonthRenderPayloads = (a: IMonthView, b: IMonthView): IMonthView => ({
  months: uniqBy([...a.months, ...b.months], (monthBlock) => `${monthBlock.month}_${monthBlock.year}`),
  weeks: uniqBy(
    [...a.weeks, ...b.weeks],
    (weekBlock) => `${weekBlock.startDate.getTime()}_${weekBlock.endDate.getTime()}`
  ),
});

export const monthView = {
  generateChart: generateMonthChart,
  mergeRenderPayloads: mergeMonthRenderPayloads,
};
