/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CollabStage } from "@/types/collaboration";

/**
 * Collaboration connection resilience (pure decision helpers).
 *
 * The Yjs connection has two failure modes this module addresses:
 *
 * 1. A terminal `disconnected` stage is never retried by the provider hook
 *    outside of tab focus/visibility/online events, so a single transient
 *    network or auth hiccup leaves the "Connection lost" badge stuck until the
 *    user switches tabs. The watchdog below re-establishes the connection
 *    without user interaction.
 * 2. The provider's liveness check (`messageReconnectTimeout`, 30s) only
 *    counts incoming data messages, while the server keepalive is a
 *    WebSocket-level ping — an idle document is torn down and reconnected (and
 *    re-authenticated against the API) every 30 seconds. A periodic
 *    `forceSyncInterval` sync keeps real traffic flowing so idle documents
 *    stay connected and only genuinely dead sockets are recycled.
 */

// Server-side document force closes (admin command, oversized document,
// memory pressure, security violation): reconnecting would immediately hit the
// same wall, so these stay terminal until the user reloads.
const FORCE_CLOSE_MIN_CODE = 4000;
const FORCE_CLOSE_MAX_CODE = 4003;

/** A connecting/reconnecting/awaiting-sync stage stuck this long is wedged. */
export const STUCK_STAGE_MS = 30_000;

/** Watchdog poll interval for healing the connection. */
export const WATCHDOG_POLL_MS = 5_000;

/** Yjs sync cadence that keeps the liveness checker fed on idle documents. */
export const KEEPALIVE_SYNC_INTERVAL_MS = 25_000;

export const isForcedCloseCode = (code: number | undefined): boolean => {
  if (!code) return false;
  return code >= FORCE_CLOSE_MIN_CODE && code <= FORCE_CLOSE_MAX_CODE;
};

export type TConnectionWatchdogInput = {
  isDisposed: boolean;
  stageKind: CollabStage["kind"];
  isDocumentForceClosed: boolean;
  msSinceStageChange: number;
};

/**
 * Whether the watchdog should recycle the WebSocket right now. Healing is a
 * plain disconnect + connect: safe for transient failures, skipped while the
 * connection is healthy or the document itself was force closed server-side.
 */
export const shouldAttemptHeal = ({
  isDisposed,
  stageKind,
  isDocumentForceClosed,
  msSinceStageChange,
}: TConnectionWatchdogInput): boolean => {
  if (isDisposed || isDocumentForceClosed) return false;
  if (stageKind === "disconnected") return true;
  if (stageKind === "connecting" || stageKind === "reconnecting" || stageKind === "awaiting-sync") {
    return msSinceStageChange >= STUCK_STAGE_MS;
  }
  // initial and synced are healthy/transient states
  return false;
};
