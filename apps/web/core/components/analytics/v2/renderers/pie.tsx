/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PieChart } from "@plane/propel/charts/pie-chart";
import { generateExtendedColors } from "@/components/chart/utils";
import type { InsightChartData } from "../cells";

export type RadialChartProps = {
  chartData: InsightChartData;
  /** `donut` = 55% inner radius; the plain pie variant uses a filled centre. */
  donut: boolean;
  /** `donut_variant: "progress"` — show the first slice's share in the centre. */
  progress: boolean;
  baseColors: string[];
  canDrilldown: boolean;
  onSliceClick: (group: string | null) => void;
};

/**
 * §12.2 — shared pie/donut renderer. `pie.tsx` and `donut.tsx` are the two
 * card-facing entry points; both configure this one so the two kinds can never
 * drift apart.
 */
export function RadialChartRenderer({
  chartData,
  donut,
  progress,
  baseColors,
  canDrilldown,
  onSliceClick,
}: RadialChartProps) {
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
      onPieClick={canDrilldown ? ({ datum }) => onSliceClick((datum?.__group as string | null) ?? null) : undefined}
    />
  );
}

type Props = Omit<RadialChartProps, "donut" | "progress">;

/** §12.2 — pie renderer (`donut: false`, no centre label). */
export function PieRenderer(props: Props) {
  return <RadialChartRenderer {...props} donut={false} progress={false} />;
}
