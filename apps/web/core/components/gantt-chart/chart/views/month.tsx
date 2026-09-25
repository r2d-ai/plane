/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { cn } from "@plane/utils";
import { HEADER_HEIGHT, SIDEBAR_WIDTH } from "@/components/gantt-chart/constants";
import { weeks } from "@/components/gantt-chart/data";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import type { IMonthView } from "../../views";

export const MonthChartView = observer(function MonthChartView() {
  const { currentViewData, renderView } = useTimeLineChartStore();
  const monthView: IMonthView = renderView;

  if (!monthView || !currentViewData) return null;

  const { months } = monthView;
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return (
    <div className="absolute top-0 left-0 flex h-max min-h-full w-max">
      {months.map((monthBlock) => {
        const days = Array.from({ length: monthBlock.days }, (_, index) => {
          const date = new Date(monthBlock.year, monthBlock.month, index + 1);
          const dayOfWeek = date.getDay();
          const isToday = date.getTime() === today.getTime();

          return {
            date,
            day: index + 1,
            dayOfWeek,
            isToday,
            weekday: weeks[dayOfWeek],
          };
        });

        return (
          <div
            key={`month-${monthBlock.month}-${monthBlock.year}`}
            className="relative flex flex-col outline-[0.25px] outline-subtle-1"
          >
            <div
              className="sticky top-0 z-[5] w-full flex-shrink-0 bg-surface-1 outline-[1px] outline-subtle-1"
              style={{ height: `${HEADER_HEIGHT}px` }}
            >
              <div className="inline-flex h-7 w-full justify-between">
                <div
                  className="sticky z-[1] m-1 flex items-center bg-surface-1 px-3 py-1 text-13 font-regular whitespace-nowrap text-secondary capitalize"
                  style={{ left: `${SIDEBAR_WIDTH}px` }}
                >
                  {monthBlock.title}
                  {monthBlock.today && (
                    <span className="ml-2 rounded-sm bg-accent-primary px-1 text-9 font-medium text-on-color">
                      Current
                    </span>
                  )}
                </div>
              </div>

              <div className="flex h-5 w-full">
                {days.map(({ date, day, dayOfWeek, isToday, weekday }) => (
                  <div
                    key={`month-day-header-${date.toISOString()}`}
                    className={cn(
                      "flex flex-shrink-0 items-center justify-center gap-0.5 overflow-hidden text-center outline-[0.25px] outline-subtle-1",
                      {
                        "bg-accent-primary/20": isToday,
                        "bg-surface-2": dayOfWeek === 0 || dayOfWeek === 6,
                      }
                    )}
                    style={{ width: `${currentViewData.data.dayWidth}px` }}
                    title={`${weekday.title}, ${monthBlock.monthData.title} ${day}, ${monthBlock.year}`}
                  >
                    {currentViewData.data.dayWidth >= 32 && (
                      <span className="text-9 font-medium text-placeholder">{weekday.abbreviation}</span>
                    )}
                    <span
                      className={cn("text-10 font-medium", {
                        "rounded-sm bg-accent-primary px-1 text-on-color": isToday,
                      })}
                    >
                      {day}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex h-full w-full flex-grow bg-surface-1">
              {days.map(({ date, dayOfWeek, isToday }) => (
                <div
                  key={`month-day-column-${date.toISOString()}`}
                  className={cn("h-full flex-shrink-0 overflow-hidden outline-[0.25px] outline-subtle", {
                    "bg-accent-primary/20": isToday,
                    "bg-surface-2": dayOfWeek === 0 || dayOfWeek === 6,
                  })}
                  style={{ width: `${currentViewData.data.dayWidth}px` }}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
});
