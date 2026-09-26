/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsMetricKey, TAnalyticsQueryResponseV2 } from "@plane/types";
import { formatValue } from "../cells";

type Props = {
  response: TAnalyticsQueryResponseV2;
  metricKey: TAnalyticsMetricKey;
  style?: Record<string, unknown>;
  unit: string;
};

/** §12.2 — numerator/denominator progress gauge. */
export function GaugeRenderer({ response, metricKey, style, unit }: Props) {
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
