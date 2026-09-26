/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Analytics V2 response warnings (§32.1).
 *
 * Lives in the analytics namespace so generic renderers can read a truncation
 * warning without reaching back into the dashboard builder.
 */

import type { TAnalyticsWarning } from "@plane/types";

export const WARNING_RESULT_TRUNCATED = "RESULT_TRUNCATED";

export function findTruncationWarning(warnings: TAnalyticsWarning[] | undefined): TAnalyticsWarning | undefined {
  return warnings?.find((entry) => entry.code === WARNING_RESULT_TRUNCATED);
}

export function hasTruncatedResult(warnings: TAnalyticsWarning[] | undefined): boolean {
  return !!findTruncationWarning(warnings);
}
