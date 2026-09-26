/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { LineChart } from "@plane/propel/charts/line-chart";
import { generateExtendedColors } from "@/components/chart/utils";
import type { InsightChartData } from "../cells";

type Props = {
  chartData: InsightChartData;
  baseColors: string[];
  hasBreakdown: boolean;
  canDrilldown: boolean;
  onPointClick: (group: string | null, series: string | null) => void;
};

/** §12.2 — line renderer, one line per series key. */
export function LineRenderer({ chartData, baseColors, hasBreakdown, canDrilldown, onPointClick }: Props) {
  const extended = generateExtendedColors(baseColors, chartData.seriesKeys.length);
  const lines = chartData.seriesKeys.map((key, index) => ({
    key,
    label: chartData.schema[key] ?? key,
    stroke: extended[index] ?? baseColors[0] ?? "#6172E8",
    fill: extended[index] ?? baseColors[0] ?? "#6172E8",
    dashedLine: false,
    showDot: true,
    smoothCurves: false,
  }));
  const dataKey = hasBreakdown ? (chartData.seriesKeys[0] ?? "count") : "count";

  return (
    <LineChart
      className="h-[220px] w-full"
      data={chartData.rows as unknown as Record<string, unknown>[]}
      lines={lines}
      xAxis={{ key: "name", label: "", dy: 20 }}
      yAxis={{ key: dataKey, label: "", offset: -40, dx: -10 }}
      onLineClick={
        canDrilldown
          ? ({ datum, lineKey }) =>
              onPointClick((datum?.__group as string | null) ?? null, hasBreakdown ? lineKey : null)
          : undefined
      }
    />
  );
}
