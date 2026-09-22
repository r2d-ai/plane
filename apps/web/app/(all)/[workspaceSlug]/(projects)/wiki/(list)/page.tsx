/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useSearchParams } from "next/navigation";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TPageNavigationTabs } from "@plane/types";
// components
import { CollectionsSection } from "@/components/pages/collections";
import { PageHead } from "@/components/core/page-title";
import { WikiPagesListRoot } from "@/components/pages/list/wiki-pages-root";
import { PagesListView } from "@/components/pages/pages-list-view";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { Route } from "./+types/page";

const getPageType = (pageType?: string | null): TPageNavigationTabs => {
  if (pageType === "private") return "private";
  if (pageType === "archived") return "archived";
  if (pageType === "favorites") return "favorites";
  return "public";
};

function WorkspaceWikiListPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const searchParams = useSearchParams();
  const type = searchParams.get("type");
  const pageType = getPageType(type);
  const { t } = useTranslation();

  // store hooks
  const { canCurrentUserCreatePage } = usePageStore(EPageStoreType.WORKSPACE);

  return (
    <>
      <PageHead title={workspaceSlug ? `${workspaceSlug} - ${t("sidebar.wiki")}` : t("sidebar.wiki")} />
      <PagesListView
        pageType={pageType}
        storeType={EPageStoreType.WORKSPACE}
        workspaceSlug={workspaceSlug}
        buildTabHref={({ workspaceSlug: slug, tabKey }) => `/${slug}/wiki?type=${tabKey}`}
        buildPageHref={({ workspaceSlug: slug, pageId }) => `/${slug}/wiki/${pageId}`}
        canCreatePage={canCurrentUserCreatePage}
        emptyStateVariant="workspace_wiki"
        collectionsSection={
          <CollectionsSection
            workspaceSlug={workspaceSlug}
            buildPageHref={({ workspaceSlug: slug, pageId }) => `/${slug}/wiki/${pageId}`}
            canCreatePage={canCurrentUserCreatePage}
          />
        }
      >
        <WikiPagesListRoot
          pageType={pageType}
          storeType={EPageStoreType.WORKSPACE}
          workspaceSlug={workspaceSlug}
          buildPageHref={({ workspaceSlug: slug, pageId }) => `/${slug}/wiki/${pageId}`}
          canCreatePage={canCurrentUserCreatePage}
        />
      </PagesListView>
    </>
  );
}

export default observer(WorkspaceWikiListPage);
