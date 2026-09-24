/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Popover } from "@plane/propel/popover";
import { Tooltip } from "@plane/propel/tooltip";
import { ControlLink } from "@plane/ui";
import { Avatar } from "@plane/ui";
import { generateWorkItemLink, getFileURL } from "@plane/utils";
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssues } from "@/hooks/store/use-issues";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import useIssuePeekOverviewRedirection from "@/hooks/use-issue-peek-overview-redirection";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { WorkItemPreviewCard } from "../../preview-card";
import { getBlockViewDetails } from "../utils";
import type { GanttStoreType } from "./base-gantt-root";

type Props = {
  issueId: string;
  isEpic?: boolean;
};

export const IssueGanttBlock = observer(function IssueGanttBlock(props: Props) {
  const { issueId, isEpic } = props;
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  const { getProjectStates } = useProjectState();
  const { getUserDetails } = useMember();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { isMobile } = usePlatformOS();
  const { handleRedirection } = useIssuePeekOverviewRedirection(isEpic);
  const storeType = useIssueStoreType() as GanttStoreType;
  const { issuesFilter } = useIssues(storeType);
  const { getBlockById } = useTimeLineChartStore();

  const issueDetails = getIssueById(issueId);
  const stateDetails =
    issueDetails && getProjectStates(issueDetails?.project_id)?.find((state) => state?.id == issueDetails?.state_id);

  const { blockStyle } = getBlockViewDetails(issueDetails, stateDetails?.color ?? "");

  const handleIssuePeekOverview = () => handleRedirection(workspaceSlug, issueDetails, isMobile);

  const assigneeIds = issueDetails?.assignee_ids ?? [];
  const barWidth = getBlockById(issueId)?.position?.width ?? 0;
  const showAssignees =
    (issuesFilter?.issueFilters?.displayProperties?.assignee ?? true) && assigneeIds.length > 0 && barWidth > 48;
  const showAssigneeName = barWidth > 200;
  const showTitle = barWidth > 80;

  return (
    <Popover delay={100} openOnHover>
      <Popover.Button
        className="w-full"
        render={
          // oxlint-disable-next-line jsx_a11y/click-events-have-key-events jsx_a11y/no-static-element-interactions
          <div
            id={`issue-${issueId}`}
            className="relative flex h-full w-full cursor-pointer items-center rounded-sm"
            style={blockStyle}
            onClick={handleIssuePeekOverview}
          >
            <div className="absolute top-0 left-0 h-full w-full bg-surface-1/50" />
            <div className="relative flex h-full w-full items-center gap-1.5 overflow-hidden px-2 py-1">
              {showTitle && <span className="min-w-0 flex-1 truncate text-13 text-primary">{issueDetails?.name}</span>}
              {showAssignees && (
                <div className="ml-auto flex flex-shrink-0 items-center gap-1">
                  {assigneeIds.slice(0, barWidth > 120 ? 2 : 1).map((assigneeId) => {
                    const member = getUserDetails(assigneeId);
                    if (!member) return null;
                    return (
                      <Avatar
                        key={assigneeId}
                        name={member.display_name}
                        src={getFileURL(member.avatar_url)}
                        size="sm"
                        showTooltip
                      />
                    );
                  })}
                  {assigneeIds.length > 2 && barWidth > 120 && (
                    <span className="text-11 text-tertiary">+{assigneeIds.length - 2}</span>
                  )}
                  {showAssigneeName && assigneeIds.length === 1 && (
                    <span className="max-w-[80px] truncate text-11 text-secondary">
                      {getUserDetails(assigneeIds[0])?.display_name}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        }
      />
      <Popover.Panel side="bottom" align="start">
        {issueDetails && issueDetails?.project_id && (
          <WorkItemPreviewCard
            projectId={issueDetails.project_id}
            stateDetails={{ id: issueDetails.state_id ?? undefined }}
            workItem={issueDetails}
          />
        )}
      </Popover.Panel>
    </Popover>
  );
});

export const IssueGanttSidebarBlock = observer(function IssueGanttSidebarBlock(props: Props) {
  const { issueId, isEpic = false } = props;
  const { workspaceSlug: routerWorkspaceSlug } = useParams();
  const workspaceSlug = routerWorkspaceSlug?.toString();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { isMobile } = usePlatformOS();
  const storeType = useIssueStoreType() as GanttStoreType;
  const { issuesFilter } = useIssues(storeType);
  const { getProjectIdentifierById } = useProject();
  const { handleRedirection } = useIssuePeekOverviewRedirection(isEpic);

  const issueDetails = getIssueById(issueId);
  const projectIdentifier = getProjectIdentifierById(issueDetails?.project_id);

  const handleIssuePeekOverview = (e: any) => {
    e.stopPropagation(true);
    e.preventDefault();
    handleRedirection(workspaceSlug, issueDetails, isMobile);
  };

  const workItemLink = generateWorkItemLink({
    workspaceSlug,
    projectId: issueDetails?.project_id,
    issueId,
    projectIdentifier,
    sequenceId: issueDetails?.sequence_id,
    isEpic,
  });

  return (
    <ControlLink
      id={`issue-${issueId}`}
      href={workItemLink}
      onClick={handleIssuePeekOverview}
      className="line-clamp-1 w-full cursor-pointer text-13 text-primary"
      disabled={!!issueDetails?.tempId}
    >
      <div className="relative flex h-full w-full cursor-pointer items-center gap-2">
        {issueDetails?.project_id && (
          <IssueIdentifier
            issueId={issueDetails.id}
            projectId={issueDetails.project_id}
            size="xs"
            variant="tertiary"
            displayProperties={issuesFilter?.issueFilters?.displayProperties}
          />
        )}
        <Tooltip tooltipContent={issueDetails?.name} isMobile={isMobile}>
          <span className="flex-grow truncate text-13 font-medium">{issueDetails?.name}</span>
        </Tooltip>
      </div>
    </ControlLink>
  );
});
