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

import { useMemo, useState } from "react";
import { Link } from "react-router";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Star } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TDashboardListTab } from "@plane/types";
import { Button, Input, ModalCore } from "@plane/ui";
import { SimpleEmptyState } from "@/components/empty-state/simple-empty-state-root";
import { useUser } from "@/hooks/store/user";
import { useProject } from "@/hooks/store/use-project";
import { DashboardService } from "@/services/dashboard.service";
import { DASHBOARD_LIST_TABS } from "../constants";
import { filterDashboardsByTab } from "../list/filter";
import { buildDashboardTimePatch } from "../detail/dashboard-header";

type Props = {
  workspaceSlug: string;
};

const dashboardService = new DashboardService();

export function WorkspaceDashboardListRoot({ workspaceSlug }: Props) {
  const { t } = useTranslation();
  const { data: currentUser } = useUser();
  const { joinedProjectIds, getProjectById } = useProject();
  const [tab, setTab] = useState<TDashboardListTab>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);

  const listKey = `workspace-dashboards-${workspaceSlug}`;
  const { data, error, isLoading, mutate } = useSWR(listKey, () =>
    dashboardService.getWorkspaceDashboards(workspaceSlug)
  );

  const filtered = useMemo(() => filterDashboardsByTab(data ?? [], tab, currentUser?.id), [data, tab, currentUser?.id]);

  const tabOptions = DASHBOARD_LIST_TABS.map((value) => ({
    value,
    label: t(`dashboard_shell.tabs.${value}`),
  }));

  const handleCreate = async () => {
    if (!name.trim() || selectedProjects.length === 0) return;
    setCreating(true);
    try {
      await dashboardService.createWorkspaceDashboard(workspaceSlug, {
        name: name.trim(),
        project_ids: selectedProjects,
        visibility: "private",
        default_time_scope: buildDashboardTimePatch("this_quarter"),
      });
      setCreateOpen(false);
      setName("");
      setSelectedProjects([]);
      await mutate();
    } finally {
      setCreating(false);
    }
  };

  const toggleFavorite = async (dashboardId: string, favorited?: boolean) => {
    if (favorited) await dashboardService.unfavoriteWorkspaceDashboard(workspaceSlug, dashboardId);
    else await dashboardService.favoriteWorkspaceDashboard(workspaceSlug, dashboardId);
    await mutate();
  };

  if (isLoading) {
    return <div className="p-6 text-13 text-tertiary">{t("dashboard_shell.loading")}</div>;
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
        <SimpleEmptyState
          title={t("dashboard_shell.error.title")}
          description={t("dashboard_shell.error.description")}
        />
        <Button variant="neutral-primary" onClick={() => void mutate()}>
          {t("dashboard_shell.widget.retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-20 font-semibold text-primary">{t("dashboard_shell.title")}</h1>
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          {t("dashboard_shell.actions.create")}
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabOptions.map((option) => (
          <Button
            key={option.value}
            size="sm"
            variant={tab === option.value ? "primary" : "neutral-primary"}
            onClick={() => setTab(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <SimpleEmptyState
            title={t("dashboard_shell.empty_list.title")}
            description={t("dashboard_shell.empty_list.description")}
          />
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            {t("dashboard_shell.actions.create")}
          </Button>
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((dashboard) => (
            <li key={dashboard.id} className="rounded-md border border-subtle bg-surface-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link
                    to={`/${workspaceSlug}/dashboards/${dashboard.id}`}
                    className="text-15 font-medium text-primary hover:underline"
                  >
                    {dashboard.name}
                  </Link>
                  {dashboard.description ? (
                    <p className="mt-1 line-clamp-2 text-12 text-tertiary">{dashboard.description}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="text-tertiary hover:text-primary"
                  onClick={() => void toggleFavorite(dashboard.id, dashboard.is_favorited)}
                  aria-label={t("dashboard_shell.actions.favorite")}
                >
                  <Star className={dashboard.is_favorited ? "fill-current text-accent-primary" : "h-4 w-4"} />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-11 text-tertiary">
                <span>
                  {t("dashboard_shell.meta.projects")} {dashboard.projects?.length ?? 0}
                </span>
                {dashboard.updated_at ? (
                  <span>
                    {t("dashboard_shell.meta.updated")}{" "}
                    {formatDistanceToNow(new Date(dashboard.updated_at), { addSuffix: true })}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      <ModalCore isOpen={createOpen} handleClose={() => setCreateOpen(false)}>
        <div className="space-y-4 p-6">
          <h2 className="text-16 font-medium">{t("dashboard_shell.create.title")}</h2>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("dashboard_shell.create.name")}
          />
          <div className="flex flex-wrap gap-2">
            {joinedProjectIds.map((projectId) => {
              const selected = selectedProjects.includes(projectId);
              return (
                <Button
                  key={projectId}
                  size="sm"
                  variant={selected ? "primary" : "neutral-primary"}
                  onClick={() =>
                    setSelectedProjects((prev) =>
                      selected ? prev.filter((id) => id !== projectId) : [...prev, projectId]
                    )
                  }
                >
                  {getProjectById(projectId)?.name ?? projectId}
                </Button>
              );
            })}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="neutral-primary" onClick={() => setCreateOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              variant="primary"
              loading={creating}
              disabled={!name.trim() || selectedProjects.length === 0}
              onClick={() => void handleCreate()}
            >
              {t("dashboard_shell.actions.create")}
            </Button>
          </div>
        </div>
      </ModalCore>
    </div>
  );
}
