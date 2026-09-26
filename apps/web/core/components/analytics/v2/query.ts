/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Builds the AnalyticsQuery V2 payload for Customized Insights (§11, §18).
 *
 * Pure and dependency-free so it can be unit-tested (§49.6) and reused
 * verbatim by "Save to dashboard" (§18.2) — the persisted widget stores this
 * query configuration, never a snapshot of the results.
 */

import type {
  TAnalyticsAllocation,
  TAnalyticsDateBasis,
  TAnalyticsDateGrouping,
  TAnalyticsDisplay,
  TAnalyticsNormalization,
  TAnalyticsQueryV2,
} from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";

import { isDateDimension, toDimensionKey, toMetricKey, toTimePreset } from "./mapping";

/** §40.1 — the engine refuses `limit > 100`. */
const DATE_DIMENSION_LIMIT = 100;
const CATEGORICAL_DIMENSION_LIMIT = 50;

export interface TInsightQueryInput {
  /** Legacy form selections (§4 baseline vocabulary). */
  xAxis: ChartXAxisProperty;
  yAxis: ChartYAxisMetric;
  groupBy?: ChartXAxisProperty | null;
  /** §9.3 date grouping; only sent when the primary dimension is a date. */
  dateGrouping?: TAnalyticsDateGrouping;
  /** §17.4 */
  display?: TAnalyticsDisplay;
  /** §17 */
  normalization?: TAnalyticsNormalization;
  /** §15 */
  allocation?: TAnalyticsAllocation;
  /** §9 — legacy duration key from the analytics header. */
  duration?: string | null;
  /** §9.1 */
  dateBasis?: TAnalyticsDateBasis;
  /** Workspace Analytics header filters. */
  projectIds?: string[];
  cycleId?: string | null;
  moduleId?: string | null;
}

/**
 * §17 + §17.4: a percentage display is meaningless without a normalisation
 * base, so `Percentage` / `Value + Percentage` forces `grand_total` when the
 * base is `None`. Kept in one place so the form state and the persisted widget
 * query can never disagree.
 */
export function reconcileDisplayNormalization(
  display: TAnalyticsDisplay,
  normalization: TAnalyticsNormalization
): { display: TAnalyticsDisplay; normalization: TAnalyticsNormalization } {
  if (display !== "value" && normalization === "none") {
    return { display, normalization: "grand_total" };
  }
  return { display, normalization };
}

/**
 * Returns the V2 query, or `null` when the selected dimension has no P0
 * equivalent in the engine registry (§12).
 */
export function buildInsightQuery(input: TInsightQueryInput): TAnalyticsQueryV2 | null {
  const primaryKey = toDimensionKey(input.xAxis);
  if (!primaryKey) return null;

  const seriesKey = input.groupBy ? toDimensionKey(input.groupBy) : null;
  if (input.groupBy && !seriesKey) return null;

  const dimensions = [{ key: primaryKey }];
  if (seriesKey) dimensions.push({ key: seriesKey });

  const filters: Record<string, string[]> = {};
  if (input.cycleId) filters.cycle_id = [input.cycleId];
  if (input.moduleId) filters.module_id = [input.moduleId];

  const { display, normalization } = reconcileDisplayNormalization(
    input.display ?? "value",
    input.normalization ?? "none"
  );

  const time: TAnalyticsQueryV2["time"] = {
    preset: toTimePreset(input.duration ?? undefined),
    basis: input.dateBasis ?? "created_at",
  };
  if (isDateDimension(primaryKey)) time.group = input.dateGrouping ?? "day";

  const metricKey = toMetricKey(input.yAxis);

  return {
    version: 1,
    source: "work_items",
    project_ids: (input.projectIds ?? []).filter(Boolean),
    metrics: [{ key: metricKey }],
    dimensions,
    filters,
    time,
    comparison: { type: "none" },
    normalization,
    display,
    allocation: input.allocation ?? "full_credit",
    sort: [{ metric: metricKey, direction: "desc" }],
    limit: isDateDimension(primaryKey) ? DATE_DIMENSION_LIMIT : CATEGORICAL_DIMENSION_LIMIT,
  };
}
