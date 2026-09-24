/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IBlockUpdateDependencyData } from "@plane/types";
import { GanttChartBlock } from "@/components/gantt-chart/blocks/block";
import type { TimelineRow } from "@/components/gantt-chart/types/timeline-row";
import { isTimelineIssueRow } from "@/components/gantt-chart/types/timeline-row";

export type GanttChartBlocksProps = {
  timelineRows: TimelineRow[];
  blockToRender: (data: any) => React.ReactNode;
  enableBlockLeftResize: boolean | ((blockId: string) => boolean);
  enableBlockRightResize: boolean | ((blockId: string) => boolean);
  enableBlockMove: boolean | ((blockId: string) => boolean);
  ganttContainerRef: React.RefObject<HTMLDivElement>;
  showAllBlocks: boolean;
  updateBlockDates?: (updates: IBlockUpdateDependencyData[]) => Promise<void>;
  enableDependency: boolean | ((blockId: string) => boolean);
};

export function GanttChartBlocksList(props: GanttChartBlocksProps) {
  const {
    timelineRows,
    blockToRender,
    enableBlockLeftResize,
    enableBlockRightResize,
    enableBlockMove,
    ganttContainerRef,
    showAllBlocks,
    updateBlockDates,
    enableDependency,
  } = props;

  return (
    <>
      {timelineRows?.filter(isTimelineIssueRow).map((row) => (
        <GanttChartBlock
          key={row.rowId}
          rowId={row.rowId}
          blockId={row.issueId}
          showAllBlocks={showAllBlocks}
          blockToRender={blockToRender}
          enableBlockLeftResize={
            typeof enableBlockLeftResize === "function" ? enableBlockLeftResize(row.issueId) : enableBlockLeftResize
          }
          enableBlockRightResize={
            typeof enableBlockRightResize === "function" ? enableBlockRightResize(row.issueId) : enableBlockRightResize
          }
          enableBlockMove={typeof enableBlockMove === "function" ? enableBlockMove(row.issueId) : enableBlockMove}
          enableDependency={typeof enableDependency === "function" ? enableDependency(row.issueId) : enableDependency}
          ganttContainerRef={ganttContainerRef}
          updateBlockDates={updateBlockDates}
        />
      ))}
    </>
  );
}
