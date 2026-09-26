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
import { BarChart } from "@plane/propel/charts/bar-chart";
import { LineChart } from "@plane/propel/charts/line-chart";
import { PieChart } from "@plane/propel/charts/pie-chart";
import { Button } from "@plane/propel/button";
import { EmptyStateCompact } from "@plane/propel/empty-state";
import type {
  TAnalyticsDrilldownRequestV2,
  TAnalyticsMetricKey,
  TAnalyticsQueryResponseV2,
  TDashboardWidgetType,
  TWorkspaceDashboardWidget,
} from "@plane/types";
import { generateExtendedColors } from "@/components/chart/utils";
import { buildInsightChartData, formatValue, type InsightChartRow } from "@/components/analytics/v2/cells";
import { buildDrilldownRequest } from "@/components/analytics/v2/drilldown";
import { isDateDimension, METRIC_LABELS, metricUnit } from "@/components/analytics/v2/mapping";
import { useInsightValueResolver } from "@/components/analytics/v2/use-insight-value-resolver";
import InsightDrilldownDrawer from "@/components/analytics/v2/insight-drilldown";
import {
  aggregateCellsToCsvRows,
  buildMatrixTableModel,
  downloadCsv,
  matrixToCsvRows,
  parseWidgetQuery,
} from "./analytics-data";
import { WidgetTruncationBanner } from "./truncation-banner";
import { WidgetDrilldownDrawer } from "./widget-drilldown-drawer";

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
        return <ScalarValue value={response.totals?.[metricKey] ?? response.data?.[0]?.value ?? 0} unit={unit} />;
      case "statistics":
        return <StatisticsGrid totals={response.totals ?? {}} />;
      case "gauge":
        return <GaugeView response={response} metricKey={metricKey} style={widget.style_config} unit={unit} />;
      case "bar":
        return chartData ? (
          <BarChartView
            chartData={chartData}
            barMode={barMode}
            baseColors={baseColors}
            onBarClick={(group, series) => openDrilldown(group, series)}
            canDrilldown={canDrilldown}
          />
        ) : null;
      case "line":
        return chartData ? (
          <LineChartView chartData={chartData} baseColors={baseColors} hasBreakdown={hasBreakdown} />
        ) : null;
      case "pie":
      case "donut":
        return chartData ? (
          <PieChartView
            chartData={chartData}
            donut={widget.widget_type === "donut"}
            progress={widget.style_config?.donut_variant === "progress"}
            baseColors={baseColors}
          />
        ) : null;
      case "matrix":
        return matrixModel ? (
          <MatrixTable
            model={matrixModel}
            resolveRow={(key) => resolve(primaryDim, key || null)}
            resolveCol={(key) => resolve(seriesDim, key || null)}
            onCellClick={(row, col) => openDrilldown(row || null, col || null)}
            canDrilldown={canDrilldown && !!seriesDim}
          />
        ) : null;
      case "table":
        return (
          <WorkItemsTablePreview
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

function ScalarValue({ value, unit }: { value: number; unit: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <span className="text-32 font-semibold text-primary">{formatValue(value, unit)}</span>
    </div>
  );
}

function StatisticsGrid({ totals }: { totals: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {Object.entries(totals).map(([key, value]) => (
        <div key={key} className="rounded-md border border-subtle px-3 py-2">
          <div className="text-11 text-tertiary">{METRIC_LABELS[key as TAnalyticsMetricKey] ?? key}</div>
          <div className="text-16 font-medium text-primary">{formatValue(value)}</div>
        </div>
      ))}
    </div>
  );
}

function GaugeView({
  response,
  metricKey,
  style,
  unit,
}: {
  response: TAnalyticsQueryResponseV2;
  metricKey: TAnalyticsMetricKey;
  style?: Record<string, unknown>;
  unit: string;
}) {
  const numeratorKey = (style?.numerator_metric as TAnalyticsMetricKey | undefined) ?? "completed_work_items";
  const denominatorKey = (style?.denominator_metric as TAnalyticsMetricKey | undefined) ?? metricKey;
  const numerator = response.totals?.[numeratorKey] ?? 0;
  const denominator = response.totals?.[denominatorKey] ?? response.totals?.[metricKey] ?? 0;
  const pct = denominator > 0 ? Math.min(100, (numerator / denominator) * 100) : 0;

  return (
    <div className="flex flex-col items-center justify-center gap-2 py-4">
      <div className="text-28 font-semibold text-primary">{pct.toFixed(1)}%</div>
      <div className="text-12 text-tertiary">
        {formatValue(numerator, unit)} / {formatValue(denominator, unit)}
      </div>
      <div className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-layer-2">
        <div className="bg-custom-primary-100 h-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function BarChartView({
  chartData,
  barMode,
  baseColors,
  onBarClick,
  canDrilldown,
}: {
  chartData: ReturnType<typeof buildInsightChartData>;
  barMode: string;
  baseColors: string[];
  onBarClick: (group: string | null, series: string | null) => void;
  canDrilldown: boolean;
}) {
  const extended = generateExtendedColors(baseColors, chartData.seriesKeys.length);
  const bars = chartData.seriesKeys.map((key, index) => ({
    key,
    label: chartData.schema[key] ?? key,
    stackId: barMode === "grouped" ? key : "stack",
    fill: extended[index] ?? baseColors[0] ?? "#6172E8",
    textClassName: "",
    showPercentage: false,
    showTopBorderRadius: () => true,
    showBottomBorderRadius: () => true,
  }));

  return (
    <BarChart
      className="h-[220px] w-full"
      data={chartData.rows as unknown as Record<string, unknown>[]}
      bars={bars}
      xAxis={{ key: "name", label: "", dy: 20 }}
      yAxis={{ key: "count", label: "", offset: -40, dx: -10 }}
      onBarClick={
        canDrilldown ? ({ datum, barKey }) => onBarClick((datum?.__group as string | null) ?? null, barKey) : undefined
      }
    />
  );
}

function LineChartView({
  chartData,
  baseColors,
  hasBreakdown,
}: {
  chartData: ReturnType<typeof buildInsightChartData>;
  baseColors: string[];
  hasBreakdown: boolean;
}) {
  const extended = generateExtendedColors(baseColors, chartData.seriesKeys.length);
  const lines = chartData.seriesKeys.map((key, index) => ({
    key,
    label: chartData.schema[key] ?? key,
    stroke: extended[index] ?? baseColors[0] ?? "#6172E8",
    dot: true,
  }));
  const dataKey = hasBreakdown ? (chartData.seriesKeys[0] ?? "count") : "count";

  return (
    <LineChart
      className="h-[220px] w-full"
      data={chartData.rows as unknown as Record<string, unknown>[]}
      lines={lines}
      xAxis={{ key: "name", label: "", dy: 20 }}
      yAxis={{ key: dataKey, label: "", offset: -40, dx: -10 }}
    />
  );
}

function PieChartView({
  chartData,
  donut,
  progress,
  baseColors,
}: {
  chartData: ReturnType<typeof buildInsightChartData>;
  donut: boolean;
  progress: boolean;
  baseColors: string[];
}) {
  const extended = generateExtendedColors(baseColors, chartData.rows.length);
  const pieData = chartData.rows.map((row, index) => ({
    name: row.name,
    value: row.count,
    __group: row.__group,
    fill: extended[index] ?? baseColors[0],
  }));
  const total = pieData.reduce((sum, row) => sum + (row.value as number), 0);
  const progressPct = progress && total > 0 ? ((pieData[0]?.value as number) / total) * 100 : undefined;

  return (
    <PieChart
      className="h-[220px] w-full"
      data={pieData}
      dataKey="value"
      innerRadius={donut ? "55%" : 0}
      outerRadius="80%"
      showLabel={false}
      cells={pieData.map((row) => ({
        key: String(row.name),
        fill: row.fill as string,
      }))}
      centerLabel={
        progressPct !== undefined
          ? { text: `${progressPct.toFixed(0)}%`, fill: "var(--text-color-primary)" }
          : undefined
      }
    />
  );
}

function MatrixTable({
  model,
  resolveRow,
  resolveCol,
  onCellClick,
  canDrilldown,
}: {
  model: ReturnType<typeof buildMatrixTableModel>;
  resolveRow: (key: string) => string;
  resolveCol: (key: string) => string;
  onCellClick: (row: string, col: string) => void;
  canDrilldown: boolean;
}) {
  return (
    <table className="w-full border-collapse text-12">
      <thead>
        <tr className="border-b border-subtle text-tertiary">
          <th className="px-2 py-1 text-left" />
          {model.colKeys.map((col) => (
            <th key={col} className="px-2 py-1 text-right">
              {resolveCol(col)}
            </th>
          ))}
          <th className="px-2 py-1 text-right font-medium">Total</th>
        </tr>
      </thead>
      <tbody>
        {model.rowKeys.map((row) => (
          <tr key={row} className="border-b border-subtle">
            <td className="px-2 py-1 text-left font-medium">{resolveRow(row)}</td>
            {model.colKeys.map((col) => {
              const cell = model.cells[row]?.[col];
              return (
                <td key={col} className="px-2 py-1 text-right">
                  {canDrilldown ? (
                    <button
                      type="button"
                      className="w-full rounded-sm hover:bg-layer-1"
                      onClick={() => onCellClick(row, col)}
                    >
                      {cell?.display ?? "—"}
                    </button>
                  ) : (
                    (cell?.display ?? "—")
                  )}
                </td>
              );
            })}
            <td className="px-2 py-1 text-right font-medium">{formatValue(model.rowTotals[row] ?? 0)}</td>
          </tr>
        ))}
        <tr className="font-medium">
          <td className="px-2 py-1 text-left">Total</td>
          {model.colKeys.map((col) => (
            <td key={col} className="px-2 py-1 text-right">
              {formatValue(model.colTotals[col] ?? 0)}
            </td>
          ))}
          <td className="px-2 py-1 text-right">{formatValue(model.grandTotal)}</td>
        </tr>
      </tbody>
    </table>
  );
}

function WorkItemsTablePreview({
  workspaceSlug,
  dashboardId,
  widgetId,
  chartData,
  canDrilldown,
  onDrilldown,
}: {
  workspaceSlug: string;
  dashboardId: string;
  widgetId: string;
  chartData: ReturnType<typeof buildInsightChartData> | null;
  canDrilldown: boolean;
  onDrilldown: (group: string | null, series: string | null) => void;
}) {
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
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        View work items
      </Button>
      {open ? (
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
