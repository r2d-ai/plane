/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import Link from "next/link";
import { observer } from "mobx-react";
// types
import { useTranslation } from "@plane/i18n";
import type { TPageNavigationTabs } from "@plane/types";
// helpers
import { cn } from "@plane/utils";

type TPageTabNavigation = {
  workspaceSlug: string;
  projectId?: string;
  pageType: TPageNavigationTabs;
  /**
   * Optional workspace-scoped tab href builder. When provided, tabs render at
   * the returned path with `?type=...` instead of the project-scoped
   * `/projects/:projectId/pages?type=...`. Use this for company wiki tabs
   * (`() => "/company-wiki"`) and workspace wiki tabs
   * (`() => `/${workspaceSlug}/wiki``).
   */
  buildTabHref?: (params: { workspaceSlug: string; tabKey: TPageNavigationTabs }) => string;
};

export const PageTabNavigation = observer(function PageTabNavigation(props: TPageTabNavigation) {
  const { workspaceSlug, projectId, pageType, buildTabHref } = props;
  const { t } = useTranslation();

  const tabs: { key: TPageNavigationTabs; label: string }[] = [
    { key: "public", label: t("wiki.tabs.public") },
    { key: "private", label: t("wiki.tabs.private") },
    { key: "archived", label: t("wiki.tabs.archived") },
  ];

  const handleTabClick = (e: React.MouseEvent<HTMLAnchorElement>, tabKey: TPageNavigationTabs) => {
    if (tabKey === pageType) e.preventDefault();
  };

  const tabHref = (tabKey: TPageNavigationTabs): string => {
    if (buildTabHref) return buildTabHref({ workspaceSlug, tabKey });
    return `/${workspaceSlug}/projects/${projectId}/pages?type=${tabKey}`;
  };

  return (
    <div className="relative flex h-full items-center">
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tabHref(tab.key)}
          onClick={(e) => handleTabClick(e, tab.key)}
          className="flex h-full flex-col"
        >
          <div
            className={cn(`flex flex-1 items-center justify-center px-4 text-13 font-medium transition-all`, {
              "text-accent-primary": tab.key === pageType,
            })}
          >
            {tab.label}
          </div>
          <div
            className={cn(`w-full rounded-t border-t-2 border-transparent transition-all`, {
              "border-accent-strong": tab.key === pageType,
            })}
          />
        </Link>
      ))}
    </div>
  );
});
