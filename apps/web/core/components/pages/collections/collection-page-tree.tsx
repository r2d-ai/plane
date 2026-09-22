/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { ChevronRight, Lock, Plus } from "lucide-react";
import useSWR from "swr";
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Button } from "@plane/ui";
import { cn } from "@plane/utils";
import { useAppRouter } from "@/hooks/use-app-router";
import { usePageCollectionStore, usePageStore } from "@/hooks/store";
import { EPageStoreType } from "@/hooks/store";
import type { IWorkspacePageStore } from "@/store/pages/workspace-page.store";

const COLLECTION_PAGE_DRAG_TYPE = "COLLECTION_PAGE";
const DEFAULT_SORT_ORDER = 65535;
const SIBLING_EDGE_RATIO = 0.25;

type TCollectionPage = {
  id: string;
  page: string;
  sort_order: number;
  page_detail: {
    id: string;
    name: string;
    access: number;
    parent: string | null;
    sort_order: number;
  };
};

type TCollectionTreeNode = TCollectionPage & {
  children: TCollectionTreeNode[];
  depth: number;
};

type TDropPosition = "before" | "after" | "inside";

type TDragData = {
  type: typeof COLLECTION_PAGE_DRAG_TYPE;
  pageId: string;
};

function sortByOrder(a: TCollectionPage, b: TCollectionPage) {
  return (a.sort_order ?? DEFAULT_SORT_ORDER) - (b.sort_order ?? DEFAULT_SORT_ORDER);
}

function buildCollectionTree(pages: TCollectionPage[]): TCollectionTreeNode[] {
  const byPageId = new Map<string, TCollectionTreeNode>();
  pages.forEach((p) => {
    byPageId.set(p.page, { ...p, children: [], depth: 0 });
  });

  const roots: TCollectionTreeNode[] = [];
  byPageId.forEach((node) => {
    const parentId = node.page_detail.parent;
    const parent = parentId ? byPageId.get(parentId) : undefined;
    if (parent && parent.page !== node.page) {
      node.depth = parent.depth + 1;
      parent.children.push(node);
      return;
    }
    roots.push(node);
  });

  const sortRecursive = (nodes: TCollectionTreeNode[]) => {
    nodes.sort(sortByOrder);
    nodes.forEach((node) => sortRecursive(node.children));
  };
  sortRecursive(roots);

  return roots;
}

function computeDropPosition(clientY: number, element: HTMLElement): TDropPosition {
  const rect = element.getBoundingClientRect();
  if (!rect.height) return "inside";
  const ratio = (clientY - rect.top) / rect.height;
  if (ratio < SIBLING_EDGE_RATIO) return "before";
  if (ratio > 1 - SIBLING_EDGE_RATIO) return "after";
  return "inside";
}

function getPageIcon(access: number) {
  if (access === EPageAccess.PRIVATE) return <Lock className="h-3.5 w-3.5 text-tertiary" />;
  return <PageIcon className="h-3.5 w-3.5 text-tertiary" />;
}

type TreeNodeProps = {
  node: TCollectionTreeNode;
  pageHref: (pageId: string) => string;
  expandedIds: Set<string>;
  toggleExpanded: (id: string) => void;
  onMove?: (source: TDragData, target: TDragData, position: TDropPosition) => void;
};

