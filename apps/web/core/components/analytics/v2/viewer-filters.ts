/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * §22 — dynamic viewer filters. A card can be scoped to "whoever is looking at
 * it"; the stored query carries the token and the caller substitutes the real
 * id before the query leaves the browser (the engine has no notion of the
 * token).
 */

export const VIEWER_FILTER_TOKENS = new Set(["current_user", "@current_user"]);

/** Replaces viewer tokens in place, preserving every other filter verbatim. */
export function resolveViewerFilterPlaceholders(
  filters: Record<string, unknown> | undefined,
  viewerId: string
): Record<string, unknown> {
  if (!filters) return {};
  const out: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(filters)) {
    if (raw === null || raw === undefined) continue;
    if (Array.isArray(raw)) {
      out[key] = raw.map((token) => (typeof token === "string" && VIEWER_FILTER_TOKENS.has(token) ? viewerId : token));
    } else if (typeof raw === "string" && VIEWER_FILTER_TOKENS.has(raw)) {
      out[key] = viewerId;
    } else {
      out[key] = raw;
    }
  }
  return out;
}
