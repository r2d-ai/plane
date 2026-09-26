/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Drill-down selection builder (§25).
 *
 * The drill-down endpoint takes the *original* query plus the selected
 * dimension values. The client never rebuilds filter logic — it only reports
 * which cell the user clicked, keyed by the raw group/series values the engine
 * returned (§25: "derived from the exact resolved aggregate query").
 */

import type { TAnalyticsDimensionKey, TAnalyticsDrilldownRequestV2, TAnalyticsQueryV2 } from "@plane/types";

export interface TDrilldownTarget {
  query: TAnalyticsQueryV2;
  primaryKey: TAnalyticsDimensionKey;
  /** Raw primary-dimension value of the clicked cell. */
  groupValue: string | null;
  /** Raw series value of the clicked segment; `null` when there is no breakdown. */
  seriesValue?: string | null;
}

/**
 * Returns the drill-down request body, or `null` when the cell cannot be
 * drilled into — a `null` group means "no value" (unassigned / unlabelled) and
 * the engine deliberately ignores `null` selections, which would otherwise
 * widen the result set back to every work item.
 */
export function buildDrilldownRequest(
  target: TDrilldownTarget,
  options: { page?: number; pageSize?: number; seriesKey?: TAnalyticsDimensionKey | null } = {}
): TAnalyticsDrilldownRequestV2 | null {
  const { query, primaryKey, groupValue, seriesValue } = target;
  if (groupValue === null || groupValue === undefined || groupValue === "") return null;

  const selection: Record<string, string | null> = { [primaryKey]: groupValue };
  const seriesKey = options.seriesKey ?? null;
  if (seriesKey) {
    if (seriesValue === null || seriesValue === undefined || seriesValue === "") return null;
    selection[seriesKey] = seriesValue;
  }

  return {
    query,
    selection: selection as TAnalyticsDrilldownRequestV2["selection"],
    page: options.page ?? 1,
    page_size: options.pageSize ?? 25,
  };
}
