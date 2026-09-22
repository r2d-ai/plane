/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
import type { TPageNavigationTabs } from "@plane/types";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { EPageStoreType as EPageStoreTypeType } from "@/hooks/store";
import type { IProjectPageStore } from "@/store/pages/project-page.store";
import type { IWorkspacePageStore } from "@/store/pages/workspace-page.store";
// local imports
import { PagesListHeaderRoot } from "./header";
import { PagesListMainContent } from "./pages-list-main-content";

type TProjectFetchPagesList = IProjectPageStore["fetchPagesList"];
type TWorkspaceFetchPagesList = IWorkspacePageStore["fetchPagesList"];

type TPageView = {
  children: React.ReactNode;
  pageType: TPageNavigationTabs;
  storeType: EPageStoreTypeType;
  workspaceSlug: string;
  /** Project id for project-scoped pages; ignored when `storeType` is workspace. */
  projectId?: string;
  /** When set, tab nav uses this href builder instead of project-scoped tabs. */
  buildTabHref?: (params: { workspaceSlug: string; tabKey: TPageNavigationTabs }) => string;
  /** Optional build hook for the redirect URL after creating a new page. */
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  /** Optional permission predicate for the empty-state create CTA. */
  canCreatePage?: boolean;
};

export const PagesListView = observer(function PagesListView(props: TPageView) {
  const { children, pageType, projectId, storeType, workspaceSlug, buildTabHref, buildPageHref, canCreatePage } = props;
  // store hooks
  const isWorkspaceStore = storeType === EPageStoreType.WORKSPACE;
  const pageStore: IProjectPageStore | IWorkspacePageStore = usePageStore(storeType);
  const { isAnyPageAvailable, fetchPagesList } = pageStore;
  // fetching pages list
  const cacheKey = isWorkspaceStore ? `WORKSPACE_PAGES_${workspaceSlug}` : `PROJECT_PAGES_${projectId}`;
  const canFetch = !!workspaceSlug && !!pageType && (isWorkspaceStore || !!projectId);
  const fetcher = canFetch
    ? () => {
        if (isWorkspaceStore) return (fetchPagesList as TWorkspaceFetchPagesList)(workspaceSlug, pageType);
        return (fetchPagesList as TProjectFetchPagesList)(workspaceSlug, projectId as string, pageType);
      }
    : null;
  useSWR(canFetch ? cacheKey : null, fetcher);

  // pages loader
  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden">
      {/* tab header */}
      {isAnyPageAvailable && (
        <PagesListHeaderRoot
          pageType={pageType}
          projectId={projectId}
          storeType={storeType}
          workspaceSlug={workspaceSlug}
          buildTabHref={buildTabHref}
        />
      )}
      <PagesListMainContent
        pageType={pageType}
        storeType={storeType}
        buildPageHref={buildPageHref}
        canCreatePage={canCreatePage}
      >
        {children}
      </PagesListMainContent>
    </div>
  );
});
