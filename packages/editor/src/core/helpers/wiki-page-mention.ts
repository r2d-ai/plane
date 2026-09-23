/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPageSearchResponse } from "@plane/types";

type TWikiPageMentionTarget = Pick<TPageSearchResponse, "id" | "workspace__slug" | "projects__id">;

type TBuildWikiPageMentionPathOptions = {
  /** When true, links use the instance-wide `/company-wiki/:id` route. */
  companyWikiSurface?: boolean;
  /** Prefer this project when the page is attached to multiple projects. */
  projectId?: string;
};

/** Workspace wiki pages are pages that are not scoped to a project. */
export function isWorkspaceWikiPage(page: TPageSearchResponse): boolean {
  const projectIds = page.projects__id;
  return !projectIds || projectIds.length === 0;
}

/** Build the in-app path for a wiki page mention chip or export link. */
export function buildWikiPageMentionPath(
  page: TWikiPageMentionTarget,
  options?: TBuildWikiPageMentionPathOptions
): string {
  const pageId = page.id ?? "";
  const workspaceSlug = page.workspace__slug ?? "";
  const projectIds = page.projects__id ?? [];

  if (!pageId) return "/";

  if (options?.companyWikiSurface) {
    return `/company-wiki/${pageId}`;
  }

  const preferredProjectId =
    options?.projectId && projectIds.includes(options.projectId) ? options.projectId : projectIds[0];

  if (preferredProjectId) {
    return `/${workspaceSlug}/projects/${preferredProjectId}/pages/${pageId}`;
  }

  return `/${workspaceSlug}/wiki/${pageId}`;
}
