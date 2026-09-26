/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { BarChart } from "@plane/propel/charts/bar-chart";
import { generateExtendedColors } from "@/components/chart/utils";
import type { InsightChartData } from "../cells";

type Props = {
  chartData: InsightChartData;
  barMode: string;
  baseColors: string[];
  onBarClick: (group: string | null, series: string | null) => void;
  canDrilldown: boolean;
};

/** §12.2 — bar renderer; `barMode` is `basic` / `stacked` / `grouped`. */
export function BarRenderer({ chartData, barMode, baseColors, onBarClick, canDrilldown }: Props) {
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
