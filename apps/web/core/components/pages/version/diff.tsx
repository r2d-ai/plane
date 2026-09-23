/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { Loader, Avatar } from "@plane/ui";
import type { TPageVersion } from "@plane/types";
import { renderFormattedDate, renderFormattedTime, getFileURL } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
// local imports
import { computeHtmlDiff, type TDiffSegment } from "./diff-utils";

type Props = {
  baseVersionId: string;
  compareVersionId: string;
  fetchVersionDetails: (pageId: string, versionId: string) => Promise<TPageVersion | undefined>;
  pageId: string;
};

function DiffSegmentView({ segment }: { segment: TDiffSegment }) {
  switch (segment.type) {
    case "equal":
      return <span className="text-secondary">{segment.oldText} </span>;
    case "added":
      return (
        <span className="rounded-sm bg-green-500/10 text-green-500 dark:bg-green-400/10 dark:text-green-400">
          {segment.newText}{" "}
        </span>
      );
    case "removed":
      return (
        <span className="rounded-sm bg-red-500/10 text-red-500 line-through dark:bg-red-400/10 dark:text-red-400">
          {segment.oldText}{" "}
        </span>
      );
    case "changed":
      return (
        <span>
          <span className="rounded-sm bg-red-500/10 text-red-500 line-through dark:bg-red-400/10 dark:text-red-400">
            {segment.oldText}{" "}
          </span>
          <span className="rounded-sm bg-green-500/10 text-green-500 dark:bg-green-400/10 dark:text-green-400">
            {segment.newText}{" "}
          </span>
        </span>
      );
    default:
      return null;
  }
}

export const PageVersionDiff = observer(function PageVersionDiff(props: Props) {
  const { baseVersionId, compareVersionId, fetchVersionDetails, pageId } = props;
  const { getUserDetails } = useMember();

  const { data: baseVersion, isLoading: isLoadingBase } = useSWR(
    pageId && baseVersionId ? `PAGE_VERSION_DIFF_BASE_${baseVersionId}` : null,
    pageId && baseVersionId ? () => fetchVersionDetails(pageId, baseVersionId) : null
  );

  const { data: compareVersion, isLoading: isLoadingCompare } = useSWR(
    pageId && compareVersionId ? `PAGE_VERSION_DIFF_COMPARE_${compareVersionId}` : null,
    pageId && compareVersionId ? () => fetchVersionDetails(pageId, compareVersionId) : null
  );

  const isLoading = isLoadingBase || isLoadingCompare;

  const diffSegments = useMemo(() => {
    if (!baseVersion?.description_html || !compareVersion?.description_html) return [];
    return computeHtmlDiff(baseVersion.description_html, compareVersion.description_html);
  }, [baseVersion?.description_html, compareVersion?.description_html]);

  const baseCreator = baseVersion?.owned_by ? getUserDetails(baseVersion.owned_by) : null;
  const compareCreator = compareVersion?.owned_by ? getUserDetails(compareVersion.owned_by) : null;

  const addedCount = diffSegments.filter((s) => s.type === "added").length;
  const removedCount = diffSegments.filter((s) => s.type === "removed").length;
  const changedCount = diffSegments.filter((s) => s.type === "changed").length;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4 p-5">
        <Loader className="space-y-4">
          <Loader.Item width="40%" height="24px" />
          <Loader.Item width="100%" height="16px" />
          <Loader.Item width="80%" height="16px" />
          <Loader.Item width="60%" height="16px" />
        </Loader>
      </div>
    );
  }

  if (!baseVersion || !compareVersion) {
    return (
      <div className="flex items-center justify-center p-8 text-13 text-tertiary">
        Unable to load version details for comparison.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Diff header */}
      <div className="flex min-h-14 items-center justify-between gap-4 border-b border-subtle px-5 py-3">
        <div className="flex items-center gap-3">
          <h6 className="text-14 font-medium">Version Comparison</h6>
          <div className="flex items-center gap-2 text-11 text-tertiary">
            {addedCount > 0 && (
              <span className="rounded-sm bg-green-500/10 px-1.5 py-0.5 text-green-600 dark:text-green-400">
                +{addedCount} added
              </span>
            )}
            {removedCount > 0 && (
              <span className="rounded-sm bg-red-500/10 px-1.5 py-0.5 text-red-600 dark:text-red-400">
                -{removedCount} removed
              </span>
            )}
            {changedCount > 0 && (
              <span className="rounded-sm bg-yellow-500/10 px-1.5 py-0.5 text-yellow-600 dark:text-yellow-400">
                ~{changedCount} changed
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Version info */}
      <div className="grid grid-cols-2 gap-4 border-b border-subtle px-5 py-3">
        <div className="flex items-center gap-2">
          <Avatar
            size="sm"
            src={getFileURL(compareCreator?.avatar_url ?? "")}
            name={compareCreator?.display_name}
            className="shrink-0"
          />
          <div>
            <p className="text-12 font-medium">
              {renderFormattedDate(compareVersion.last_saved_at)}, {renderFormattedTime(compareVersion.last_saved_at)}
            </p>
            <p className="text-11 text-tertiary">{compareCreator?.display_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Avatar
            size="sm"
            src={getFileURL(baseCreator?.avatar_url ?? "")}
            name={baseCreator?.display_name}
            className="shrink-0"
          />
          <div>
            <p className="text-12 font-medium">
              {renderFormattedDate(baseVersion.last_saved_at)}, {renderFormattedTime(baseVersion.last_saved_at)}
            </p>
            <p className="text-11 text-tertiary">{baseCreator?.display_name}</p>
          </div>
        </div>
      </div>

      {/* Diff content */}
      <div className="vertical-scrollbar scrollbar-sm flex-1 overflow-y-scroll p-5">
        {diffSegments.length === 0 ? (
          <p className="text-13 text-tertiary">No differences found between these versions.</p>
        ) : (
          <div className="text-13 leading-relaxed">
            {diffSegments.map((segment) => (
              <DiffSegmentView key={`${segment.type}-${segment.oldText}-${segment.newText}`} segment={segment} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
});
