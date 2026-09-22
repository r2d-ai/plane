/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { LayoutGrid, ListTree } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Tabs } from "@plane/propel/tabs";
import type { TPageNavigationTabs } from "@plane/types";
// components
import { PagesListRoot } from "@/components/pages/list/root";
import { WikiTreeView } from "@/components/pages/list/wiki-tree";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { EPageStoreType as EPageStoreTypeType } from "@/hooks/store";

type TProps = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreTypeType;
  workspaceSlug: string;
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  canCreatePage?: boolean;
};

/**
 * @description Workspace Wiki list root (WIKI-04a).
 *
 * Renders the Wiki pages as either a flat list (default) or a recursive
 * hierarchy tree. The user can toggle the view mode via the segmented
 * control at the top. Counts respect permission filtering because the
 * store already filters out pages the current user cannot access.
 */
export const WikiPagesListRoot = observer(function WikiPagesListRoot(props: TProps) {
  const { pageType, storeType, workspaceSlug, buildPageHref, canCreatePage } = props;
  const { t } = useTranslation();
  const { canCurrentUserCreatePage } = usePageStore(EPageStoreType.WORKSPACE);
  const [viewMode, setViewMode] = useState<"list" | "tree">("tree");

  const showCreate = useMemo(
    () => canCreatePage ?? canCurrentUserCreatePage,
    [canCreatePage, canCurrentUserCreatePage]
  );

  // Archived and favorites are best rendered as a flat list — the tree view
  // is reserved for the live "public" and "private" sections.
  const isTreeSupported = pageType === "public" || pageType === "private";

  return (
    <div className="flex h-full w-full flex-col gap-3 overflow-hidden">
      {isTreeSupported && (
        <div className="flex items-center justify-between px-1">
          <Tabs value={viewMode} onValueChange={(value) => setViewMode(value as "list" | "tree")} className="h-7">
            <Tabs.List>
              <Tabs.Trigger value="tree" className="flex items-center gap-1 text-13">
                <ListTree className="h-3.5 w-3.5" />
                <span>{t("wiki.tree.root_label")}</span>
              </Tabs.Trigger>
              <Tabs.Trigger value="list" className="flex items-center gap-1 text-13">
                <LayoutGrid className="h-3.5 w-3.5" />
                <span>{t("common.list")}</span>
              </Tabs.Trigger>
            </Tabs.List>
          </Tabs>
        </div>
      )}
      <div className="flex-1 overflow-auto px-1" data-testid="wiki-pages-root">
        {viewMode === "tree" && isTreeSupported ? (
          <WikiTreeView
            workspaceSlug={workspaceSlug}
            pageType={pageType}
            buildPageHref={buildPageHref}
            canCreatePage={showCreate}
          />
        ) : (
          <PagesListRoot pageType={pageType} storeType={storeType} />
        )}
      </div>
    </div>
  );
});
