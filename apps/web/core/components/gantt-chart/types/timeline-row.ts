/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TimelineGroupRow = {
  type: "group";
  rowId: string;
  groupId: string;
  label: string;
  count: number;
  collapsed: boolean;
};

export type TimelineIssueRow = {
  type: "issue";
  rowId: string;
  issueId: string;
  groupId?: string;
};

export type TimelineRow = TimelineGroupRow | TimelineIssueRow;

export const isTimelineGroupRow = (row: TimelineRow): row is TimelineGroupRow => row.type === "group";

export const isTimelineIssueRow = (row: TimelineRow): row is TimelineIssueRow => row.type === "issue";
