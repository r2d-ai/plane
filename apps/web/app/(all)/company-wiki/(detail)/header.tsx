/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { WikiIcon } from "@plane/propel/icons";
import type { ICustomSearchSelectOption } from "@plane/types";
import { Breadcrumbs, Header, BreadcrumbNavigationSearchDropdown } from "@plane/ui";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { PageAccessIcon } from "@/components/common/page-access-icon";
import { SwitcherIcon, SwitcherLabel } from "@/components/common/switcher-label";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
// plane web imports
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

export const CompanyWikiDetailsHeader = observer(function CompanyWikiDetailsHeader() {
  // router
  const router = useAppRouter();
  const { pageId } = useParams();
  // store hooks
  const { getCurrentWorkspacePageIdsByTab, getPageById } = usePageStore(storeType);
  const page = usePage({
    pageId: pageId?.toString() ?? "",
    storeType,
  });
  // derived values
  const pageIds = getCurrentWorkspacePageIdsByTab("public") ?? [];

  const switcherOptions = pageIds
    .map((id) => {
      const _page = id === pageId ? page : getPageById(id);
      if (!_page) return;
      return {
        value: _page.id,
        query: _page.name,
        content: (
          <div className="flex items-center justify-between gap-2">
            <SwitcherLabel logo_props={_page.logo_props} name={getPageName(_page.name)} LabelIcon={WikiIcon} />
            <PageAccessIcon {..._page} />
          </div>
        ),
      };
    })
    .filter((option) => option !== undefined) as ICustomSearchSelectOption[];

  if (!page) return null;

  return (
    <Header>
      <Header.LeftItem>
        <div>
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label="Company Wiki"
                  href="/company-wiki/"
                  icon={<WikiIcon className="h-4 w-4 text-tertiary" />}
                />
              }
            />

            <Breadcrumbs.Item
              component={
                <BreadcrumbNavigationSearchDropdown
                  selectedItem={pageId?.toString() ?? ""}
                  navigationItems={switcherOptions}
                  onChange={(value: string) => {
                    router.push(`/company-wiki/${value}`);
                  }}
                  title={getPageName(page?.name)}
                  icon={
                    <Breadcrumbs.Icon>
                      <SwitcherIcon logo_props={page.logo_props} LabelIcon={WikiIcon} size={16} />
                    </Breadcrumbs.Icon>
                  }
                  isLast
                />
              }
            />
          </Breadcrumbs>
        </div>
      </Header.LeftItem>
      <Header.RightItem>
        <span className="text-13 text-tertiary">Company Wiki</span>
      </Header.RightItem>
    </Header>
  );
});
