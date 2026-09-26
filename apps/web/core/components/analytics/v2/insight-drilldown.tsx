/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import type { TAnalyticsDimensionKey, TAnalyticsDrilldownRequestV2, TAnalyticsMetricKey } from "@plane/types";
import { Button } from "@plane/propel/button";
import { cn } from "@plane/utils";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local
import { metricUnit } from "./mapping";
import { formatValue } from "./cells";
import { useInsightValueResolver } from "./use-insight-value-resolver";

const analyticsService = new AnalyticsService();

type Props = {
  workspaceSlug: string;
  request: TAnalyticsDrilldownRequestV2;
  onClose: () => void;
};

/**
 * §25 drill-down: a right-side drawer listing the work items behind a chart
 * segment. The request echoes the *original* aggregate query plus the selected
 * dimension values, so the row set is derived server-side under the same ACL
 * scope — the client never re-filters (§25, §37).
 */
export default function InsightDrilldownDrawer(props: Props) {
  const { workspaceSlug, request, onClose } = props;
  const [page, setPage] = useState(request.page ?? 1);
  const pageSize = request.page_size ?? 25;
  const resolve = useInsightValueResolver();

  const pagedRequest = useMemo(() => ({ ...request, page }), [request, page]);

  const { data, isLoading, error } = useSWR(
    `analytics-v2-drilldown-${workspaceSlug}-${page}-${JSON.stringify(request.selection)}`,
    () => analyticsService.postAnalyticsV2Drilldown(workspaceSlug, pagedRequest)
  );

  const primaryKey = request.query.dimensions?.[0]?.key ?? null;
  const seriesKey: TAnalyticsDimensionKey | null = request.query.dimensions?.[1]?.key ?? null;
  const metricKey: TAnalyticsMetricKey = request.query.metrics?.[0]?.key ?? "work_item_count";
  const unit = metricUnit(metricKey);

  const selectionLabel = (key: TAnalyticsDimensionKey | null): string | null => {
    if (!key) return null;
    const raw = request.selection[key];
    const value = Array.isArray(raw) ? (raw[0] ?? null) : (raw ?? null);
    return value === null ? null : resolve(key, value);
  };

  const pageCount = data ? Math.max(1, Math.ceil(data.total / (data.page_size || pageSize))) : 1;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button type="button" aria-label="Close drill-down" className="absolute inset-0 bg-backdrop" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-md flex-col border-l border-subtle bg-surface-1 shadow-raised-200">
        <header className="flex items-start justify-between gap-3 border-b border-subtle px-5 py-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-16 font-medium">Workload details</h2>
            <p className="text-13 text-tertiary">
              {[selectionLabel(primaryKey), selectionLabel(seriesKey)].filter(Boolean).join(" · ")}
            </p>
          </div>
          <button type="button" onClick={onClose} className="grid place-items-center rounded-sm p-1 hover:bg-layer-1">
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex items-center justify-between gap-2 border-b border-subtle px-5 py-3">
          <div className="text-13 text-secondary">
            {isLoading ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
              </span>
            ) : (
              <>
                <span className="text-primary">{data?.total ?? 0}</span> matching work items
                {data?.contributions?.[metricKey] !== undefined && (
                  <span className="text-tertiary">
                    {" · "}
                    {formatValue(data.contributions[metricKey], unit)}
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {error ? (
            <div className="text-danger px-3 py-6 text-13">Could not load the matching work items.</div>
          ) : isLoading ? (
            <div className="grid place-items-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-secondary" />
            </div>
          ) : (data?.rows?.length ?? 0) > 0 ? (
            <ul className="flex flex-col">
              {data?.rows.map((row) => (
                <li key={row.id} className="flex items-start gap-2 rounded-sm px-3 py-2 hover:bg-layer-1">
                  <span className="bg-custom-300/10 font-mono text-custom-300 mt-0.5 w-fit shrink-0 rounded px-1.5 py-0.5 text-11">
                    {row.sequence_id}
                  </span>
                  <span className="text-13 break-words text-primary">{row.name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyStateCompact
              assetKey="unknown"
              assetClassName="size-20"
              rootClassName="px-5 py-10"
              title="No matching work items"
            />
          )}
        </div>

        <footer
          className={cn(
            "flex items-center justify-between border-t border-subtle px-5 py-3",
            pageCount <= 1 && "hidden"
          )}
        >
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            <ChevronLeft className="h-3.5 w-3.5" /> Previous
          </Button>
          <span className="text-13 text-tertiary">
            Page {page} of {pageCount}
          </span>
          <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => setPage((p) => p + 1)}>
            Next <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </footer>
      </aside>
    </div>
  );
}
