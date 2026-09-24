/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { cn } from "@plane/utils";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import { HEADER_HEIGHT, SIDEBAR_WIDTH } from "../../constants";
import type { IDayViewMonthBlock } from "../../views/day-view";

export const DayChartView = observer(function DayChartView() {
  const { currentViewData, renderView } = useTimeLineChartStore();
  const dayBlocks: IDayViewMonthBlock[] = renderView;

  return (
    <div className="absolute top-0 left-0 flex h-max min-h-full w-max">
      {currentViewData &&
        dayBlocks?.map((block) => (
          <div
            key={`day-month-${block.year}-${block.month}`}
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
                  {block.title}
                </div>
              </div>
              <div className="flex h-5 w-full">
                {block.children?.map((day) => (
                  <div
                    key={`day-sub-title-${day.date.toISOString()}`}
                    className={cn(
                      "flex flex-shrink-0 items-center justify-between p-1 text-center capitalize outline-[0.25px] outline-subtle-1",
                      {
                        "bg-accent-primary/20": day.today,
                      }
                    )}
                    style={{ width: `${currentViewData.data.dayWidth}px` }}
                  >
                    <div className="text-11 font-medium text-placeholder">{day.dayData.abbreviation}</div>
                    <div className="text-11 font-medium">
                      <span
                        className={cn({
                          "rounded-sm bg-accent-primary px-1 text-on-color": day.today,
                        })}
                      >
                        {day.date.getDate()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex h-full w-full flex-grow bg-surface-1">
              {block.children?.map((day) => (
                <div
                  key={`day-column-${day.date.toISOString()}`}
                  className={cn("h-full overflow-hidden outline-[0.25px] outline-subtle", {
                    "bg-accent-primary/20": day.today,
                  })}
                  style={{ width: `${currentViewData.data.dayWidth}px` }}
                >
                  {["sat", "sun"].includes(day.dayData.shortTitle) && (
                    <div className="h-full bg-surface-2 outline-[0.25px] outline-strong" />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
});
