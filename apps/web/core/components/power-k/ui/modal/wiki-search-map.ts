import type { IWorkspacePageSearchResult, TWikiSearchResult } from "@plane/types";
import { getWikiPagePath } from "../../../../helpers/wiki-routes";

export const isWikiPath = (pathname: string): boolean => /^\/wiki(?:\/|$)/.test(pathname);

export const wikiSearchResultPath = (result: Pick<TWikiSearchResult, "workspace_slug" | "page_id">): string =>
  getWikiPagePath(result.workspace_slug, result.page_id);

export const workPageSearchResultPath = (
  page: Pick<IWorkspacePageSearchResult, "workspace__slug" | "id" | "project_ids">,
  projectId?: string
): string => {
  const selectedProjectId = projectId && page.project_ids.includes(projectId) ? projectId : page.project_ids[0];
  return selectedProjectId
    ? `/${page.workspace__slug}/projects/${selectedProjectId}/pages/${page.id}`
    : getWikiPagePath(page.workspace__slug, page.id);
};
