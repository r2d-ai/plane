/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import type { TAnalyticsTimePreset, TDashboardViewMode } from "@plane/types";
import { Button } from "@plane/ui";
import { SimpleEmptyState } from "@/components/empty-state/simple-empty-state-root";
import { useUser } from "@/hooks/store/user";
import { DashboardService } from "@/services/dashboard.service";
import { MARKDOWN_PLACEHOLDER_QUERY_CONFIG } from "../constants";
import { defaultLayoutForIndex } from "../layout";
import { buildDashboardTimePatch, DashboardDetailHeader } from "./dashboard-header";
import { DashboardGrid } from "./dashboard-grid";

type Props = {
  workspaceSlug: string;
  dashboardId: string;
};

const dashboardService = new DashboardService();

export function WorkspaceDashboardDetailRoot({ workspaceSlug, dashboardId }: Props) {
  const { t } = useTranslation();
  const { data: currentUser } = useUser();
  const [mode, setMode] = useState<TDashboardViewMode>("view");

  const detailKey = `workspace-dashboard-${workspaceSlug}-${dashboardId}`;
  const {
    data: dashboard,
    error: detailError,
    isLoading: detailLoading,
    mutate: mutateDetail,
  } = useSWR(detailKey, () => dashboardService.getWorkspaceDashboard(workspaceSlug, dashboardId));

  const batchKey = dashboard ? `${detailKey}-data` : null;
  const {
    data: batch,
    isLoading: batchLoading,
    mutate: mutateBatch,
  } = useSWR(batchKey, () => dashboardService.fetchDashboardBatchData(workspaceSlug, dashboardId));

  const timePreset = useMemo(() => {
    const preset = dashboard?.default_time_scope?.preset;
    return (typeof preset === "string" ? preset : "this_quarter") as TAnalyticsTimePreset;
  }, [dashboard?.default_time_scope]);

  const selectedProjectIds = useMemo(() => dashboard?.projects ?? [], [dashboard?.projects]);

  const canEdit = useMemo(() => {
    if (!dashboard || !currentUser) return false;
    return dashboard.owner === currentUser.id || dashboard.visibility === "workspace";
  }, [dashboard, currentUser]);

  const refreshData = useCallback(() => {
    void mutateBatch();
  }, [mutateBatch]);

  const handleTimePresetChange = useCallback(
    async (preset: TAnalyticsTimePreset) => {
      if (!dashboard) return;
      await dashboardService.updateWorkspaceDashboard(workspaceSlug, dashboardId, {
        default_time_scope: buildDashboardTimePatch(preset),
      });
      await mutateDetail();
      await mutateBatch();
    },
    [dashboard, dashboardId, mutateBatch, mutateDetail, workspaceSlug]
  );

  const handleProjectsChange = useCallback(
    async (projectIds: string[]) => {
      await dashboardService.updateWorkspaceDashboard(workspaceSlug, dashboardId, { project_ids: projectIds });
      await mutateDetail();
      await mutateBatch();
    },
    [dashboardId, mutateBatch, mutateDetail, workspaceSlug]
  );

  const handleLayoutPersist = useCallback(
    async (entries: ReturnType<typeof import("../layout").buildLayoutPersistencePayload>) => {
      await dashboardService.updateDashboardLayout(workspaceSlug, dashboardId, entries);
      await mutateDetail();
    },
    [dashboardId, mutateDetail, workspaceSlug]
  );

  const handleAddMarkdownWidget = useCallback(async () => {
    if (!dashboard) return;
    const index = dashboard.widgets?.length ?? 0;
    await dashboardService.createDashboardWidget(workspaceSlug, dashboardId, {
      title: t("dashboard_shell.widget.markdown_title"),
      widget_type: "markdown",
      query_config: MARKDOWN_PLACEHOLDER_QUERY_CONFIG,
      style_config: {
        body: t("dashboard_shell.widget.markdown_placeholder"),
      },
      layout_config: defaultLayoutForIndex(index),
      inherit_time_scope: true,
    });
    await mutateDetail();
    await mutateBatch();
  }, [dashboard, dashboardId, mutateBatch, mutateDetail, t, workspaceSlug]);

  if (detailLoading) {
    return <div className="p-6 text-13 text-tertiary">{t("dashboard_shell.loading")}</div>;
  }

  if (detailError || !dashboard) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
        <SimpleEmptyState
          title={t("dashboard_shell.error.title")}
          description={t("dashboard_shell.error.description")}
        />
        <Button variant="neutral-primary" onClick={() => void mutateDetail()}>
          {t("dashboard_shell.widget.retry")}
        </Button>
      </div>
    );
  }

  const widgets = dashboard.widgets ?? [];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <DashboardDetailHeader
        dashboard={dashboard}
        mode={mode}
        canEdit={canEdit}
        selectedProjectIds={selectedProjectIds}
        timePreset={timePreset}
        onProjectsChange={handleProjectsChange}
        onTimePresetChange={handleTimePresetChange}
        onToggleMode={() => setMode((prev) => (prev === "edit" ? "view" : "edit"))}
        onAddMarkdownWidget={() => void handleAddMarkdownWidget()}
      />
      <div className="flex-1 overflow-y-auto p-5">
        {widgets.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16">
            <SimpleEmptyState
              title={t("dashboard_shell.empty_detail.title")}
              description={t("dashboard_shell.empty_detail.description")}
            />
            {canEdit ? (
              <Button variant="primary" onClick={() => void handleAddMarkdownWidget()}>
                {t("dashboard_shell.header.add_widget")}
              </Button>
            ) : null}
          </div>
        ) : (
          <DashboardGrid
            widgets={widgets}
            batch={batch}
            batchLoading={batchLoading}
            editMode={mode === "edit" && canEdit}
            onLayoutPersist={handleLayoutPersist}
            onRefreshData={refreshData}
          />
        )}
      </div>
    </div>
  );
}
