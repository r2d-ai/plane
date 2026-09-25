/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { autoScrollForElements } from "@atlaskit/pragmatic-drag-and-drop-auto-scroll/element";
import { observer } from "mobx-react";
import type {
  ChartDataType,
  IBlockUpdateData,
  IBlockUpdateDependencyData,
  IGanttBlock,
  TGanttViews,
} from "@plane/types";
import { cn, getDate } from "@plane/utils";
import { MultipleSelectGroup } from "@/components/core/multiple-select";
import {
  DayChartView,
  GanttChartSidebar,
  MonthChartView,
  QuarterChartView,
  WeekChartView,
} from "@/components/gantt-chart";
import { GanttChartRowList } from "@/components/gantt-chart/blocks/block-row-list";
import { GanttChartBlocksList } from "@/components/gantt-chart/blocks/blocks-list";
import type { TimelineRow } from "@/components/gantt-chart/types/timeline-row";
import { IssueBulkOperationsRoot } from "@/components/issues/bulk-operations";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";
import { useBulkOperationStatus } from "@/hooks/use-bulk-operation-status";
import { useTimelinePan } from "@/hooks/use-timeline-pan";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import { DEFAULT_BLOCK_WIDTH, GANTT_SELECT_GROUP, HEADER_HEIGHT } from "../constants";
import { getItemPositionWidth } from "../views";
import { TimelineDragHelper } from "./timeline-drag-helper";

type Props = {
  blockIds: string[];
  timelineRows: TimelineRow[];
  sidebarWidth: number;
  visibleColumns: TGanttColumnKey[];
  canLoadMoreBlocks?: boolean;
  loadMoreBlocks?: () => void;
  updateBlockDates?: (updates: IBlockUpdateDependencyData[]) => Promise<void>;
  blockToRender: (data: any) => React.ReactNode;
  blockUpdateHandler: (block: any, payload: IBlockUpdateData) => void;
  bottomSpacing: boolean;
  enableBlockLeftResize: boolean | ((blockId: string) => boolean);
  enableBlockMove: boolean | ((blockId: string) => boolean);
  enableBlockRightResize: boolean | ((blockId: string) => boolean);
  enableReorder: boolean | ((blockId: string) => boolean);
  enableSelection: boolean | ((blockId: string) => boolean);
  enableAddBlock: boolean | ((blockId: string) => boolean);
  enableDependency: boolean | ((blockId: string) => boolean);
  itemsContainerWidth: number;
  showAllBlocks: boolean;
  sidebarToRender: (props: any) => React.ReactNode;
  title: string;
  updateCurrentViewRenderPayload: (
    direction: "left" | "right",
    currentView: TGanttViews,
    targetDate?: Date
  ) => ChartDataType | undefined;
  onSidebarWidthChange: (width: number) => void;
  onToggleGroupCollapse?: (groupId: string) => void;
  onZoom: (direction: "in" | "out", clientX?: number) => void;
  quickAdd?: React.ReactNode | undefined;
  isEpic?: boolean;
};

