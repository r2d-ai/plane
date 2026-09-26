/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import type { TAnalyticsDateGrouping, TAnalyticsDimensionKey } from "@plane/types";
import { capitalizeFirstLetter } from "@plane/utils";
// hooks
import { useCycle } from "@/hooks/store/use-cycle";
import { useLabel } from "@/hooks/store/use-label";
import { useMember } from "@/hooks/store/use-member";
import { useModule } from "@/hooks/store/use-module";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
// local
import { formatDateBucket } from "./cells";

const UUID_LIKE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const STATE_GROUP_LABELS: Record<string, string> = {
  backlog: "Backlog",
  unstarted: "Unstarted",
  started: "Started",
  completed: "Completed",
  cancelled: "Cancelled",
};

const shortId = (value: string) => (value.length > 8 ? `${value.slice(0, 8)}…` : value);

export type TInsightValueResolver = (
  dimension: TAnalyticsDimensionKey | null | undefined,
  raw: string | null | undefined,
  dateGrouping?: TAnalyticsDateGrouping
) => string;

/**
 * Resolves the raw dimension values the engine returns (mostly UUIDs) into the
 * labels a human can read. Unresolvable values degrade to a short identifier
 * rather than leaking a full UUID into the axis.
 */
export function useInsightValueResolver(): TInsightValueResolver {
  const { workspaceSlug } = useParams();
  const { labelMap, fetchedMap, fetchWorkspaceLabels } = useLabel();
  const { getUserDetails } = useMember();
  const { getProjectById } = useProject();
  const { getStateById, workspaceStates } = useProjectState();
  const { getCycleById } = useCycle();
  const { getModuleById } = useModule();

  const slug = workspaceSlug?.toString();
  useEffect(() => {
    if (!slug || fetchedMap[slug]) return;
    fetchWorkspaceLabels(slug).catch(() => undefined);
  }, [fetchWorkspaceLabels, fetchedMap, slug]);

  return useCallback<TInsightValueResolver>(
    (dimension, raw, dateGrouping) => {
      if (raw === null || raw === undefined || raw === "") return "None";
      const value = String(raw);

      switch (dimension) {
        case "labels":
          return labelMap[value]?.name ?? (UUID_LIKE.test(value) ? shortId(value) : value);
        case "assignees":
        case "created_by":
          if (value === "-") return "Unassigned";
          return (
            getUserDetails(value)?.display_name ||
            getUserDetails(value)?.email ||
            (UUID_LIKE.test(value) ? shortId(value) : value)
          );
        case "project":
          return getProjectById(value)?.name ?? (UUID_LIKE.test(value) ? shortId(value) : value);
        case "state":
          return (
            workspaceStates?.find((state) => state.id === value)?.name ??
            getStateById(value)?.name ??
            (UUID_LIKE.test(value) ? shortId(value) : value)
          );
        case "state_group":
          return STATE_GROUP_LABELS[value] ?? capitalizeFirstLetter(value);
        case "priority":
          return capitalizeFirstLetter(value);
        case "cycle":
          return getCycleById(value)?.name ?? (UUID_LIKE.test(value) ? shortId(value) : value);
        case "module":
          return getModuleById(value)?.name ?? (UUID_LIKE.test(value) ? shortId(value) : value);
        case "created_date":
        case "completed_date":
        case "start_date":
        case "due_date":
          return formatDateBucket(value, dateGrouping);
        default:
          return UUID_LIKE.test(value) ? shortId(value) : value;
      }
    },
    [getCycleById, getModuleById, getProjectById, getStateById, getUserDetails, labelMap, workspaceStates]
  );
}
