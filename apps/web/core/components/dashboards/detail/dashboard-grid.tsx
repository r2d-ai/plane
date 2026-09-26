/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import type { TDashboardBatchDataResponse, TWorkspaceDashboardWidget } from "@plane/types";
import { DASHBOARD_GRID_COLUMNS } from "../constants";
import {
  buildLayoutPersistencePayload,
  gridItemStyle,
  mobileStackOrder,
  moveGridItem,
  normalizeGridLayout,
  resizeGridItem,
  type TDashboardGridItem,
} from "../layout";
import { DashboardWidgetShell } from "./widget-shell";

type Props = {
  widgets: TWorkspaceDashboardWidget[];
  batch?: TDashboardBatchDataResponse;
  batchLoading: boolean;
  editMode: boolean;
  onLayoutPersist: (layout: ReturnType<typeof buildLayoutPersistencePayload>) => Promise<void>;
  onRefreshData: () => void;
};

export function DashboardGrid({ widgets, batch, batchLoading, editMode, onLayoutPersist, onRefreshData }: Props) {
  const [layout, setLayout] = useState<TDashboardGridItem[]>(() => normalizeGridLayout(widgets));
  const [isMobile, setIsMobile] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  useEffect(() => {
    setLayout(normalizeGridLayout(widgets));
  }, [widgets]);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const mobileOrder = useMemo(() => mobileStackOrder(layout), [layout]);
  const orderedWidgets = useMemo(() => {
    if (!isMobile) return widgets;
    const map = new Map(widgets.map((w) => [w.id, w]));
    return mobileOrder.map((id) => map.get(id)).filter(Boolean) as TWorkspaceDashboardWidget[];
  }, [isMobile, mobileOrder, widgets]);

  const persistLayout = useCallback(
    async (next: TDashboardGridItem[]) => {
      setLayout(next);
      if (!editMode) return;
      await onLayoutPersist(buildLayoutPersistencePayload(next));
    },
    [editMode, onLayoutPersist]
  );

  const handleDragStart = (widgetId: string) => {
    if (!editMode || isMobile) return;
    setDraggingId(widgetId);
  };

  const handleDragOver = (event: React.DragEvent, widgetId: string) => {
    if (!editMode || isMobile || !draggingId || draggingId === widgetId) return;
    event.preventDefault();
    const target = layout.find((item) => item.id === widgetId);
    const dragged = layout.find((item) => item.id === draggingId);
    if (!target || !dragged) return;
    const next = moveGridItem(layout, draggingId, target.x, target.y);
    void persistLayout(next);
  };

  const handleDragEnd = () => setDraggingId(null);

  const handleResize = (widgetId: string, deltaW: number, deltaH: number) => {
    const current = layout.find((item) => item.id === widgetId);
    if (!current || !editMode || isMobile) return;
    const next = resizeGridItem(layout, widgetId, current.w + deltaW, current.h + deltaH);
    void persistLayout(next);
  };

  return (
    <div
      className="grid w-full gap-3"
      style={
        isMobile
          ? { gridTemplateColumns: "1fr" }
          : {
              gridTemplateColumns: `repeat(${DASHBOARD_GRID_COLUMNS}, minmax(0, 1fr))`,
              gridAutoRows: "minmax(72px, auto)",
            }
      }
    >
      {(isMobile ? orderedWidgets : widgets).map((widget) => {
        const item = layout.find((entry) => entry.id === widget.id);
        if (!item) return null;
        return (
          <div
            key={widget.id}
            draggable={editMode && !isMobile}
            onDragStart={() => handleDragStart(widget.id)}
            onDragOver={(event) => handleDragOver(event, widget.id)}
            onDragEnd={handleDragEnd}
            className="shadow-xs relative min-h-[120px] rounded-md border border-subtle bg-surface-2"
            style={gridItemStyle(item, isMobile)}
          >
            {editMode && !isMobile ? (
              <button
                type="button"
                aria-label="Resize widget"
                className="absolute right-1 bottom-1 z-10 h-4 w-4 cursor-se-resize rounded-sm border border-strong bg-surface-1"
                onClick={() => handleResize(widget.id, 1, 1)}
              />
            ) : null}
            <DashboardWidgetShell
              widget={widget}
              batch={batch?.widgets?.[widget.id]}
              loading={batchLoading}
              onRetry={onRefreshData}
            />
          </div>
        );
      })}
    </div>
  );
}
