/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { PageIcon } from "@plane/propel/icons";
import type { ICustomSearchSelectOption } from "@plane/types";
import { Breadcrumbs, Header, BreadcrumbNavigationSearchDropdown } from "@plane/ui";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { PageAccessIcon } from "@/components/common/page-access-icon";
import { SwitcherIcon, SwitcherLabel } from "@/components/common/switcher-label";
import { CommonWorkspaceBreadcrumbs } from "@/components/breadcrumbs/common";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
import { useWorkspace } from "@/hooks/store/use-workspace";
// plane web imports
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

export const WikiDetailsHeader = observer(function WikiDetailsHeader() {
  // router
  const router = useAppRouter();
  const { workspaceSlug, pageId } = useParams();
  // store hooks
  const { getWorkspaceBySlug } = useWorkspace();
  const { getCurrentWorkspacePageIdsByTab, getPageById } = usePageStore(storeType);
  const page = usePage({
    pageId: pageId?.toString() ?? "",
    storeType,
  });
  // derived values
  const workspace = workspaceSlug ? getWorkspaceBySlug(workspaceSlug.toString()) : undefined;
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
            <SwitcherLabel logo_props={_page.logo_props} name={getPageName(_page.name)} LabelIcon={PageIcon} />
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
            <CommonWorkspaceBreadcrumbs workspaceSlug={workspaceSlug?.toString()} />
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label="Wiki"
                  href={`/${workspaceSlug}/wiki/`}
                  icon={<PageIcon className="h-4 w-4 text-tertiary" />}
                />
              }
            />

            <Breadcrumbs.Item
              component={
                <BreadcrumbNavigationSearchDropdown
                  selectedItem={pageId?.toString() ?? ""}
                  navigationItems={switcherOptions}
                  onChange={(value: string) => {
                    router.push(`/${workspaceSlug}/wiki/${value}`);
                  }}
                  title={getPageName(page?.name)}
                  icon={
                    <Breadcrumbs.Icon>
                      <SwitcherIcon logo_props={page.logo_props} LabelIcon={PageIcon} size={16} />
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
        {/* Wiki-specific actions wired in WIKI-03b */}
        <span className="text-13 text-tertiary">{workspace?.name || workspaceSlug}</span>
      </Header.RightItem>
    </Header>
  );
});
