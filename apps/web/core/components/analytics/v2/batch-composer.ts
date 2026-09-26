/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Batch composition for Analytics V2 (spec §32.3, §40.2).
 *
 * `POST /analytics/v2/batch/` takes `{"queries": [{key, ...query}]}` and
 * isolates a failure per entry, so one broken card never blanks the dashboard.
 * This module turns dashboard cards into those entries and folds the response
 * back into the shape card shells consume — pure, so the composition is
 * unit-testable without a network round-trip.
 *
 * The per-request entry cap stays backend-owned (`MAX_BATCH_QUERIES` in
 * `plane/analytics/v2/query.py`), so the client sends every card it was given
 * and lets the engine answer the way it does today.
 */

import type {
  TDashboardBatchDataResponse,
  TDashboardBatchWidgetResult,
  TWorkspaceDashboard,
  TWorkspaceDashboardWidget,
} from "@plane/types";

import { resolveViewerFilterPlaceholders } from "./viewer-filters";

export type TAnalyticsBatchQuery = Record<string, unknown> & { key: string };

export type TAnalyticsBatchResultEntry = {
  key: string;
  status: "ok" | "error";
  data?: unknown;
  error?: { code: string; message: string };
};

export type TAnalyticsBatchRequest = { queries: TAnalyticsBatchQuery[] };

export type TAnalyticsBatchResponse = { workspace_slug?: string; results?: TAnalyticsBatchResultEntry[] };

const INVALID_QUERY_ERROR = { code: "INVALID_QUERY", message: "Invalid query" } as const;

/** §26 — key-wise intersection of two structured filter bags. */
export function intersectStructuredFilters(
  left: Record<string, unknown> | undefined,
  right: Record<string, unknown> | undefined
): Record<string, unknown> {
  if (!left) return { ...right };
  if (!right) return { ...left };

  const out: Record<string, unknown> = {};
  for (const key of new Set([...Object.keys(left), ...Object.keys(right)])) {
    const lv = left[key];
    const rv = right[key];
    if (lv === null || lv === undefined) {
      out[key] = rv;
      continue;
    }
    if (rv === null || rv === undefined) {
      out[key] = lv;
      continue;
    }
    const leftValues = Array.isArray(lv) ? lv : [lv];
    const rightValues = Array.isArray(rv) ? rv : [rv];
    const intersection = leftValues.filter((value) => rightValues.includes(value));
    if (intersection.length > 0) out[key] = intersection;
  }
  return out;
}

/** Text/markdown cards carry no query — they never enter the batch. */
function isStaticWidget(widget: TWorkspaceDashboardWidget): boolean {
  return widget.widget_type === "text" || widget.widget_type === "markdown";
}

/** The query body a card persists: `query_config.query` or the flat V2 body. */
function widgetQueryBody(widget: TWorkspaceDashboardWidget): Record<string, unknown> | null {
  const config = widget.query_config;
  if (!config || typeof config !== "object") return null;
  const body = config as Record<string, unknown>;
  if (body.query && typeof body.query === "object") return { ...(body.query as Record<string, unknown>) };
  const { schema_version: _schemaVersion, ...rest } = body;
  if (typeof rest.version !== "number") return null;
  return rest;
}

/**
 * One batch entry for `widget`: the persisted query, scoped to the dashboard's
 * projects and filters, with the dashboard time scope applied. `null` when the
 * card has no readable query — the caller turns that into an error entry so the
 * card shows its own failure state instead of the whole batch failing.
 */
export function buildWidgetBatchQuery(
  dashboard: TWorkspaceDashboard,
  widget: TWorkspaceDashboardWidget,
  viewerId?: string
): TAnalyticsBatchQuery | null {
  const body = widgetQueryBody(widget);
  if (!body || isStaticWidget(widget)) return null;

  const query: Record<string, unknown> = { ...body, key: widget.id };

  // The engine intersects these with the viewer's visible projects (§37), so
  // the client only has to state the dashboard's configured scope.
  query.project_ids = dashboard.projects ?? [];

  const configFilters = (widget.query_config as Record<string, unknown> | undefined)?.filters as
    | Record<string, unknown>
    | undefined;
  const filters = intersectStructuredFilters(
    intersectStructuredFilters(query.filters as Record<string, unknown> | undefined, configFilters),
    dashboard.filters
  );
  // No viewer id means the card keeps its `current_user` tokens unresolved, so
  // it renders empty rather than silently widening its own scope.
  query.filters = viewerId ? resolveViewerFilterPlaceholders(filters, viewerId) : filters;

  if (widget.inherit_time_scope) {
    if (dashboard.default_time_scope) query.time = { ...dashboard.default_time_scope };
  } else if (widget.custom_time_scope) {
    query.time = { ...widget.custom_time_scope };
  } else if (dashboard.default_time_scope && query.time === undefined) {
    query.time = { ...dashboard.default_time_scope };
  }

  if (dashboard.comparison && query.comparison === undefined) {
    query.comparison = { ...dashboard.comparison };
  }

  return query as TAnalyticsBatchQuery;
}

/** Every non-static card as one batch request. */
export function buildWidgetBatchRequest(
  dashboard: TWorkspaceDashboard,
  widgets: TWorkspaceDashboardWidget[],
  viewerId?: string
): TAnalyticsBatchRequest {
  const queries: TAnalyticsBatchQuery[] = [];
  for (const widget of widgets) {
    const query = buildWidgetBatchQuery(dashboard, widget, viewerId);
    if (query) queries.push(query);
  }
  return { queries };
}

/**
 * Fold the per-entry results back into the card-keyed shape the grid renders.
 * Cards the engine never answered (no query, dropped by the cap) get the same
 * error entry the old dashboard-scoped endpoint returned for them.
 */
export function normalizeWidgetBatchResults(
  dashboard: TWorkspaceDashboard,
  widgets: TWorkspaceDashboardWidget[],
  results: TAnalyticsBatchResultEntry[] | undefined
): TDashboardBatchDataResponse {
  const out: Record<string, TDashboardBatchWidgetResult> = {};

  for (const entry of results ?? []) {
    if (!entry || typeof entry.key !== "string") continue;
    if (entry.status === "ok") {
      out[entry.key] = { status: "ok", data: entry.data };
    } else {
      out[entry.key] = { status: "error", error: entry.error ?? INVALID_QUERY_ERROR };
    }
  }

  for (const widget of widgets) {
    if (out[widget.id]) continue;
    out[widget.id] = { status: "error", error: { ...INVALID_QUERY_ERROR } };
  }

  return {
    dashboard_id: dashboard.id,
    resolved_time: dashboard.default_time_scope ?? {},
    widgets: out,
  };
}
