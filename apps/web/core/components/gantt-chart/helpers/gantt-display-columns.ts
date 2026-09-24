/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IIssueDisplayProperties } from "@plane/types";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";

const DISPLAY_PROPERTY_TO_GANTT_COLUMN: Partial<Record<keyof IIssueDisplayProperties, TGanttColumnKey>> = {
  state: "status",
  assignee: "assignee",
  priority: "priority",
  modules: "module",
  labels: "labels",
  start_date: "start_date",
  due_date: "target_date",
  estimate: "estimate",
};

const GANTT_COLUMN_ORDER: TGanttColumnKey[] = [
  "status",
  "assignee",
  "duration",
  "priority",
  "module",
  "labels",
  "start_date",
  "target_date",
  "estimate",
];

export const getGanttVisibleColumnsFromDisplayProperties = (
  displayProperties: IIssueDisplayProperties | undefined
): TGanttColumnKey[] => {
  const columns: TGanttColumnKey[] = ["work_item"];

  if (!displayProperties) return columns;

  const enabledColumns = new Set<TGanttColumnKey>();

  for (const [property, column] of Object.entries(DISPLAY_PROPERTY_TO_GANTT_COLUMN)) {
    if (displayProperties[property as keyof IIssueDisplayProperties]) {
      enabledColumns.add(column);
    }
  }

  if (displayProperties.start_date && displayProperties.due_date) {
    enabledColumns.add("duration");
  }

  for (const column of GANTT_COLUMN_ORDER) {
    if (enabledColumns.has(column)) {
      columns.push(column);
    }
  }

  return columns;
};
