/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { cn } from "@plane/utils";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import { HEADER_HEIGHT, SIDEBAR_WIDTH } from "../../constants";
import type { IMonthBlock, IQuarterMonthBlock } from "../../views";
import { groupMonthsToQuarters } from "../../views";

type QuarterWeekChunk = {
  key: string;
  startDay: number;
  endDay: number;
  days: number;
  isToday: boolean;
  label: string;
};

const getMonthWeekChunks = (monthBlock: IMonthBlock): QuarterWeekChunk[] => {
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === monthBlock.year && today.getMonth() === monthBlock.month;
  const chunks: QuarterWeekChunk[] = [];

  for (let startDay = 1; startDay <= monthBlock.days; startDay += 7) {
    const endDay = Math.min(monthBlock.days, startDay + 6);
    chunks.push({
      key: `${monthBlock.year}-${monthBlock.month}-${startDay}`,
      startDay,
      endDay,
      days: endDay - startDay + 1,
      isToday: isCurrentMonth && today.getDate() >= startDay && today.getDate() <= endDay,
      label:
        startDay === 1
          ? `${monthBlock.monthData.abbreviation} ${startDay}–${endDay}`
          : `${startDay}–${endDay}`,
    });
  }

  return chunks;
};

export const QuarterChartView = observer(function QuarterChartView() {
  const { currentViewData, renderView } = useTimeLineChartStore();
  const monthBlocks: IMonthBlock[] = renderView;
  const quarterBlocks: IQuarterMonthBlock[] = groupMonthsToQuarters(monthBlocks);

  return (
    <div className="absolute top-0 left-0 flex h-max min-h-full w-max">
      {currentViewData &&
        quarterBlocks.map((quarterBlock) => (
          <div
            key={`quarter-${quarterBlock.quarterNumber}-${quarterBlock.year}`}
            className="relative flex flex-col outline-[0.25px] outline-subtle-1"
          >
            <div
              className="sticky top-0 z-[5] w-full flex-shrink-0 bg-surface-1 outline-[1px] outline-subtle-1"
              style={{ height: `${HEADER_HEIGHT}px` }}
            >
              <div className="inline-flex h-7 w-full justify-between">
                <div
                  className="sticky z-[1] my-1 flex items-center bg-surface-1 px-3 py-1 text-14 font-regular whitespace-nowrap text-secondary capitalize"
                  style={{ left: `${SIDEBAR_WIDTH}px` }}
                >
                  {quarterBlock.title}
                  {quarterBlock.today && (
                    <span className="ml-2 rounded-sm bg-accent-primary px-1 text-9 font-medium text-on-color">
                      Current
                    </span>
                  )}
                </div>
                <div className="sticky px-3 py-2 text-11 whitespace-nowrap text-placeholder capitalize">
                  {quarterBlock.shortTitle}
                </div>
              </div>

              <div className="flex h-5 w-full">
                {quarterBlock.children.flatMap((monthBlock) =>
                  getMonthWeekChunks(monthBlock).map((chunk) => (
                    <div
                      key={chunk.key}
                      className={cn(
                        "flex flex-shrink-0 items-center justify-center overflow-hidden px-1 text-center outline-[0.25px] outline-subtle-1",
                        {
                          "bg-accent-primary/20": chunk.isToday,
                        }
                      )}
                      style={{ width: `${currentViewData.data.dayWidth * chunk.days}px` }}
                      title={`${monthBlock.monthData.title} ${chunk.startDay}–${chunk.endDay}, ${monthBlock.year}`}
                    >
                      <span
                        className={cn("truncate text-10 font-medium text-placeholder", {
                          "rounded-sm bg-accent-primary px-1 text-on-color": chunk.isToday,
                        })}
                      >
                        {chunk.label}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="flex h-full w-full flex-grow bg-surface-1">
              {quarterBlock.children.flatMap((monthBlock) =>
                getMonthWeekChunks(monthBlock).map((chunk) => (
                  <div
                    key={`quarter-week-column-${chunk.key}`}
                    className={cn("h-full flex-shrink-0 overflow-hidden outline-[0.25px] outline-subtle", {
                      "bg-accent-primary/20": chunk.isToday,
                    })}
                    style={{ width: `${currentViewData.data.dayWidth * chunk.days}px` }}
                  />
                ))
              )}
            </div>
          </div>
        ))}
    </div>
  );
});
