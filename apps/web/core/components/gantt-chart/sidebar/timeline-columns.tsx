/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";
import { Avatar } from "@plane/ui";
import { findTotalDaysInRange, getFileURL } from "@plane/utils";
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
import { useMember } from "@/hooks/store/use-member";
import { useProjectState } from "@/hooks/store/use-project-state";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";

export const GANTT_COLUMN_DEFINITIONS: {
  key: TGanttColumnKey;
  i18nKey: string;
  required?: boolean;
}[] = [
  { key: "work_item", i18nKey: "gantt.columns.work_item", required: true },
  { key: "status", i18nKey: "gantt.columns.status" },
  { key: "assignee", i18nKey: "gantt.columns.assignee" },
  { key: "duration", i18nKey: "common.duration" },
  { key: "priority", i18nKey: "gantt.columns.priority" },
  { key: "module", i18nKey: "gantt.columns.module" },
  { key: "labels", i18nKey: "gantt.columns.labels" },
  { key: "start_date", i18nKey: "gantt.columns.start_date" },
  { key: "target_date", i18nKey: "gantt.columns.target_date" },
  { key: "estimate", i18nKey: "gantt.columns.estimate" },
];

type ColumnCellProps = {
  columnKey: TGanttColumnKey;
  issue: TIssue;
  isEpic?: boolean;
};

export const TimelineColumnCell = observer(function TimelineColumnCell(props: ColumnCellProps) {
  const { columnKey, issue } = props;
  const { t } = useTranslation();
  const { getProjectStates } = useProjectState();
  const { getUserDetails } = useMember();

  const stateDetails = getProjectStates(issue.project_id)?.find((s) => s.id === issue.state_id);

  switch (columnKey) {
    case "work_item":
      if (!issue.project_id) return null;
      return (
        <IssueIdentifier
          issueId={issue.id}
          projectId={issue.project_id}
          size="xs"
          variant="tertiary"
          displayProperties={{ key: true }}
        />
      );
    case "status":
      return (
        <span className="truncate text-13 text-secondary" title={stateDetails?.name}>
          {stateDetails?.name ?? "—"}
        </span>
      );
    case "assignee": {
      const assigneeIds = issue.assignee_ids ?? [];
      if (assigneeIds.length === 0) return <span className="text-13 text-tertiary">{t("common.none")}</span>;
      const first = getUserDetails(assigneeIds[0]);
      return (
        <div className="flex items-center gap-1 truncate">
          {first && <Avatar name={first.display_name} src={getFileURL(first.avatar_url)} size="sm" showTooltip />}
          {assigneeIds.length > 1 && <span className="text-11 text-tertiary">+{assigneeIds.length - 1}</span>}
        </div>
      );
    }
    case "duration": {
      const days = findTotalDaysInRange(issue.start_date, issue.target_date);
      if (!days) return <span className="text-13 text-tertiary">—</span>;
      return (
        <span className="text-13 text-secondary">
          {days} {days > 1 ? t("gantt.days") : t("gantt.day")}
        </span>
      );
    }
    case "priority":
      return <span className="truncate text-13 text-secondary capitalize">{issue.priority ?? "—"}</span>;
    case "start_date":
      return <span className="truncate text-13 text-secondary">{issue.start_date ?? "—"}</span>;
    case "target_date":
      return <span className="truncate text-13 text-secondary">{issue.target_date ?? "—"}</span>;
    case "module":
    case "labels":
    case "estimate":
      return <span className="truncate text-13 text-tertiary">—</span>;
    default:
      return null;
  }
});
