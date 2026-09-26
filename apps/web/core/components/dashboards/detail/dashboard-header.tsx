/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * FROZEN -- legacy dashboard-builder surface, scheduled for deletion in Phase D of RD-475.
 * Product spec: docs/workspace-dashboards-analytics-v2-spec.md
 * Do not add features, extend behaviour, or wire up new consumers here. The fixed
 * Workspace Dashboard replaces this surface; see RD-475 for the migration table.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import type { TAnalyticsTimePreset, TDashboardViewMode, TWorkspaceDashboardDetail } from "@plane/types";
import { Button, CustomSearchSelect } from "@plane/ui";
import { ProjectSelect } from "@/components/analytics/select/project";
import { useProject } from "@/hooks/store/use-project";
import { DASHBOARD_TIME_PRESET_OPTIONS } from "../constants";
import { dashboardTimeScopeFromPreset } from "../time-scope";

type Props = {
  dashboard: TWorkspaceDashboardDetail;
  mode: TDashboardViewMode;
  canEdit: boolean;
  selectedProjectIds: string[];
  timePreset: TAnalyticsTimePreset;
  onProjectsChange: (ids: string[]) => void;
  onTimePresetChange: (preset: TAnalyticsTimePreset) => void;
  onToggleMode: () => void;
  onAddMarkdownWidget: () => void;
};

export const DashboardDetailHeader = observer(function DashboardDetailHeader({
  dashboard,
  mode,
  canEdit,
  selectedProjectIds,
  timePreset,
  onProjectsChange,
  onTimePresetChange,
  onToggleMode,
  onAddMarkdownWidget,
}: Props) {
  const { t } = useTranslation();
  const { joinedProjectIds } = useProject();

  const timeOptions = DASHBOARD_TIME_PRESET_OPTIONS.map((option) => ({
    value: option.value,
    query: t(option.labelKey),
    content: <span>{t(option.labelKey)}</span>,
  }));

  return (
    <div className="flex flex-col gap-3 border-b border-subtle px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-18 font-semibold text-primary">{dashboard.name}</h1>
          <p className="text-12 text-tertiary capitalize">{dashboard.visibility}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {mode === "edit" && canEdit ? (
            <Button variant="neutral-primary" size="sm" onClick={onAddMarkdownWidget}>
              {t("dashboard_shell.header.add_widget")}
            </Button>
          ) : null}
          {canEdit ? (
            <Button variant="primary" size="sm" onClick={onToggleMode}>
              {mode === "edit" ? t("dashboard_shell.actions.view") : t("dashboard_shell.actions.edit")}
            </Button>
          ) : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ProjectSelect
          value={selectedProjectIds}
          onChange={(val) => {
            if (mode === "edit" && canEdit) onProjectsChange(val ?? []);
          }}
          projectIds={joinedProjectIds}
        />
        <CustomSearchSelect
          value={[timePreset]}
          onChange={(val) => onTimePresetChange(val as TAnalyticsTimePreset)}
          options={timeOptions}
          label={t("dashboard_shell.header.time_range")}
        />
      </div>
      {mode === "view" ? null : <p className="text-12 text-tertiary">{t("dashboard_shell.header.edit_hint")}</p>}
    </div>
  );
});

export function buildDashboardTimePatch(preset: TAnalyticsTimePreset) {
  return dashboardTimeScopeFromPreset(preset);
}
