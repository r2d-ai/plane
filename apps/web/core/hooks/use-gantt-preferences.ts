/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useState } from "react";
import type { TGanttViews } from "@plane/types";

export type TGanttColumnKey =
  | "work_item"
  | "status"
  | "assignee"
  | "duration"
  | "priority"
  | "module"
  | "labels"
  | "start_date"
  | "target_date"
  | "estimate";

export type TGanttPreferences = {
  scale: TGanttViews;
  sidebarWidth: number;
  visibleColumns: TGanttColumnKey[];
};

export const DEFAULT_GANTT_VISIBLE_COLUMNS: TGanttColumnKey[] = ["work_item", "status", "assignee", "duration"];

export const GANTT_SIDEBAR_MIN_WIDTH = 320;
export const GANTT_SIDEBAR_MAX_WIDTH = 720;
export const GANTT_SIDEBAR_DEFAULT_WIDTH = 460;

const DEFAULT_PREFERENCES: TGanttPreferences = {
  scale: "week",
  sidebarWidth: GANTT_SIDEBAR_DEFAULT_WIDTH,
  visibleColumns: DEFAULT_GANTT_VISIBLE_COLUMNS,
};

const getStorageKey = (workspaceSlug: string, entityId: string) => `plane-gantt-prefs-${workspaceSlug}-${entityId}`;

export const useGanttPreferences = (workspaceSlug: string | undefined, entityId: string | undefined) => {
  const [preferences, setPreferences] = useState<TGanttPreferences>(DEFAULT_PREFERENCES);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!workspaceSlug || !entityId) return;
    try {
      const stored = localStorage.getItem(getStorageKey(workspaceSlug, entityId));
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<TGanttPreferences>;
        setPreferences({
          ...DEFAULT_PREFERENCES,
          ...parsed,
          visibleColumns: parsed.visibleColumns ?? DEFAULT_GANTT_VISIBLE_COLUMNS,
        });
      }
    } catch {
      // ignore corrupt storage
    }
    setIsLoaded(true);
  }, [workspaceSlug, entityId]);

  const updatePreferences = useCallback(
    (updates: Partial<TGanttPreferences>) => {
      setPreferences((prev) => {
        const next = { ...prev, ...updates };
        if (workspaceSlug && entityId) {
          try {
            localStorage.setItem(getStorageKey(workspaceSlug, entityId), JSON.stringify(next));
          } catch {
            // storage may be unavailable
          }
        }
        return next;
      });
    },
    [workspaceSlug, entityId]
  );

  return { preferences, updatePreferences, isLoaded };
};
