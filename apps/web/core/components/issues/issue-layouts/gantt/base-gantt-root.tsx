/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useEffect, useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { EIssueFilterType, EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type {
  EIssuesStoreType,
  GroupByColumnTypes,
  IBlockUpdateData,
  TGroupedIssues,
  TIssue,
  TIssueKanbanFilters,
} from "@plane/types";
import { EIssueLayoutTypes, GANTT_TIMELINE_TYPE } from "@plane/types";
import { renderFormattedPayloadDate } from "@plane/utils";
import { getGanttVisibleColumnsFromDisplayProperties } from "@/components/gantt-chart/helpers/gantt-display-columns";
import { buildTimelineRows, getIssueIdsFromTimelineRows } from "@/components/gantt-chart/helpers/timeline-rows";
import { TimeLineTypeContext } from "@/components/gantt-chart/contexts";
import { GanttChartRoot } from "@/components/gantt-chart/root";
import { IssueGanttSidebar } from "@/components/gantt-chart/sidebar/issues/sidebar";
import { useIssues } from "@/hooks/store/use-issues";
import { useUserPermissions } from "@/hooks/store/user";
import { useGanttPreferences } from "@/hooks/use-gantt-preferences";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";
import { useIssuesActions } from "@/hooks/use-issues-actions";
import { useTimeLineChart } from "@/hooks/use-timeline-chart";
import { useBulkOperationStatus } from "@/hooks/use-bulk-operation-status";
import { IssueLayoutHOC } from "../issue-layout-HOC";
import { GanttQuickAddIssueButton, QuickAddIssueRoot } from "../quick-add";
import { getGroupByColumns, isWorkspaceLevel } from "../utils";
import { IssueGanttBlock } from "./blocks";

interface IBaseGanttRoot {
  viewId?: string | undefined;
  isCompletedCycle?: boolean;
  isEpic?: boolean;
}

export type GanttStoreType =
  | EIssuesStoreType.PROJECT
  | EIssuesStoreType.MODULE
  | EIssuesStoreType.CYCLE
  | EIssuesStoreType.PROJECT_VIEW
  | EIssuesStoreType.EPIC;

export const BaseGanttRoot = observer(function BaseGanttRoot(props: IBaseGanttRoot) {
  const { viewId, isCompletedCycle = false, isEpic = false } = props;
  const { t } = useTranslation();
  const { workspaceSlug, projectId } = useParams();

  const storeType = useIssueStoreType() as GanttStoreType;
  const { issues, issuesFilter } = useIssues(storeType);
  const { fetchIssues, fetchNextIssues, updateIssue, quickAddIssue, updateFilters } = useIssuesActions(storeType);
  const { initGantt, updateCurrentView } = useTimeLineChart(GANTT_TIMELINE_TYPE.ISSUE);
  const { allowPermissions } = useUserPermissions();
  const isBulkOperationsEnabled = useBulkOperationStatus();

  const entityId = viewId ?? projectId?.toString() ?? "default";
  const { preferences, updatePreferences, isLoaded } = useGanttPreferences(workspaceSlug?.toString(), entityId);

  const appliedDisplayFilters = issuesFilter.issueFilters?.displayFilters;
  const displayProperties = issuesFilter.issueFilters?.displayProperties;
  const group_by = (appliedDisplayFilters?.group_by ?? null) as GroupByColumnTypes | null;
  const showEmptyGroup = appliedDisplayFilters?.show_empty_groups ?? false;
  const collapsedGroups = issuesFilter?.issueFilters?.kanbanFilters;

  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 1);

  useEffect(() => {
    fetchIssues("init-loader", { canGroup: !!group_by, perPageCount: group_by ? 50 : 100 }, viewId);
  }, [fetchIssues, storeType, viewId, group_by]);

  useEffect(() => {
    initGantt();
  }, [initGantt]);

  useEffect(() => {
    if (isLoaded) {
      updateCurrentView(preferences.scale);
    }
  }, [isLoaded, preferences.scale, updateCurrentView]);

  const groupedIssueIds = issues.groupedIssueIds as TGroupedIssues | undefined;

  const groups = useMemo(
    () =>
      getGroupByColumns({
        groupBy: group_by,
        includeNone: true,
        isWorkspaceLevel: isWorkspaceLevel(storeType),
        isEpic,
        projectId: projectId?.toString(),
      }),
    [group_by, storeType, isEpic, projectId]
  );

  const timelineRows = useMemo(
    () =>
      buildTimelineRows({
        groupBy: group_by,
        groups,
        groupedIssueIds,
        collapsedGroups: collapsedGroups ?? { group_by: [], sub_group_by: [] },
        showEmptyGroups: showEmptyGroup,
      }),
    [group_by, groups, groupedIssueIds, collapsedGroups, showEmptyGroup]
  );

  const blockIds = useMemo(() => getIssueIdsFromTimelineRows(timelineRows), [timelineRows]);
  const visibleColumns = useMemo(
    () => getGanttVisibleColumnsFromDisplayProperties(displayProperties),
    [displayProperties]
  );
  const nextPageResults = issues.getPaginationData(undefined, undefined)?.nextPageResults;

  const { enableIssueCreation } = issues?.viewFlags || {};

  const loadMoreIssues = useCallback(() => {
    fetchNextIssues();
  }, [fetchNextIssues]);

  const updateIssueBlockStructure = async (issue: TIssue, data: IBlockUpdateData) => {
    if (!workspaceSlug) return;

    const payload: any = { ...data };
    if (data.sort_order) payload.sort_order = data.sort_order.newSortOrder;

    if (updateIssue) {
      await updateIssue(issue.project_id, issue.id, payload);
    }
  };

  const isAllowed = allowPermissions([EUserPermissions.ADMIN, EUserPermissions.MEMBER], EUserPermissionsLevel.PROJECT);

  const updateBlockDates = useCallback(
    (
      updates: {
        id: string;
        start_date?: string;
        target_date?: string;
      }[]
    ) =>
      issues.updateIssueDates(workspaceSlug.toString(), updates, projectId.toString()).catch(() => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("toast.error"),
          message: "Error while updating work item dates, Please try again Later",
        });
      }),
    [issues, projectId, workspaceSlug, t]
  );

  const handleScaleChange = useCallback(
    (scale: import("@plane/types").TGanttViews) => {
      updatePreferences({ scale });
    },
    [updatePreferences]
  );

  const handleCollapsedGroups = useCallback(
    (value: string) => {
      if (!workspaceSlug) return;
      let nextCollapsed = issuesFilter?.issueFilters?.kanbanFilters?.group_by || [];
      if (nextCollapsed.includes(value)) {
        nextCollapsed = nextCollapsed.filter((_value) => _value !== value);
      } else {
        nextCollapsed = [...nextCollapsed, value];
      }
      updateFilters(projectId?.toString() ?? "", EIssueFilterType.KANBAN_FILTERS, {
        group_by: nextCollapsed,
      } as TIssueKanbanFilters);
    },
    [workspaceSlug, issuesFilter, projectId, updateFilters]
  );

  const quickAdd =
    enableIssueCreation && isAllowed && !isCompletedCycle ? (
      <QuickAddIssueRoot
        layout={EIssueLayoutTypes.GANTT}
        QuickAddButton={GanttQuickAddIssueButton}
        containerClassName="sticky bottom-0 z-[1]"
        prePopulatedData={{
          start_date: renderFormattedPayloadDate(new Date()),
          target_date: renderFormattedPayloadDate(targetDate),
        }}
        quickAddCallback={quickAddIssue}
        isEpic={isEpic}
      />
    ) : undefined;

  return (
    <IssueLayoutHOC layout={EIssueLayoutTypes.GANTT}>
      <TimeLineTypeContext.Provider value={GANTT_TIMELINE_TYPE.ISSUE}>
        <div className="h-full w-full overflow-hidden">
          <GanttChartRoot
            border={false}
            title={isEpic ? t("epic.label", { count: 2 }) : t("issue.label", { count: 2 })}
            loaderTitle={isEpic ? t("epic.label", { count: 2 }) : t("issue.label", { count: 2 })}
            blockIds={blockIds}
            timelineRows={timelineRows}
            sidebarWidth={preferences.sidebarWidth}
            visibleColumns={visibleColumns}
            onSidebarWidthChange={(width) => updatePreferences({ sidebarWidth: width })}
            onToggleGroupCollapse={handleCollapsedGroups}
            onScaleChange={handleScaleChange}
            blockUpdateHandler={updateIssueBlockStructure}
            blockToRender={(data: TIssue) => <IssueGanttBlock issueId={data.id} isEpic={isEpic} />}
            sidebarToRender={(sidebarProps) => <IssueGanttSidebar {...sidebarProps} showAllBlocks isEpic={isEpic} />}
            enableBlockLeftResize={isAllowed}
            enableBlockRightResize={isAllowed}
            enableBlockMove={isAllowed}
            enableReorder={appliedDisplayFilters?.order_by === "sort_order" && isAllowed}
            enableAddBlock={isAllowed}
            enableSelection={isBulkOperationsEnabled && isAllowed}
            quickAdd={quickAdd}
            loadMoreBlocks={loadMoreIssues}
            canLoadMoreBlocks={nextPageResults}
            updateBlockDates={updateBlockDates}
            showAllBlocks
            enableDependency
            isEpic={isEpic}
          />
        </div>
      </TimeLineTypeContext.Provider>
    </IssueLayoutHOC>
  );
});
