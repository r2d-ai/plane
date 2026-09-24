/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ALL_ISSUES } from "@plane/constants";
import type { GroupByColumnTypes, IGroupByColumn, TGroupedIssues, TIssueKanbanFilters } from "@plane/types";
import type { TimelineRow } from "../types/timeline-row";

type BuildTimelineRowsParams = {
  groupBy: GroupByColumnTypes | null;
  groups: IGroupByColumn[] | undefined;
  groupedIssueIds: TGroupedIssues | undefined;
  collapsedGroups: TIssueKanbanFilters;
  showEmptyGroups: boolean;
};

export const buildTimelineRows = ({
  groupBy,
  groups,
  groupedIssueIds,
  collapsedGroups,
  showEmptyGroups,
}: BuildTimelineRowsParams): TimelineRow[] => {
  if (!groupedIssueIds) return [];

  // Ungrouped: flat issue rows
  if (!groupBy || !groups) {
    const issueIds = (groupedIssueIds[ALL_ISSUES] as string[]) ?? [];
    return issueIds.map((issueId) => ({
      type: "issue" as const,
      rowId: issueId,
      issueId,
    }));
  }

  const collapsedGroupIds = new Set(collapsedGroups.group_by ?? []);
  const rows: TimelineRow[] = [];

  for (const group of groups) {
    const issueIds = (groupedIssueIds[group.id] as string[]) ?? [];
    if (!showEmptyGroups && issueIds.length === 0) continue;

    const collapsed = collapsedGroupIds.has(group.id);

    rows.push({
      type: "group",
      rowId: `group-${group.id}`,
      groupId: group.id,
      label: group.name,
      count: issueIds.length,
      collapsed,
    });

    if (!collapsed) {
      for (const issueId of issueIds) {
        rows.push({
          type: "issue",
          rowId: `${group.id}:${issueId}`,
          issueId,
          groupId: group.id,
        });
      }
    }
  }

  return rows;
};

export const getIssueIdsFromTimelineRows = (rows: TimelineRow[]): string[] => {
  const ids = new Set<string>();
  for (const row of rows) {
    if (row.type === "issue") ids.add(row.issueId);
  }
  return Array.from(ids);
};
