/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IIssueDisplayProperties } from "@plane/types";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";

export const GANTT_DEFAULT_VISIBLE_COLUMNS: TGanttColumnKey[] = ["work_item", "duration"];

export const GANTT_DISPLAY_PROPERTY_KEYS: (keyof IIssueDisplayProperties)[] = [
  "key",
  "issue_type",
  "state",
  "assignee",
  "priority",
  "modules",
  "labels",
  "start_date",
  "due_date",
];

export const GANTT_LAYOUT_DISPLAY_PROPERTIES: Partial<IIssueDisplayProperties> = {
  key: false,
  issue_type: false,
  state: false,
  assignee: false,
  priority: false,
  estimate: false,
  modules: false,
  labels: false,
  start_date: false,
  due_date: false,
};

export const isLegacyDefaultGanttDisplayProperties = (displayProperties: IIssueDisplayProperties): boolean =>
  GANTT_DISPLAY_PROPERTY_KEYS.every((property) => displayProperties[property] !== false);

const OPTIONAL_DISPLAY_PROPERTY_COLUMNS: Partial<Record<keyof IIssueDisplayProperties, TGanttColumnKey>> = {
  priority: "priority",
  modules: "module",
  labels: "labels",
  start_date: "start_date",
  due_date: "target_date",
  estimate: "estimate",
};

const OPTIONAL_COLUMN_ORDER: TGanttColumnKey[] = [
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
  if (!displayProperties) return GANTT_DEFAULT_VISIBLE_COLUMNS;

  const columns: TGanttColumnKey[] = ["work_item"];

  if (displayProperties.state) columns.push("status");
  if (displayProperties.assignee) columns.push("assignee");

  columns.push("duration");

  const optionalColumns = new Set<TGanttColumnKey>();
  for (const [property, column] of Object.entries(OPTIONAL_DISPLAY_PROPERTY_COLUMNS)) {
    if (displayProperties[property as keyof IIssueDisplayProperties]) {
      optionalColumns.add(column);
    }
  }

  for (const column of OPTIONAL_COLUMN_ORDER) {
    if (optionalColumns.has(column)) {
      columns.push(column);
    }
  }

  return columns;
};
