/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// component
import { Outlet } from "react-router";
import useSWR from "swr";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
// plane web hooks
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { EPageStoreType, usePageStore } from "@/hooks/store";
// local components
import { CompanyWikiDetailsHeader } from "./header";

export default function CompanyWikiDetailsLayout() {
  const workspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;
  const { fetchPagesList } = usePageStore(EPageStoreType.WORKSPACE);
  // fetching pages list
  useSWR(`WORKSPACE_PAGES_${workspaceSlug}`, workspaceSlug ? () => fetchPagesList(workspaceSlug) : null);
  return (
    <>
      <AppHeader header={<CompanyWikiDetailsHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
