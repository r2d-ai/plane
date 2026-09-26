/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import type { TAnalyticsDimensionKey, TAnalyticsDrilldownResponseV2, TAnalyticsMetricKey } from "@plane/types";
import { Button } from "@plane/propel/button";
import { cn } from "@plane/utils";
import { metricUnit } from "@/components/analytics/v2/mapping";
import { formatValue } from "@/components/analytics/v2/cells";
import { useInsightValueResolver } from "@/components/analytics/v2/use-insight-value-resolver";
import { DashboardService } from "@/services/dashboard.service";

const dashboardService = new DashboardService();

type Props = {
  workspaceSlug: string;
  dashboardId: string;
  widgetId: string;
  selection: Record<string, string | string[] | null>;
  metricKey?: TAnalyticsMetricKey;
  onClose: () => void;
};

export function WidgetDrilldownDrawer(props: Props) {
  const { workspaceSlug, dashboardId, widgetId, selection, metricKey = "work_item_count", onClose } = props;
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const resolve = useInsightValueResolver();

  const { data, isLoading, error } = useSWR(
    `dashboard-drilldown-${workspaceSlug}-${dashboardId}-${widgetId}-${page}-${JSON.stringify(selection)}`,
    () =>
      dashboardService.postDashboardWidgetDrilldown(workspaceSlug, dashboardId, widgetId, {
        selection,
        page,
        page_size: pageSize,
      })
  );

  const drill = data as TAnalyticsDrilldownResponseV2 | undefined;
  const unit = metricUnit(metricKey);
  const primaryKey = (Object.keys(selection)[0] as TAnalyticsDimensionKey | undefined) ?? null;

  const selectionLabel = useMemo(() => {
    if (!primaryKey) return null;
    const raw = selection[primaryKey];
    const value = Array.isArray(raw) ? (raw[0] ?? null) : (raw ?? null);
    return value === null ? null : resolve(primaryKey, String(value));
  }, [primaryKey, resolve, selection]);

  const pageCount = drill ? Math.max(1, Math.ceil(drill.total / (drill.page_size || pageSize))) : 1;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" aria-label="Close drill-down" className="absolute inset-0 bg-backdrop" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-md flex-col border-l border-subtle bg-surface-1 shadow-raised-200">
        <header className="flex items-start justify-between gap-3 border-b border-subtle px-5 py-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-16 font-medium">Workload details</h2>
            {selectionLabel ? <p className="text-13 text-tertiary">{selectionLabel}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="grid place-items-center rounded-sm p-1 hover:bg-layer-1">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex items-center justify-between gap-2 border-b border-subtle px-5 py-3">
          <div className="text-13 text-secondary">
            {isLoading ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
              </span>
            ) : drill ? (
              <>
                {drill.total} matching work items
                {drill.contributions?.[metricKey] !== undefined
                  ? ` · ${formatValue(drill.contributions[metricKey], unit)}`
                  : null}
              </>
            ) : (
              "—"
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-12 text-tertiary">
              {page} / {pageCount}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= pageCount || isLoading}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-3">
          {error ? (
            <p className="text-danger text-13">Could not load drill-down.</p>
          ) : isLoading ? null : !drill?.rows?.length ? (
            <EmptyStateCompact assetKey="unknown" title="No matching work items" rootClassName="py-8" />
          ) : (
            <ul className="flex flex-col gap-2">
              {drill.rows.map((row) => (
                <li
                  key={row.id}
                  className={cn("rounded-md border border-subtle px-3 py-2 text-13", "hover:bg-layer-1")}
                >
                  <div className="font-medium text-primary">{row.name}</div>
                  <div className="text-12 text-tertiary">#{row.sequence_id}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
