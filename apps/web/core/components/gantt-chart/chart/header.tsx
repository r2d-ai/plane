/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Expand, Shrink } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TGanttViews } from "@plane/types";
import { Row } from "@plane/ui";
import { cn } from "@plane/utils";
import { VIEWS_LIST } from "@/components/gantt-chart/data";
import { GANTT_COLUMN_DEFINITIONS } from "@/components/gantt-chart/sidebar/timeline-columns";
import type { TGanttColumnKey } from "@/hooks/use-gantt-preferences";
import { useTimeLineChartStore } from "@/hooks/use-timeline-chart";
import { GANTT_BREADCRUMBS_HEIGHT } from "../constants";

type Props = {
  blockIds: string[];
  fullScreenMode: boolean;
  handleChartView: (view: TGanttViews) => void;
  handleToday: () => void;
  loaderTitle: string;
  toggleFullScreenMode: () => void;
  showToday: boolean;
  visibleColumns?: TGanttColumnKey[];
  onToggleColumn?: (column: TGanttColumnKey) => void;
};

export const GanttChartHeader = observer(function GanttChartHeader(props: Props) {
  const { t } = useTranslation();
  const {
    blockIds,
    fullScreenMode,
    handleChartView,
    handleToday,
    loaderTitle,
    toggleFullScreenMode,
    showToday,
    visibleColumns,
    onToggleColumn,
  } = props;
  // chart hook
  const { currentView } = useTimeLineChartStore();

  return (
    <Row
      className="relative flex w-full flex-shrink-0 flex-wrap items-center gap-2 bg-surface-1 py-2 whitespace-nowrap"
      style={{ height: `${GANTT_BREADCRUMBS_HEIGHT}px` }}
    >
      <div className="ml-auto">
        <div className="ml-auto text-11 font-medium text-tertiary">
          {blockIds ? `${blockIds.length} ${loaderTitle}` : t("common.loading")}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {VIEWS_LIST.map((chartView: any) => (
          <button
            key={chartView?.key}
            type="button"
            className={cn(
              "cursor-pointer rounded-md bg-layer-transparent p-1 px-2 text-11 hover:bg-layer-transparent-hover",
              {
                "bg-layer-transparent-selected": currentView === chartView?.key,
              }
            )}
            onClick={() => handleChartView(chartView?.key)}
          >
            {t(chartView?.i18n_title)}
          </button>
        ))}
      </div>

      {showToday && (
        <button
          type="button"
          className="rounded-md bg-layer-transparent p-1 px-2 text-11 hover:bg-layer-transparent-hover"
          onClick={handleToday}
        >
          {t("common.today")}
        </button>
      )}

      {visibleColumns && onToggleColumn && (
        <details className="relative">
          <summary className="cursor-pointer list-none rounded-md bg-layer-transparent p-1 px-2 text-11 hover:bg-layer-transparent-hover">
            {t("gantt.columns_menu")}
          </summary>
          <div className="absolute right-0 z-20 mt-1 min-w-[10rem] rounded-md border border-subtle bg-surface-1 p-1 shadow-raised-200">
            {GANTT_COLUMN_DEFINITIONS.filter((col) => !col.required).map((col) => (
              <label
                key={col.key}
                className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 text-11 hover:bg-layer-transparent-hover"
              >
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(col.key)}
                  onChange={() => onToggleColumn(col.key)}
                />
                {t(col.i18nKey)}
              </label>
            ))}
          </div>
        </details>
      )}

      <button
        type="button"
        className="flex items-center justify-center rounded-md border border-subtle bg-layer-transparent p-1 transition-all hover:bg-layer-transparent-hover"
        onClick={toggleFullScreenMode}
      >
        {fullScreenMode ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
      </button>
    </Row>
  );
});
