/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { BookOpen, LayoutGrid, ListTree } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Tabs } from "@plane/propel/tabs";
import { Button } from "@plane/propel/button";
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
  /** Drives the wiki home hero copy. */
  variant?: "workspace" | "company";
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
  const { pageType, storeType, workspaceSlug, buildPageHref, canCreatePage, variant = "workspace" } = props;
  const { t } = useTranslation();
  const pageStore = usePageStore(EPageStoreType.WORKSPACE);
  const { canCurrentUserCreatePage } = usePageStore(EPageStoreType.WORKSPACE);
  const [viewMode, setViewMode] = useState<"list" | "tree">("tree");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());

  const showCreate = useMemo(
    () => canCreatePage ?? canCurrentUserCreatePage,
    [canCreatePage, canCurrentUserCreatePage]
  );

  const pageIds = pageStore.getCurrentWorkspaceFilteredPageIdsByTab(pageType) ?? [];
  const pageCount = pageIds.length;

  const isTreeSupported = pageType === "public" || pageType === "private";

  const allExpandableIds = useMemo(() => {
    const ids = new Set<string>();
    const idsForTab = pageStore.getCurrentWorkspaceFilteredPageIdsByTab(pageType) ?? [];
    idsForTab.forEach((pageId) => {
      const page = pageStore.getPageById(pageId);
      if (!page?.id) return;
      const hasChild = idsForTab.some((candidateId) => pageStore.getPageById(candidateId)?.parent_id === page.id);
      if (hasChild) ids.add(page.id);
    });
    return ids;
  }, [pageStore, pageType]);

  const handleExpandAll = useCallback(() => {
    setExpandedIds(new Set(allExpandableIds));
  }, [allExpandableIds]);

  const handleCollapseAll = useCallback(() => {
    setExpandedIds(new Set());
  }, []);

  const heroTitle = variant === "company" ? t("wiki.home.company_title") : t("wiki.home.workspace_title");
  const heroDescription =
    variant === "company" ? t("wiki.home.company_description") : t("wiki.home.workspace_description");

  return (
    <div className="flex h-full w-full flex-col gap-4 overflow-hidden">
      <section className="rounded-lg border border-subtle bg-surface-1 px-4 py-3" data-testid="wiki-home-hero">
        <div className="flex items-start gap-3">
          <div className="grid size-9 place-items-center rounded-md bg-layer-1 text-accent-primary">
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-15 font-semibold text-primary">{heroTitle}</h2>
              {pageCount > 0 && (
                <span className="rounded-full bg-layer-1 px-2 py-0.5 text-11 text-secondary">
                  {t("wiki.home.page_count", { count: pageCount })}
                </span>
              )}
            </div>
            <p className="mt-1 text-13 text-secondary">{heroDescription}</p>
            <p className="mt-2 text-12 text-tertiary">{t("wiki.search_unified_hint")}</p>
          </div>
        </div>
      </section>

      {isTreeSupported && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-1">
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
          {viewMode === "tree" && allExpandableIds.size > 0 && (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={handleExpandAll}>
                {t("wiki.tree.expand_all")}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleCollapseAll}>
                {t("wiki.tree.collapse_all")}
              </Button>
            </div>
          )}
        </div>
      )}

      <div
        className="flex-1 overflow-auto rounded-lg border border-subtle bg-surface-1 px-2 py-2"
        data-testid="wiki-pages-root"
      >
        {viewMode === "tree" && isTreeSupported ? (
          <WikiTreeView
            workspaceSlug={workspaceSlug}
            pageType={pageType}
            buildPageHref={buildPageHref}
            canCreatePage={showCreate}
            expandedIds={expandedIds}
            onExpandedIdsChange={setExpandedIds}
          />
        ) : (
          <PagesListRoot pageType={pageType} storeType={storeType} />
        )}
      </div>
    </div>
  );
});
