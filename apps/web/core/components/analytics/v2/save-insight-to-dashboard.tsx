/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { BookmarkPlus, Loader2 } from "lucide-react";
import type { TAnalyticsQueryV2, TDashboardWidgetType, TWorkspaceDashboard } from "@plane/types";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Button } from "@plane/propel/button";
import { EModalPosition, EModalWidth, ModalCore, CustomSelect } from "@plane/ui";
// services
import { isWorkspaceDashboardsEnabled } from "@/helpers/workspace-dashboards-access";
import { useInstance } from "@/hooks/store/use-instance";
import { DashboardService } from "@/services/dashboard.service";

const dashboardService = new DashboardService();

const WIDGET_TYPES: { value: TDashboardWidgetType; label: string }[] = [
  { value: "number", label: "Number" },
  { value: "bar", label: "Bar" },
  { value: "line", label: "Line" },
  { value: "pie", label: "Pie" },
  { value: "donut", label: "Donut" },
  { value: "table", label: "Table" },
];

type Props = {
  /** The AnalyticsQuery V2 configuration to persist (§18.2 — no snapshot). */
  query: TAnalyticsQueryV2 | null;
  defaultTitle: string;
  disabled?: boolean;
};

/**
 * §18.2 Save to dashboard: choose a dashboard, a widget title and a
 * visualization, then persist the *query configuration* — never a snapshot of
 * the current results.
 *
 * Depends on the dashboard CRUD API (RD-453, §33). Until those endpoints ship
 * the picker reports the failure instead of silently dropping the widget.
 */
export default function SaveInsightToDashboard(props: Props) {
  const { query, defaultTitle, disabled } = props;
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const { config } = useInstance();

  if (!isWorkspaceDashboardsEnabled(config)) {
    return null;
  }

  const [isOpen, setIsOpen] = useState(false);
  const [dashboardId, setDashboardId] = useState<string | undefined>(undefined);
  const [title, setTitle] = useState(defaultTitle);
  const [widgetType, setWidgetType] = useState<TDashboardWidgetType>("bar");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    data: dashboards,
    isLoading,
    error,
  } = useSWR(isOpen && slug ? `workspace-dashboards-${slug}` : null, () =>
    dashboardService.getWorkspaceDashboards(slug)
  );

  useEffect(() => {
    if (isOpen) setTitle(defaultTitle);
  }, [defaultTitle, isOpen]);

  useEffect(() => {
    if (!dashboardId && dashboards && dashboards.length > 0) setDashboardId(dashboards[0]?.id);
  }, [dashboardId, dashboards]);

  const handleClose = () => {
    setIsOpen(false);
    setIsSubmitting(false);
  };

  const handleSave = async () => {
    if (!query || !dashboardId || !title.trim()) return;
    setIsSubmitting(true);
    try {
      await dashboardService.createDashboardWidget(slug, dashboardId, {
        title: title.trim(),
        widget_type: widgetType,
        query_config: { ...query, schema_version: 1 },
      });
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Saved to dashboard" });
      handleClose();
    } catch (err) {
      const payload = (err ?? {}) as { detail?: string; error?: string };
      const message = payload.detail || payload.error || "Could not save this insight to a dashboard.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Save failed", message });
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        prependIcon={<BookmarkPlus className="h-3.5 w-3.5" />}
        onClick={() => setIsOpen(true)}
        disabled={disabled || !query}
      >
        Save to dashboard
      </Button>

      <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.CENTER} width={EModalWidth.LG}>
        <div className="flex flex-col gap-5 p-6">
          <div>
            <h2 className="text-16 font-medium">Save to dashboard</h2>
            <p className="mt-1 text-13 text-tertiary">
              The widget stores this query configuration and re-evaluates it whenever the dashboard is opened.
            </p>
          </div>

          <label className="flex flex-col gap-1.5">
            <span className="text-13 text-secondary">Dashboard</span>
            {isLoading ? (
              <span className="inline-flex items-center gap-2 text-13 text-tertiary">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading dashboards…
              </span>
            ) : error ? (
              <span className="text-danger text-13">
                Dashboard API unavailable — this lands with RD-453 (§33). No widget was saved.
              </span>
            ) : (dashboards?.length ?? 0) === 0 ? (
              <span className="text-13 text-tertiary">No dashboards yet. Create one first.</span>
            ) : (
              <CustomSelect
                value={dashboardId}
                label={
                  dashboards?.find((dashboard: TWorkspaceDashboard) => dashboard.id === dashboardId)?.name ?? "Select"
                }
                onChange={(val: string) => setDashboardId(val)}
                maxHeight="lg"
              >
                {(dashboards ?? []).map((dashboard) => (
                  <CustomSelect.Option key={dashboard.id} value={dashboard.id}>
                    {dashboard.name}
                  </CustomSelect.Option>
                ))}
              </CustomSelect>
            )}
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-13 text-secondary">Widget title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="focus:border-custom-300 h-9 w-full rounded-md border border-subtle bg-transparent px-2.5 text-13 text-primary outline-none"
              placeholder="Widget title"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-13 text-secondary">Visualization</span>
            <CustomSelect
              value={widgetType}
              label={WIDGET_TYPES.find((option) => option.value === widgetType)?.label ?? "Bar"}
              onChange={(val: TDashboardWidgetType) => setWidgetType(val)}
              maxHeight="lg"
            >
              {WIDGET_TYPES.map((option) => (
                <CustomSelect.Option key={option.value} value={option.value}>
                  {option.label}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </label>

          <div className="flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              loading={isSubmitting}
              disabled={isSubmitting || !query || !dashboardId || !title.trim()}
            >
              Save
            </Button>
          </div>
        </div>
      </ModalCore>
    </>
  );
}