export const GanttChartMainContent = observer(function GanttChartMainContent(props: Props) {
  const {
    blockIds,
    timelineRows,
    sidebarWidth,
    visibleColumns,
    loadMoreBlocks,
    blockToRender,
    blockUpdateHandler,
    bottomSpacing,
    enableBlockLeftResize,
    enableBlockMove,
    enableBlockRightResize,
    enableReorder,
    enableAddBlock,
    enableSelection,
    enableDependency,
    itemsContainerWidth,
    showAllBlocks,
    sidebarToRender,
    title,
    canLoadMoreBlocks,
    updateCurrentViewRenderPayload,
    onSidebarWidthChange,
    onToggleGroupCollapse,
    onZoom,
    quickAdd,
    updateBlockDates,
    isEpic = false,
  } = props;

  const ganttContainerRef = useRef<HTMLDivElement>(null);
  const { currentView, currentViewData } = useTimeLineChartStore();
  const isBulkOperationsEnabled = useBulkOperationStatus();
  const { isPanning, containerProps: panProps } = useTimelinePan({ containerRef: ganttContainerRef });

  useEffect(() => {
    const element = ganttContainerRef.current;
    if (!element) return;

    return combine(
      autoScrollForElements({
        element,
        getAllowedAxis: () => "vertical",
        canScroll: ({ source }) => source.data.dragInstanceId === "GANTT_REORDER",
      })
    );
  }, [ganttContainerRef]);

  const onScroll = (e: React.UIEvent<HTMLDivElement, UIEvent>) => {
    const { clientWidth, scrollLeft, scrollWidth } = e.currentTarget;

    const approxRangeLeft = scrollLeft;
    const approxRangeRight = scrollWidth - (scrollLeft + clientWidth);
    const calculatedRangeRight = itemsContainerWidth - (scrollLeft + clientWidth);

    if (approxRangeRight < clientWidth || calculatedRangeRight < clientWidth) {
      updateCurrentViewRenderPayload("right", currentView);
    }
    if (approxRangeLeft < clientWidth) {
      updateCurrentViewRenderPayload("left", currentView);
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const container = ganttContainerRef.current;
    if (!container || e.deltaY === 0) return;

    const rect = container.getBoundingClientRect();
    const pointerX = e.clientX - rect.left;
    const pointerY = e.clientY - rect.top;
    const isOverTimeline = pointerX >= sidebarWidth;
    const isOverTimeHeader = isOverTimeline && pointerY >= 0 && pointerY <= HEADER_HEIGHT;
    const isModifierZoom = isOverTimeline && (e.ctrlKey || e.metaKey);

    // Preserve native wheel scrolling in the work-item body.
    // Wheel over the time axis zooms directly; Ctrl/Cmd + wheel zooms anywhere in the timeline.
    if (!isOverTimeHeader && !isModifierZoom) return;

    e.preventDefault();
    onZoom(e.deltaY < 0 ? "in" : "out", e.clientX);
  };

  const handleScrollToBlock = (block: IGanttBlock) => {
    const scrollContainer = ganttContainerRef.current as HTMLDivElement;
    const scrollToEndDate = !block.start_date && block.target_date;
    const scrollToDate = block.start_date ? getDate(block.start_date) : getDate(block.target_date);
    let chartData;

    if (!scrollContainer || !currentViewData || !scrollToDate) return;

    if (scrollToDate.getTime() < currentViewData.data.startDate.getTime()) {
      chartData = updateCurrentViewRenderPayload("left", currentView, scrollToDate);
    } else if (scrollToDate.getTime() > currentViewData.data.endDate.getTime()) {
      chartData = updateCurrentViewRenderPayload("right", currentView, scrollToDate);
    }

    const updatedPosition = getItemPositionWidth(chartData ?? currentViewData, block);

    setTimeout(() => {
      if (updatedPosition)
        scrollContainer.scrollLeft = updatedPosition.marginLeft - 4 - (scrollToEndDate ? DEFAULT_BLOCK_WIDTH : 0);
    });
  };

  const CHART_VIEW_COMPONENTS: {
    [key in TGanttViews]: React.FC;
  } = {
    day: DayChartView,
    week: WeekChartView,
    month: MonthChartView,
    quarter: QuarterChartView,
  };

  if (!currentView) return null;
  const ActiveChartView = CHART_VIEW_COMPONENTS[currentView];

  return (
    <>
      <TimelineDragHelper ganttContainerRef={ganttContainerRef} />
      <MultipleSelectGroup
        containerRef={ganttContainerRef}
        entities={{
          [GANTT_SELECT_GROUP]: blockIds ?? [],
        }}
        disabled={!isBulkOperationsEnabled || isEpic}
      >
        {(helpers) => (
          <>
            <div
              id="gantt-container"
              className={cn(
                "vertical-scrollbar horizontal-scrollbar flex scrollbar-lg h-full w-full overflow-auto overscroll-contain border-t-[0.5px] border-subtle outline-none",
                {
                  "mb-8": bottomSpacing,
                  "cursor-grabbing select-none": isPanning,
                }
              )}
              ref={ganttContainerRef}
              onScroll={onScroll}
              onWheel={handleWheel}
              {...panProps}
            >
              <GanttChartSidebar
                blockIds={blockIds}
                timelineRows={timelineRows}
                sidebarWidth={sidebarWidth}
                visibleColumns={visibleColumns}
                loadMoreBlocks={loadMoreBlocks}
                canLoadMoreBlocks={canLoadMoreBlocks}
                ganttContainerRef={ganttContainerRef}
                blockUpdateHandler={blockUpdateHandler}
                enableReorder={enableReorder}
                enableSelection={enableSelection}
                sidebarToRender={sidebarToRender}
                title={title}
                selectionHelpers={helpers}
                showAllBlocks={showAllBlocks}
                onSidebarWidthChange={onSidebarWidthChange}
                onToggleGroupCollapse={onToggleGroupCollapse}
                isEpic={isEpic}
              />
              <div className="relative h-max min-h-full flex-shrink-0 flex-grow">
                <ActiveChartView />
                {currentViewData && (
                  <div
                    className="relative h-full"
                    style={{
                      width: `${itemsContainerWidth}px`,
                      transform: `translateY(${HEADER_HEIGHT}px)`,
                      paddingBottom: `${HEADER_HEIGHT}px`,
                    }}
                  >
                    <GanttChartRowList
                      timelineRows={timelineRows}
                      sidebarWidth={sidebarWidth}
                      blockUpdateHandler={blockUpdateHandler}
                      handleScrollToBlock={handleScrollToBlock}
                      enableAddBlock={enableAddBlock}
                      showAllBlocks={showAllBlocks}
                      selectionHelpers={helpers}
                      ganttContainerRef={ganttContainerRef}
                      onToggleGroupCollapse={onToggleGroupCollapse}
                    />
                    <GanttChartBlocksList
                      timelineRows={timelineRows}
                      blockToRender={blockToRender}
                      enableBlockLeftResize={enableBlockLeftResize}
                      enableBlockRightResize={enableBlockRightResize}
                      enableBlockMove={enableBlockMove}
                      ganttContainerRef={ganttContainerRef}
                      enableDependency={enableDependency}
                      showAllBlocks={showAllBlocks}
                      updateBlockDates={updateBlockDates}
                    />
                  </div>
                )}
              </div>
            </div>
            {quickAdd ? quickAdd : null}
            <IssueBulkOperationsRoot selectionHelpers={helpers} />
          </>
        )}
      </MultipleSelectGroup>
    </>
  );
});
