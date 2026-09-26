/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Button } from "@plane/propel/button";
import type { InsightChartData, InsightChartRow } from "../cells";
import { WidgetDrilldownDrawer } from "./widget-drilldown-drawer";

type Props = {
  workspaceSlug: string;
  dashboardId: string;
  widgetId: string;
  chartData: InsightChartData | null;
  canDrilldown: boolean;
  onDrilldown: (group: string | null, series: string | null) => void;
  /**
   * Surfaces without a dashboard instance (the fixed Workspace Dashboard) pass
   * this to open the generic Analytics V2 drill-down drawer instead of the
   * dashboard-scoped one. Omitted → unchanged dashboard behaviour.
   */
  onOpenWorkItems?: () => void;
};

/**
 * §12.2 — work-item table renderer: the aggregate cross-tab, or a lazy
 * drill-down drawer when the card has no rows to show.
 */
export function WorkItemTableRenderer({
  workspaceSlug,
  dashboardId,
  widgetId,
  chartData,
  canDrilldown,
  onDrilldown,
  onOpenWorkItems,
}: Props) {
  const [open, setOpen] = useState(false);
  if (chartData && chartData.rows.length > 0) {
    return (
      <table className="w-full text-12">
        <thead>
          <tr className="border-b border-subtle text-tertiary">
            <th className="px-2 py-1 text-left">Group</th>
            {chartData.seriesKeys.map((key) => (
              <th key={key} className="px-2 py-1 text-right">
                {chartData.schema[key]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chartData.rows.map((row: InsightChartRow) => (
            <tr key={String(row.__group)} className="border-b border-subtle">
              <td className="px-2 py-1">{row.name}</td>
              {chartData.seriesKeys.map((key) => (
                <td key={key} className="px-2 py-1 text-right">
                  {canDrilldown ? (
                    <button type="button" className="hover:bg-layer-1" onClick={() => onDrilldown(row.__group, key)}>
                      {row.__display[key] ?? "—"}
                    </button>
                  ) : (
                    (row.__display[key] ?? "—")
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Button variant="secondary" size="sm" onClick={() => (onOpenWorkItems ? onOpenWorkItems() : setOpen(true))}>
        View work items
      </Button>
      {onOpenWorkItems ? null : open ? (
        <WidgetDrilldownDrawer
          workspaceSlug={workspaceSlug}
          dashboardId={dashboardId}
          widgetId={widgetId}
          selection={{}}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
}
