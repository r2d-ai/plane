/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ChartDataType } from "@plane/types";
import { EStartOfTheWeek } from "@plane/types";
import { generateWeeks, months } from "../data";
import { getNumberOfDaysBetweenTwoDates } from "./helpers";
import type { IDayBlock } from "./week-view";

export interface IDayViewMonthBlock {
  month: number;
  year: number;
  title: string;
  today: boolean;
  children: IDayBlock[];
}

/**
 * Generate Day Chart data — calendar-day cells at day scale
 */
const generateDayChart = (
  dayPayload: ChartDataType,
  side: null | "left" | "right",
  targetDate?: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
) => {
  let renderState = dayPayload;

  const range: number = renderState.data.approxFilterRange || 2;
  let filteredDates: IDayViewMonthBlock[] = [];
  let minusDate: Date = new Date();
  let plusDate: Date = new Date();

  let startDate = new Date();
  let endDate = new Date();

  if (side === null) {
    const currentDate = renderState.data.currentDate;

    minusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - range, currentDate.getDate());
    plusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + range, currentDate.getDate());

    if (minusDate && plusDate) filteredDates = getDayViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    startDate = filteredDates[0]?.children[0]?.date ?? minusDate;
    const lastMonth = filteredDates[filteredDates.length - 1];
    endDate = lastMonth?.children[lastMonth.children.length - 1]?.date ?? plusDate;
    renderState = {
      ...renderState,
      data: {
        ...renderState.data,
        startDate,
        endDate,
      },
    };
  } else if (side === "left") {
    const chartStartDate = renderState.data.startDate;
    const currentDate = targetDate ? targetDate : chartStartDate;

    minusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - range, 1);
    plusDate = new Date(chartStartDate.getFullYear(), chartStartDate.getMonth(), chartStartDate.getDate() - 1);

    if (minusDate && plusDate) filteredDates = getDayViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    startDate = filteredDates[0]?.children[0]?.date ?? minusDate;
    endDate = new Date(chartStartDate.getFullYear(), chartStartDate.getMonth(), chartStartDate.getDate() - 1);
    renderState = {
      ...renderState,
      data: { ...renderState.data, startDate },
    };
  } else if (side === "right") {
    const chartEndDate = renderState.data.endDate;
    const currentDate = targetDate ? targetDate : chartEndDate;

    minusDate = new Date(chartEndDate.getFullYear(), chartEndDate.getMonth(), chartEndDate.getDate() + 1);
    plusDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + range, 1);

    if (minusDate && plusDate) filteredDates = getDayViewBetweenTwoDates(minusDate, plusDate, startOfWeek);

    startDate = new Date(chartEndDate.getFullYear(), chartEndDate.getMonth(), chartEndDate.getDate() + 1);
    const lastMonth = filteredDates[filteredDates.length - 1];
    endDate = lastMonth?.children[lastMonth.children.length - 1]?.date ?? plusDate;
    renderState = {
      ...renderState,
      data: { ...renderState.data, endDate },
    };
  }

  const days = Math.abs(getNumberOfDaysBetweenTwoDates(startDate, endDate)) + 1;
  const scrollWidth = days * dayPayload.data.dayWidth;

  return { state: renderState, payload: filteredDates, scrollWidth };
};

const getDayViewBetweenTwoDates = (
  startDate: Date,
  endDate: Date,
  startOfWeek: EStartOfTheWeek = EStartOfTheWeek.SUNDAY
): IDayViewMonthBlock[] => {
  const monthBlocks: IDayViewMonthBlock[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekDays = generateWeeks(startOfWeek);

  const currentDate = new Date(startDate);
  currentDate.setHours(0, 0, 0, 0);
  const end = new Date(endDate);
  end.setHours(0, 0, 0, 0);

  let currentMonth = -1;
  let currentYear = -1;
  let currentBlock: IDayViewMonthBlock | null = null;

  // oxlint-disable-next-line no-unmodified-loop-condition -- currentDate is mutated via setDate
  while (currentDate <= end) {
    const month = currentDate.getMonth();
    const year = currentDate.getFullYear();

    if (month !== currentMonth || year !== currentYear) {
      currentMonth = month;
      currentYear = year;
      currentBlock = {
        month,
        year,
        title: `${months[month].abbreviation} ${year}`,
        today: false,
        children: [],
      };
      monthBlocks.push(currentBlock);
    }

    const dayOfWeek = currentDate.getDay();
    const dayData = weekDays.find((d) => d.key === dayOfWeek) ?? weekDays[dayOfWeek];
    const isToday = today.getTime() === currentDate.getTime();

    currentBlock?.children.push({
      date: new Date(currentDate),
      day: dayOfWeek,
      dayData,
      title: `${dayData.abbreviation} ${currentDate.getDate()}`,
      today: isToday,
    });

    if (isToday && currentBlock) currentBlock.today = true;

    currentDate.setDate(currentDate.getDate() + 1);
  }

  return monthBlocks;
};

const mergeDayRenderPayloads = (a: IDayViewMonthBlock[], b: IDayViewMonthBlock[]) => [...a, ...b];

export const dayView = {
  generateChart: generateDayChart,
  mergeRenderPayloads: mergeDayRenderPayloads,
};
