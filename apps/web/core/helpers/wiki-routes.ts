import type { TWikiPersonalSection } from "@plane/types";

const cleanSegment = (value: string): string => value.trim().replace(/^\/+|\/+$/g, "");

export const getWikiPersonalPath = (section: TWikiPersonalSection): string => `/wiki/personal/${section}`;

export const getWikiHomePath = (workspaceSlug: string): string => {
  const slug = cleanSegment(workspaceSlug);
  if (!slug) throw new Error("Wiki workspace slug is required");
  return `/wiki/${slug}`;
};

export const getDefaultWikiPath = (defaultWorkspaceSlug: string): string => {
  const slug = cleanSegment(defaultWorkspaceSlug);
  if (!slug) throw new Error("Default Wiki workspace slug is not configured");
  return getWikiHomePath(slug);
};

export const getWikiPagePath = (workspaceSlug: string, pageId: string): string => {
  const id = cleanSegment(pageId);
  if (!id) throw new Error("Wiki page id is required");
  return `${getWikiHomePath(workspaceSlug)}/${id}`;
};

export const getWikiCollectionPath = (workspaceSlug: string, collectionId: string): string => {
  const id = cleanSegment(collectionId);
  if (!id) throw new Error("Wiki collection id is required");
  return `${getWikiHomePath(workspaceSlug)}/collections/${id}`;
};

export const resolveLegacyWikiPath = (pathname: string, defaultWorkspaceSlug: string): string | null => {
  const companyMatch = pathname.match(/^\/company-wiki(?:\/([^/]+))?\/?$/);
  if (companyMatch) {
    return companyMatch[1]
      ? getWikiPagePath(defaultWorkspaceSlug, companyMatch[1])
      : getDefaultWikiPath(defaultWorkspaceSlug);
  }

  const workspaceMatch = pathname.match(/^\/([^/]+)\/wiki(?:\/([^/]+))?\/?$/);
  if (!workspaceMatch) return null;
  return workspaceMatch[2] ? getWikiPagePath(workspaceMatch[1], workspaceMatch[2]) : getWikiHomePath(workspaceMatch[1]);
};
