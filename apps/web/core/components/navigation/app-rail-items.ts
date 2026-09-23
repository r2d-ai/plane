/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// helpers
import { getDefaultWikiPath } from "../../helpers/wiki-routes";

export type AppRailItemKey = "work" | "wiki";

export type AppRailItem = {
  key: AppRailItemKey;
  label: string;
  href: string;
  isActive: boolean;
};

type BuildAppRailItemsParams = {
  workWorkspaceSlug: string;
  wikiWorkspaceSlug: string;
  pathname: string;
};

export const buildAppRailItems = ({
  workWorkspaceSlug,
  wikiWorkspaceSlug,
  pathname,
}: BuildAppRailItemsParams): AppRailItem[] => {
  const wikiHref = wikiWorkspaceSlug.trim() ? getDefaultWikiPath(wikiWorkspaceSlug) : "/wiki";
  const isWikiActive = pathname === "/wiki" || pathname.startsWith("/wiki/");

  const workHref = `/${workWorkspaceSlug}/`;
  const isWorkActive =
    !isWikiActive && (pathname === `/${workWorkspaceSlug}` || pathname.startsWith(`/${workWorkspaceSlug}/`));

  return [
    { key: "work", label: "Work", href: workHref, isActive: isWorkActive },
    { key: "wiki", label: "Wiki", href: wikiHref, isActive: isWikiActive },
  ];
};
