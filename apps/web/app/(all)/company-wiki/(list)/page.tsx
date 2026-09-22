/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useSearchParams } from "next/navigation";
// plane imports
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TPageNavigationTabs } from "@plane/types";
// components
import { PageHead } from "@/components/core/page-title";
import { CompanyWikiRouteScope } from "@/components/pages/company-wiki-route-scope";
import { PagesListRoot } from "@/components/pages/list/root";
import { PagesListView } from "@/components/pages/pages-list-view";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

const getPageType = (pageType?: string | null): TPageNavigationTabs => {
  if (pageType === "private") return "private";
  if (pageType === "archived") return "archived";
  return "public";
};

/**
 * Company Wiki landing page (spec §29.1, §29.13).
 *
 * Resolves `COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG` and renders the
 * Workspace Wiki UI against that workspace. The URL never contains the
 * workspace slug so the same canonical page is reachable from every
 * workspace.
 */
const CompanyWikiListPage = observer(function CompanyWikiListPage() {
  const searchParams = useSearchParams();
  const type = searchParams.get("type");
  const pageType = getPageType(type);
  // i18n
  const { t } = useTranslation();
  // store hooks
  const { canCurrentUserCreatePage } = usePageStore(EPageStoreType.WORKSPACE);
  const workspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;

  return (
    <>
      <PageHead title={t("sidebar.company_wiki")} />
      <CompanyWikiRouteScope />
      <PagesListView
        pageType={pageType}
        storeType={EPageStoreType.WORKSPACE}
        workspaceSlug={workspaceSlug}
        buildTabHref={({ tabKey }) => `/company-wiki?type=${tabKey}`}
        buildPageHref={({ pageId }) => `/company-wiki/${pageId}`}
        canCreatePage={canCurrentUserCreatePage}
        emptyStateVariant="company_wiki"
      >
        <PagesListRoot pageType={pageType} storeType={EPageStoreType.WORKSPACE} />
      </PagesListView>
    </>
  );
});

export default CompanyWikiListPage;