const CollectionTreeNode = observer(function CollectionTreeNode(props: TreeNodeProps) {
  const { node, pageHref, expandedIds, toggleExpanded, onMove } = props;
  const { t } = useTranslation();
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [dropPosition, setDropPosition] = useState<TDropPosition | null>(null);
  const isExpanded = expandedIds.has(node.page);
  const hasChildren = node.children.length > 0;

  const handleToggle = useCallback(() => {
    if (hasChildren) toggleExpanded(node.page);
  }, [hasChildren, node.page, toggleExpanded]);

  useEffect(() => {
    const element = rowRef.current;
    if (!element) return;
    const data: TDragData = { type: COLLECTION_PAGE_DRAG_TYPE, pageId: node.page };
    return combine(
      draggable({
        element,
        getInitialData: () => data,
        canDrag: () => !!node.page,
      }),
      dropTargetForElements({
        element,
        getData: () => data,
        canDrop: ({ source }) => {
          const sourceData = source.data as TDragData;
          return sourceData?.type === COLLECTION_PAGE_DRAG_TYPE && sourceData.pageId !== node.page;
        },
        onDrag: ({ location, self }) =>
          setDropPosition(computeDropPosition(location.current.input.clientY, self.element as HTMLElement)),
        onDragLeave: () => setDropPosition(null),
        onDrop: ({ source, self, location }) => {
          setDropPosition(null);
          const sourceData = source.data as TDragData;
          if (sourceData?.type !== COLLECTION_PAGE_DRAG_TYPE || !onMove) return;
          const position = computeDropPosition(location.current.input.clientY, self.element as HTMLElement);
          onMove(sourceData, self.data as TDragData, position);
        },
      })
    );
  }, [node.page, onMove]);

  return (
    <li className="flex flex-col" data-page-id={node.page}>
      <div
        ref={rowRef}
        className={cn(
          "group/coll-row flex h-7 cursor-pointer items-center gap-1 rounded-sm px-1 text-13 transition-colors hover:bg-layer-1",
          {
            "border-t-2 border-accent-strong": dropPosition === "before",
            "border-b-2 border-accent-strong": dropPosition === "after",
            "bg-layer-1 ring-1 ring-accent-strong": dropPosition === "inside",
          }
        )}
        style={{ paddingLeft: `${4 + node.depth * 16}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={handleToggle}
            className="grid size-4 place-items-center rounded-sm text-tertiary transition-colors hover:bg-layer-2 hover:text-primary"
          >
            <ChevronRight className={cn("size-3 transition-transform", { "rotate-90": isExpanded })} />
          </button>
        ) : (
          <span className="size-4" aria-hidden />
        )}
        <a href={pageHref(node.page)} className="flex flex-1 items-center gap-2 truncate text-primary">
          {getPageIcon(node.page_detail.access)}
          <span className="truncate">{node.page_detail.name || t("wiki.untitled")}</span>
          {hasChildren && <span className="ml-auto text-11 text-tertiary">{node.children.length}</span>}
        </a>
      </div>
      {hasChildren && isExpanded && (
        <ul className="flex flex-col">
          {node.children.map((child) => (
            <CollectionTreeNode
              key={child.page}
              node={child}
              pageHref={pageHref}
              expandedIds={expandedIds}
              toggleExpanded={toggleExpanded}
              onMove={onMove}
            />
          ))}
        </ul>
      )}
    </li>
  );
});

type TProps = {
  workspaceSlug: string;
  collectionId: string;
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  canCreatePage?: boolean;
};

export const CollectionPageTree = observer(function CollectionPageTree(props: TProps) {
  const { workspaceSlug, collectionId, buildPageHref, canCreatePage } = props;
  const router = useAppRouter();
  const { t } = useTranslation();
  const collectionStore = usePageCollectionStore();
  const pageStore = usePageStore(EPageStoreType.WORKSPACE) as IWorkspacePageStore;
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());

  const { data: collectionPages } = useSWR(
    workspaceSlug && collectionId ? `COLLECTION_PAGES_${collectionId}` : null,
    () => collectionStore.fetchCollectionPages(workspaceSlug, collectionId)
  );

  const pages = useMemo(() => collectionPages || [], [collectionPages]);
  const tree = useMemo(() => buildCollectionTree(pages), [pages]);

  const toggleExpanded = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const defaultHref = useCallback(
    (pageId: string) => (buildPageHref ? buildPageHref({ workspaceSlug, pageId }) : `/${workspaceSlug}/wiki/${pageId}`),
    [buildPageHref, workspaceSlug]
  );

  const handleAddPage = useCallback(async () => {
    const newPage = await pageStore.createPage({ access: EPageAccess.PUBLIC } as never);
    if (newPage?.id) {
      await collectionStore.addPageToCollection(workspaceSlug, collectionId, newPage.id);
      router.push(defaultHref(newPage.id));
    }
  }, [pageStore, collectionStore, workspaceSlug, collectionId, defaultHref, router]);

  const pagesRef = useRef(pages);
  pagesRef.current = pages;

  const resolveSortOrder = useCallback((target: TDragData, position: TDropPosition): number => {
    if (position === "inside") return DEFAULT_SORT_ORDER;
    const currentPages = pagesRef.current;
    const siblings = currentPages.slice().toSorted(sortByOrder);
    const targetIndex = siblings.findIndex((p) => p.page === target.pageId);
    if (targetIndex === -1) return DEFAULT_SORT_ORDER;
    const insertAt = position === "before" ? targetIndex : targetIndex + 1;
    const before = siblings[insertAt - 1]?.sort_order;
    const after = siblings[insertAt]?.sort_order;
    if (before !== undefined && after !== undefined && before !== after) return (before + after) / 2;
    if (before !== undefined) return before + 1;
    if (after !== undefined) return after - 1;
    return DEFAULT_SORT_ORDER;
  }, []);

  const handleMove = useCallback(
    async (source: TDragData, target: TDragData, position: TDropPosition) => {
      const sortOrder = resolveSortOrder(target, position);
      const currentPages = pagesRef.current;
      const pageIds = currentPages.map((p) => p.page);
      const sortOrders = currentPages.map((p) => (p.page === source.pageId ? sortOrder : p.sort_order));
      try {
        await collectionStore.reorderPages(workspaceSlug, collectionId, pageIds, sortOrders);
      } catch {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("common.error"),
          message: t("wiki.collections.reorder_failed"),
        });
      }
    },
    [collectionStore, workspaceSlug, collectionId, resolveSortOrder, t]
  );

  if (pages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <p className="text-13 text-tertiary">{t("wiki.collections.no_pages")}</p>
        {canCreatePage && (
          <Button variant="outline-primary" size="sm" onClick={handleAddPage} className="mt-2">
            <Plus className="mr-1 h-3.5 w-3.5" />
            {t("wiki.collections.add_page")}
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <ul className="flex flex-col gap-0.5" data-testid="collection-page-tree">
        {tree.map((node) => (
          <Fragment key={node.page}>
            <CollectionTreeNode
              node={node}
              pageHref={defaultHref}
              expandedIds={expandedIds}
              toggleExpanded={toggleExpanded}
              onMove={handleMove}
            />
          </Fragment>
        ))}
      </ul>
      {canCreatePage && (
        <button
          type="button"
          onClick={handleAddPage}
          className="flex w-full items-center gap-1 rounded-sm px-1 py-1 text-13 text-tertiary transition-colors hover:bg-layer-1 hover:text-primary"
        >
          <Plus className="h-3.5 w-3.5" />
          {t("wiki.collections.add_page")}
        </button>
      )}
    </div>
  );
});
