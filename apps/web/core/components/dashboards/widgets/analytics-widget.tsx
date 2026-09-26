/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import { Download } from "lucide-react";
import { CHART_COLOR_PALETTES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import type {
  TAnalyticsDrilldownRequestV2,
  TAnalyticsMetricKey,
  TAnalyticsQueryResponseV2,
  TDashboardWidgetType,
  TWorkspaceDashboardWidget,
} from "@plane/types";
import { buildInsightChartData } from "@/components/analytics/v2/cells";
import { buildDrilldownRequest } from "@/components/analytics/v2/drilldown";
import InsightDrilldownDrawer from "@/components/analytics/v2/insight-drilldown";
import { isDateDimension, METRIC_LABELS, metricUnit } from "@/components/analytics/v2/mapping";
import {
  AggregateTableRenderer,
  BarRenderer,
  DonutRenderer,
  GaugeRenderer,
  LineRenderer,
  MatrixRenderer,
  NumberRenderer,
  PieRenderer,
  WidgetTruncationBanner,
  WorkItemTableRenderer,
} from "@/components/analytics/v2/renderers";
import { useInsightValueResolver } from "@/components/analytics/v2/use-insight-value-resolver";
import { WidgetDrilldownDrawer } from "@/components/analytics/v2/renderers/widget-drilldown-drawer";
import {
  aggregateCellsToCsvRows,
  buildMatrixTableModel,
  downloadCsv,
  matrixToCsvRows,
  parseWidgetQuery,
} from "./analytics-data";

type Props = {
  widget: TWorkspaceDashboardWidget;
  response: TAnalyticsQueryResponseV2;
  workspaceSlug: string;
  dashboardId: string;
};

const CHART_TYPES = new Set<TDashboardWidgetType>(["bar", "line", "pie", "donut"]);

export function DashboardAnalyticsWidget({ widget, response, workspaceSlug, dashboardId }: Props) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const resolve = useInsightValueResolver();
  const query = useMemo(() => parseWidgetQuery(widget) ?? response.query, [response.query, widget]);

  const [dashboardDrilldown, setDashboardDrilldown] = useState<Record<string, string | string[] | null> | null>(null);
  const [insightDrilldown, setInsightDrilldown] = useState<TAnalyticsDrilldownRequestV2 | null>(null);

  const display = query.display ?? "value";
  const metricKey: TAnalyticsMetricKey = query.metrics?.[0]?.key ?? "work_item_count";
  const metricLabel = METRIC_LABELS[metricKey] ?? metricKey;
  const unit = metricUnit(metricKey);
  const primaryDim = query.dimensions?.[0]?.key ?? null;
  const seriesDim = query.dimensions?.[1]?.key ?? null;
  const hasBreakdown = !!seriesDim;
  const dateDimension = isDateDimension(primaryDim);
  const canDrilldown = !!primaryDim && !dateDimension;
  const barMode = (widget.style_config?.bar_mode as string | undefined) ?? (hasBreakdown ? "stacked" : "basic");

  const baseColors = useMemo(
    () => CHART_COLOR_PALETTES[0]?.[resolvedTheme === "dark" ? "dark" : "light"] ?? [],
    [resolvedTheme]
  );

  const chartData = useMemo(() => {
    if (!CHART_TYPES.has(widget.widget_type) && widget.widget_type !== "matrix" && widget.widget_type !== "table") {
      return null;
    }
    return buildInsightChartData({
      cells: response.data ?? [],
      metricLabel,
      hasBreakdown,
      display,
      unit,
      dateGrouping: dateDimension ? (query.time?.group ?? "day") : undefined,
      resolveGroup: (raw) => resolve(primaryDim, raw, query.time?.group),
      resolveSeries: (raw) => resolve(seriesDim, raw),
    });
  }, [
    dateDimension,
    display,
    hasBreakdown,
    metricLabel,
    primaryDim,
    query.time?.group,
    resolve,
    response.data,
    seriesDim,
    unit,
    widget.widget_type,
  ]);

  const matrixModel = useMemo(() => {
    if (widget.widget_type !== "matrix") return null;
    return buildMatrixTableModel(response.data ?? [], display, unit);
  }, [display, response.data, unit, widget.widget_type]);

  const openDrilldown = useCallback(
    (groupValue: string | null, seriesValue: string | null) => {
      if (!primaryDim || !canDrilldown) return;
      const request = buildDrilldownRequest(
        { query, primaryKey: primaryDim, groupValue, seriesValue: hasBreakdown ? seriesValue : null },
        { seriesKey: hasBreakdown ? seriesDim : null }
      );
      if (request) {
        setInsightDrilldown(request);
        return;
      }
      const selection: Record<string, string | string[] | null> = { [primaryDim]: groupValue };
      if (hasBreakdown && seriesDim && seriesValue) selection[seriesDim] = seriesValue;
      setDashboardDrilldown(selection);
    },
    [canDrilldown, hasBreakdown, primaryDim, query, seriesDim]
  );

  const exportWidgetCsv = useCallback(() => {
    const safeTitle = (widget.title || "widget").replace(/[^\w.-]+/g, "_");
    if (widget.widget_type === "matrix" && matrixModel) {
      const colLabels: Record<string, string> = {};
      for (const key of matrixModel.colKeys) colLabels[key] = resolve(seriesDim, key || null);
      let body = matrixToCsvRows(matrixModel, colLabels);
      const truncated = response.warnings?.find((w) => w.code === "RESULT_TRUNCATED");
      if (truncated) body += `# ${truncated.message}\n`;
      downloadCsv(`${safeTitle}.csv`, body);
      return;
    }
    const body = aggregateCellsToCsvRows(response, { includeTruncationNote: true });
    downloadCsv(`${safeTitle}.csv`, body);
  }, [matrixModel, resolve, response, seriesDim, widget.title, widget.widget_type]);

  const isEmpty = (response.data?.length ?? 0) === 0 && Object.keys(response.totals ?? {}).length === 0;

  if (isEmpty) {
    return (
      <div className="flex h-full flex-col gap-2 p-3">
        <WidgetHeader title={widget.title} onExport={exportWidgetCsv} />
        <WidgetTruncationBanner warnings={response.warnings} />
        <EmptyStateCompact
          assetKey="unknown"
          title={t("dashboard_shell.widget.no_data")}
          rootClassName="flex-1 border-0 py-6"
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 p-3">
      <WidgetHeader title={widget.title} onExport={exportWidgetCsv} />
      <WidgetTruncationBanner warnings={response.warnings} />
      <div className="min-h-0 flex-1 overflow-auto">{renderBody()}</div>
      {dashboardDrilldown ? (
        <WidgetDrilldownDrawer
          workspaceSlug={workspaceSlug}
          dashboardId={dashboardId}
          widgetId={widget.id}
          selection={dashboardDrilldown}
          metricKey={metricKey}
          onClose={() => setDashboardDrilldown(null)}
        />
      ) : null}
      {insightDrilldown ? (
        <InsightDrilldownDrawer
          workspaceSlug={workspaceSlug}
          request={insightDrilldown}
          onClose={() => setInsightDrilldown(null)}
        />
      ) : null}
    </div>
  );

  function renderBody() {
    switch (widget.widget_type) {
      case "number":
      case "counter":
        return <NumberRenderer value={response.totals?.[metricKey] ?? response.data?.[0]?.value ?? 0} unit={unit} />;
      case "statistics":
        return <AggregateTableRenderer totals={response.totals ?? {}} />;
      case "gauge":
        return <GaugeRenderer response={response} metricKey={metricKey} style={widget.style_config} unit={unit} />;
      case "bar":
        return chartData ? (
          <BarRenderer
            chartData={chartData}
            barMode={barMode}
            baseColors={baseColors}
            onBarClick={(group, series) => openDrilldown(group, series)}
            canDrilldown={canDrilldown}
          />
        ) : null;
      case "line":
        return chartData ? (
          <LineRenderer
            chartData={chartData}
            baseColors={baseColors}
            hasBreakdown={hasBreakdown}
            canDrilldown={canDrilldown}
            onPointClick={(group, series) => openDrilldown(group, series)}
          />
        ) : null;
      case "pie":
        return chartData ? (
          <PieRenderer
            chartData={chartData}
            baseColors={baseColors}
            canDrilldown={canDrilldown}
            onSliceClick={(group) => openDrilldown(group, null)}
          />
        ) : null;
      case "donut":
        return chartData ? (
          <DonutRenderer
            chartData={chartData}
            progress={widget.style_config?.donut_variant === "progress"}
            baseColors={baseColors}
            canDrilldown={canDrilldown}
            onSliceClick={(group) => openDrilldown(group, null)}
          />
        ) : null;
      case "matrix":
        return matrixModel ? (
          <MatrixRenderer
            model={matrixModel}
            resolveRow={(key) => resolve(primaryDim, key || null)}
            resolveCol={(key) => resolve(seriesDim, key || null)}
            onCellClick={(row, col) => openDrilldown(row || null, col || null)}
            canDrilldown={canDrilldown && !!seriesDim}
          />
        ) : null;
      case "table":
        return (
          <WorkItemTableRenderer
            workspaceSlug={workspaceSlug}
            dashboardId={dashboardId}
            widgetId={widget.id}
            chartData={chartData}
            canDrilldown={canDrilldown}
            onDrilldown={openDrilldown}
          />
        );
      default:
        return <p className="text-12 text-tertiary">{t("dashboard_shell.widget.unsupported_type")}</p>;
    }
  }
}

function WidgetHeader({ title, onExport }: { title: string; onExport: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-13 font-medium text-primary">{title}</h3>
      <Button variant="secondary" size="sm" prependIcon={<Download className="h-3.5 w-3.5" />} onClick={onExport}>
        {t("exporter.csv.short_description")}
      </Button>
    </div>
  );
}
