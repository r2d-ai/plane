/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import type { IGanttBlock } from "@plane/types";
import { Row } from "@plane/ui";
import { cn } from "@plane/utils";
import { MultipleSelectEntityAction } from "@/components/core/multiple-select";
import { IssueGanttSidebarBlock } from "@/components/issues/issue-layouts/gantt/blocks";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import { BLOCK_HEIGHT, GANTT_SELECT_GROUP } from "../../constants";
import { TimelineColumnCell } from "../timeline-columns";

type Props = {
  block: IGanttBlock;
  visibleColumns: TGanttColumnKey[];
  enableSelection: boolean;
  isDragging: boolean;
  selectionHelpers?: TSelectionHelper;
  isEpic?: boolean;
};

export const IssuesSidebarBlock = observer(function IssuesSidebarBlock(props: Props) {
  const { block, visibleColumns, enableSelection, isDragging, selectionHelpers, isEpic = false } = props;
  const { updateActiveBlockId, isBlockActive } = useTimeLineChartStore();
  const { getIsIssuePeeked } = useIssueDetail();

  if (!block?.data) return null;

  const isIssueSelected = selectionHelpers?.getIsEntitySelected(block.id);
  const isIssueFocused = selectionHelpers?.getIsEntityActive(block.id);
  const isBlockHoveredOn = isBlockActive(block.id);

  return (
    <div
      className={cn("group/list-block", {
        "rounded-sm bg-layer-1": isDragging,
        "rounded-l-sm border border-r-0 border-accent-strong": getIsIssuePeeked(block.data.id),
        "border border-r-0 border-strong-1": isIssueFocused,
      })}
      onMouseEnter={() => updateActiveBlockId(block.id)}
      onMouseLeave={() => updateActiveBlockId(null)}
    >
      <Row
        className={cn(
          "group flex w-full items-center gap-2 bg-layer-transparent pr-4 hover:bg-layer-transparent-hover",
          {
            "bg-layer-transparent-hover": isBlockHoveredOn,
            "bg-accent-primary/5 hover:bg-accent-primary/10": isIssueSelected,
            "bg-accent-primary/10": isIssueSelected && isBlockHoveredOn,
          }
        )}
        style={{ height: `${BLOCK_HEIGHT}px` }}
      >
        {enableSelection && selectionHelpers && (
          <div className="absolute left-1 flex items-center gap-2">
            <MultipleSelectEntityAction
              className={cn(
                "pointer-events-none opacity-0 transition-opacity group-hover/list-block:pointer-events-auto group-hover/list-block:opacity-100",
                {
                  "pointer-events-auto opacity-100": isIssueSelected,
                }
              )}
              groupId={GANTT_SELECT_GROUP}
              id={block.id}
              selectionHelpers={selectionHelpers}
            />
          </div>
        )}
        <div className="flex h-full w-full min-w-0 items-center gap-2 truncate pl-4">
          {visibleColumns.map((columnKey) => (
            <div
              key={columnKey}
              className={cn("min-w-0 truncate", {
                "flex-[2]": columnKey === "work_item",
                "flex-1": columnKey !== "work_item",
              })}
            >
              {columnKey === "work_item" ? (
                <IssueGanttSidebarBlock issueId={block.data.id} isEpic={isEpic} />
              ) : (
                <TimelineColumnCell columnKey={columnKey} issue={block.data} isEpic={isEpic} />
              )}
            </div>
          ))}
        </div>
      </Row>
    </div>
  );
});
