/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IBlockUpdateData, IGanttBlock } from "@plane/types";
import RenderIfVisible from "@/components/core/render-if-visible-HOC";
import { BlockRow } from "@/components/gantt-chart/blocks/block-row";
import { BLOCK_HEIGHT } from "@/components/gantt-chart/constants";
import type { TimelineRow } from "@/components/gantt-chart/types/timeline-row";
import { isTimelineGroupRow } from "@/components/gantt-chart/types/timeline-row";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";

export type GanttChartBlocksProps = {
  timelineRows: TimelineRow[];
  sidebarWidth: number;
  blockUpdateHandler: (block: any, payload: IBlockUpdateData) => void;
  handleScrollToBlock: (block: IGanttBlock) => void;
  enableAddBlock: boolean | ((blockId: string) => boolean);
  showAllBlocks: boolean;
  selectionHelpers: TSelectionHelper;
  ganttContainerRef: React.RefObject<HTMLDivElement>;
  onToggleGroupCollapse?: (groupId: string) => void;
};

export function GanttChartRowList(props: GanttChartBlocksProps) {
  const {
    timelineRows,
    sidebarWidth,
    blockUpdateHandler,
    handleScrollToBlock,
    enableAddBlock,
    showAllBlocks,
    selectionHelpers,
    ganttContainerRef,
    onToggleGroupCollapse,
  } = props;

  return (
    <div className="absolute top-0 left-0 w-max min-w-full cursor-grab">
      {timelineRows?.map((row) => {
        if (isTimelineGroupRow(row)) {
          return (
            <button
              key={row.rowId}
              type="button"
              className="relative w-max min-w-full border-b-[0.5px] border-subtle-1 bg-surface-2"
              style={{ height: `${BLOCK_HEIGHT}px`, width: `100%` }}
              onClick={() => onToggleGroupCollapse?.(row.groupId)}
              aria-expanded={!row.collapsed}
            />
          );
        }

        const blockId = row.issueId;
        return (
          <RenderIfVisible
            key={row.rowId}
            root={ganttContainerRef}
            horizontalOffset={100}
            verticalOffset={200}
            classNames="relative min-w-full w-max"
            placeholderChildren={<div className="pointer-events-none w-full" style={{ height: `${BLOCK_HEIGHT}px` }} />}
            shouldRecordHeights={false}
          >
            <BlockRow
              rowId={row.rowId}
              blockId={blockId}
              sidebarWidth={sidebarWidth}
              showAllBlocks={showAllBlocks}
              blockUpdateHandler={blockUpdateHandler}
              handleScrollToBlock={handleScrollToBlock}
              enableAddBlock={typeof enableAddBlock === "function" ? enableAddBlock(blockId) : enableAddBlock}
              selectionHelpers={selectionHelpers}
              ganttContainerRef={ganttContainerRef}
            />
          </RenderIfVisible>
        );
      })}
    </div>
  );
}
