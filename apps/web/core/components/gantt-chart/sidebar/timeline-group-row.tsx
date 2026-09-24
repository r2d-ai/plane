/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@plane/utils";
import { BLOCK_HEIGHT } from "../constants";
import type { TimelineGroupRow } from "../types/timeline-row";

type Props = {
  row: TimelineGroupRow;
  onToggle?: (groupId: string) => void;
  sidebarWidth: number;
};

export function TimelineGroupRowSidebar(props: Props) {
  const { row, onToggle, sidebarWidth } = props;

  return (
    <button
      type="button"
      className="sticky left-0 z-[4] flex w-full cursor-pointer items-center gap-2 border-b-[0.5px] border-subtle-1 bg-surface-2 px-3 text-left text-13 font-medium text-secondary hover:bg-layer-1"
      style={{ height: `${BLOCK_HEIGHT}px`, width: `${sidebarWidth}px` }}
      onClick={() => onToggle?.(row.groupId)}
      aria-expanded={!row.collapsed}
    >
      {row.collapsed ? (
        <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" />
      ) : (
        <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" />
      )}
      <span className="truncate">{row.label}</span>
      <span className={cn("ml-auto flex-shrink-0 text-11 text-tertiary")}>{row.count}</span>
    </button>
  );
}
