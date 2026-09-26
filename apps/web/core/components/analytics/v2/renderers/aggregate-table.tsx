/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsMetricKey } from "@plane/types";
import { formatValue } from "../cells";
import { METRIC_LABELS } from "../mapping";

type Props = {
  totals: Record<string, number>;
};

/** §12.2 — aggregate-table renderer for `statistics` cards (metric → total). */
export function AggregateTableRenderer({ totals }: Props) {
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
