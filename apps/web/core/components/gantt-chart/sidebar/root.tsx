/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RefObject } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import type { IBlockUpdateData } from "@plane/types";
import { Row, ERowVariant } from "@plane/ui";
import { cn } from "@plane/utils";
import { MultipleSelectGroupAction } from "@/components/core/multiple-select";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";
import type { TSelectionHelper } from "@/hooks/use-multiple-select";
import { GANTT_SELECT_GROUP, HEADER_HEIGHT } from "../constants";
import type { TimelineRow } from "../types/timeline-row";
import { GANTT_COLUMN_DEFINITIONS } from "./timeline-columns";
import { SidebarSplitter } from "./sidebar-splitter";

type Props = {
  blockIds: string[];
  timelineRows: TimelineRow[];
  sidebarWidth: number;
  visibleColumns: TGanttColumnKey[];
  blockUpdateHandler: (block: any, payload: IBlockUpdateData) => void;
  canLoadMoreBlocks?: boolean;
  loadMoreBlocks?: () => void;
  ganttContainerRef: RefObject<HTMLDivElement>;
  enableReorder: boolean | ((blockId: string) => boolean);
  enableSelection: boolean | ((blockId: string) => boolean);
  sidebarToRender: (props: any) => React.ReactNode;
  title: string;
  selectionHelpers: TSelectionHelper;
  showAllBlocks?: boolean;
  onSidebarWidthChange: (width: number) => void;
  onToggleGroupCollapse?: (groupId: string) => void;
  isEpic?: boolean;
};

export const GanttChartSidebar = observer(function GanttChartSidebar(props: Props) {
  const { t } = useTranslation();
  const {
    blockIds,
    timelineRows,
    sidebarWidth,
    visibleColumns,
    blockUpdateHandler,
    enableReorder,
    enableSelection,
    sidebarToRender,
    loadMoreBlocks,
    canLoadMoreBlocks,
    ganttContainerRef,
    title,
    selectionHelpers,
    showAllBlocks = false,
    onSidebarWidthChange,
    onToggleGroupCollapse,
    isEpic = false,
  } = props;

  const isGroupSelectionEmpty = selectionHelpers.isGroupSelected(GANTT_SELECT_GROUP) === "empty";

  const columnHeaders = GANTT_COLUMN_DEFINITIONS.filter((col) => visibleColumns.includes(col.key));

  return (
    <Row
      id="gantt-sidebar"
      className="sticky left-0 z-10 h-max min-h-full flex-shrink-0 border-r-[0.5px] border-subtle-1 bg-surface-1"
      style={{ width: `${sidebarWidth}px` }}
      variant={ERowVariant.HUGGING}
    >
      <SidebarSplitter onResize={onSidebarWidthChange} />
      <Row
        className="group/list-header sticky top-0 z-10 box-border flex flex-shrink-0 items-end gap-2 border-b-[0.5px] border-subtle-1 bg-surface-1 pr-4 pb-2 text-13 font-medium text-tertiary"
        style={{ height: `${HEADER_HEIGHT}px`, width: `${sidebarWidth}px` }}
      >
        <div className={cn("flex min-w-0 flex-1 items-center gap-2")}>
          {enableSelection && (
            <div className="absolute left-1 flex w-3.5 flex-shrink-0 items-center">
              <MultipleSelectGroupAction
                className={cn(
                  "pointer-events-none size-3.5 opacity-0 !outline-none group-hover/list-header:pointer-events-auto group-hover/list-header:opacity-100",
                  {
                    "pointer-events-auto opacity-100": !isGroupSelectionEmpty,
                  }
                )}
                groupID={GANTT_SELECT_GROUP}
                selectionHelpers={selectionHelpers}
              />
            </div>
          )}
          {columnHeaders.map((col, index) => (
            <h6
              key={col.key}
              className={cn("truncate", {
                "flex-[2]": col.key === "work_item",
                "flex-1": col.key !== "work_item",
                "pl-4": index === 0 && enableSelection,
              })}
            >
              {col.key === "work_item" ? title : t(col.i18nKey)}
            </h6>
          ))}
        </div>
      </Row>

      <Row variant={ERowVariant.HUGGING} className="h-max min-h-full bg-surface-1">
        {sidebarToRender &&
          sidebarToRender({
            title,
            blockUpdateHandler,
            blockIds,
            timelineRows,
            sidebarWidth,
            visibleColumns,
            enableReorder,
            enableSelection,
            canLoadMoreBlocks,
            ganttContainerRef,
            loadMoreBlocks,
            selectionHelpers,
            showAllBlocks,
            onToggleGroupCollapse,
            isEpic,
          })}
      </Row>
    </Row>
  );
});
