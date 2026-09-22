/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { combine } from "@atlaskit/pragmatic-drag-and-drop/combine";
import { draggable, dropTargetForElements } from "@atlaskit/pragmatic-drag-and-drop/element/adapter";
import { observer } from "mobx-react";
import { Archive, ChevronRight, Globe, Lock, Plus } from "lucide-react";
// plane imports
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageNavigationTabs } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
// store types
import type { TPageInstance } from "@/store/pages/base-page";
import type { IWorkspacePageStore } from "@/store/pages/workspace-page.store";

const WIKI_PAGE_DRAG_TYPE = "WIKI_PAGE";
const DEFAULT_SORT_ORDER = 65535;
/** Fraction of a row's height that counts as "drop before/after" instead of "drop inside". */
const SIBLING_EDGE_RATIO = 0.25;

type TWikiTreePage = TPageInstance;

type TWikiTreeNode = TWikiTreePage & {
  children: TWikiTreeNode[];
  depth: number;
};

type TDropPosition = "before" | "after" | "inside";

type TWikiDragData = {
  type: typeof WIKI_PAGE_DRAG_TYPE;
  pageId: string;
  parentId: string | null;
};

function sortByOrderThenName(a: TWikiTreePage, b: TWikiTreePage) {
  const aOrder = a.sort_order;
  const bOrder = b.sort_order;
  if (aOrder !== undefined && bOrder !== undefined && aOrder !== bOrder) return aOrder - bOrder;
  if (aOrder !== undefined && bOrder === undefined) return -1;
  if (bOrder !== undefined && aOrder === undefined) return 1;
  return (a.name ?? "").localeCompare(b.name ?? "");
}

/**
 * @description Build a tree from a flat list of Wiki pages keyed by `parent_id`.
 * A page whose parent is outside the visible set (or part of a malformed cycle)
 * is treated as a root so no page is ever dropped from the tree.
 */
function buildWikiTree(pages: TWikiTreePage[]): TWikiTreeNode[] {
  const byId = new Map<string, TWikiTreeNode>();
  pages.forEach((page) => {
    if (page.id) byId.set(page.id, { ...page, children: [], depth: 0 });
  });

  const roots: TWikiTreeNode[] = [];
  byId.forEach((node) => {
    const parentId = node.parent_id;
    const parent = parentId ? byId.get(parentId) : undefined;
    if (parent && parent.id !== node.id) {
      node.depth = parent.depth + 1;
      parent.children.push(node);
      return;
    }
    roots.push(node);
  });

  const sortRecursive = (nodes: TWikiTreeNode[]) => {
    nodes.sort(sortByOrderThenName);
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

function getPageIcon(page: TWikiTreePage) {
  if (page.logo_props?.in_use) {
    return <Logo logo={page.logo_props} size={14} type="lucide" />;
  }
  if (page.archived_at) return <Archive className="h-3.5 w-3.5 text-tertiary" />;
  if (page.access === EPageAccess.PRIVATE) return <Lock className="h-3.5 w-3.5 text-tertiary" />;
  return <PageIcon className="h-3.5 w-3.5 text-tertiary" />;
}

function getAccessIcon(page: TWikiTreePage) {
  if (page.archived_at) return <Archive className="h-3 w-3 text-tertiary" />;
  if (page.access === EPageAccess.PUBLIC) return <Globe className="h-3 w-3 text-tertiary" />;
  return <Lock className="h-3 w-3 text-tertiary" />;
}

type TWikiTreeItemProps = {
  node: TWikiTreeNode;
  pageHref: (pageId: string) => string;
  expandedIds: Set<string>;
  toggleExpanded: (id: string) => void;
  onAddSubPage?: (parentId: string) => void;
  onMove?: (source: TWikiDragData, target: TWikiDragData, position: TDropPosition) => void;
  canDropOn?: (targetId: string, sourceId: string) => boolean;
  showAddChild: boolean;
};

const WikiTreeItem = observer(function WikiTreeItem(props: TWikiTreeItemProps) {
  const { node, pageHref, expandedIds, toggleExpanded, onAddSubPage, onMove, canDropOn, showAddChild } = props;
  const { t } = useTranslation();
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [dropPosition, setDropPosition] = useState<TDropPosition | null>(null);
  const isExpanded = expandedIds.has(node.id ?? "");
  const hasChildren = node.children.length > 0;
  const childCount = node.children.length;

  const handleToggle = useCallback(() => {
    if (hasChildren) toggleExpanded(node.id ?? "");
  }, [hasChildren, node.id, toggleExpanded]);

  // drag/drop: the row is both a draggable page and a drop target (reorder siblings, reparent)
  useEffect(() => {
    const element = rowRef.current;
    if (!element || !node.id) return;
    const data: TWikiDragData = {
      type: WIKI_PAGE_DRAG_TYPE,
      pageId: node.id,
      parentId: node.parent_id ?? null,
    };
    return combine(
      draggable({
        element,
        getInitialData: () => data,
        canDrag: () => !!node.id,
      }),
      dropTargetForElements({
        element,
        getData: () => data,
        canDrop: ({ source }) => {
          const sourceData = source.data as TWikiDragData;
          if (sourceData?.type !== WIKI_PAGE_DRAG_TYPE || !sourceData.pageId) return false;
          return canDropOn ? canDropOn(node.id ?? "", sourceData.pageId) : sourceData.pageId !== node.id;
        },
        onDrag: ({ location, self }) =>
          setDropPosition(computeDropPosition(location.current.input.clientY, self.element as HTMLElement)),
        onDragLeave: () => setDropPosition(null),
        onDrop: ({ source, self, location }) => {
          setDropPosition(null);
          const sourceData = source.data as TWikiDragData;
          if (sourceData?.type !== WIKI_PAGE_DRAG_TYPE || !onMove) return;
          const position = computeDropPosition(location.current.input.clientY, self.element as HTMLElement);
          onMove(sourceData, self.data as TWikiDragData, position);
        },
      })
    );
  }, [node.id, node.parent_id, canDropOn, onMove]);

  return (
    <li className="flex flex-col" data-page-id={node.id}>
      <div
        ref={rowRef}
        className={cn(
          "group/wiki-row flex h-7 cursor-pointer items-center gap-1 rounded-sm px-1 text-13 transition-colors hover:bg-layer-1",
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
            aria-label={isExpanded ? t("wiki.actions.collapse") : t("wiki.actions.expand")}
            onClick={handleToggle}
            className="grid size-4 place-items-center rounded-sm text-tertiary transition-colors hover:bg-layer-2 hover:text-primary"
            data-testid="wiki-tree-toggle"
          >
            <ChevronRight
              className={cn("size-3 transition-transform", {
                "rotate-90": isExpanded,
              })}
            />
          </button>
        ) : (
          <span className="size-4" aria-hidden />
        )}
        <a href={node.id ? pageHref(node.id) : "#"} className="flex flex-1 items-center gap-2 truncate text-primary">
          {getPageIcon(node)}
          <span className="truncate">{node.name?.trim() ? node.name : t("wiki.untitled")}</span>
          {hasChildren && (
            <span className="ml-auto text-11 text-tertiary" data-testid="wiki-tree-child-count">
              {t("wiki.tree.child_count_label", { count: childCount })}
            </span>
          )}
        </a>
        <span className="ml-1" aria-hidden>
          {getAccessIcon(node)}
        </span>
        {showAddChild && onAddSubPage && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onAddSubPage(node.id ?? "");
            }}
            className="ml-1 grid size-4 place-items-center rounded-sm text-tertiary opacity-0 transition-opacity group-hover/wiki-row:opacity-100 hover:bg-layer-2 hover:text-primary"
            aria-label={t("wiki.actions.create_sub_page")}
            data-testid="wiki-tree-add-child"
          >
            <Plus className="size-3" />
          </button>
        )}
      </div>
      {hasChildren && isExpanded && (
        <ul className="flex flex-col">
          {node.children.map((child) => (
            <WikiTreeItem
              key={child.id}
              node={child}
              pageHref={pageHref}
              expandedIds={expandedIds}
              toggleExpanded={toggleExpanded}
              onAddSubPage={onAddSubPage}
              onMove={onMove}
              canDropOn={canDropOn}
              showAddChild={showAddChild}
            />
          ))}
        </ul>
      )}
    </li>
  );
});

type TProps = {
  /**
   * Build the absolute URL for a given page id. Defaults to
   * `/${workspaceSlug}/wiki/${pageId}`.
   */
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  workspaceSlug: string;
  /** Active navigation tab; the tree only shows the matching access bucket. */
  pageType?: TPageNavigationTabs;
  /** Whether the current user can create child pages (controls the "+" button). */
  canCreatePage?: boolean;
};

/**
 * @description Recursive Wiki tree component (WIKI-04a §7.2).
 *
 * Renders the current store's Wiki pages as a nested tree grouped by parent.
 * Rows are drag/drop enabled: dropping on a row's top/bottom edge reorders it
 * as a sibling, dropping on the row body reparents it as a child. The move is
 * optimistic and the store rolls back the local order if the server rejects it
 * (cycle/scope guard). Archived pages are never part of the active tree.
 */
export const WikiTreeView = observer(function WikiTreeView(props: TProps) {
  const { buildPageHref, workspaceSlug, pageType, canCreatePage } = props;
  const router = useAppRouter();
  const { t } = useTranslation();
  const pageStore = usePageStore(EPageStoreType.WORKSPACE) as IWorkspacePageStore;
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set());

  const pages = (Object.values(pageStore?.data ?? {}).filter(Boolean) as TWikiTreePage[]).filter((page) => {
    if (!page.id || page.archived_at) return false;
    if (pageType === "private") return page.access === EPageAccess.PRIVATE;
    if (pageType === "public") return page.access !== EPageAccess.PRIVATE;
    return true;
  });

  const tree = buildWikiTree(pages);

  const descendantIdsOf = useCallback(
    (ancestorId: string): Set<string> => {
      const childrenByParent = new Map<string, string[]>();
      pages.forEach((page) => {
        if (!page.id) return;
        const parentId = page.parent_id;
        if (!parentId) return;
        const bucket = childrenByParent.get(parentId) ?? [];
        bucket.push(page.id);
        childrenByParent.set(parentId, bucket);
      });
      const descendants = new Set<string>();
      const stack = [...(childrenByParent.get(ancestorId) ?? [])];
      while (stack.length) {
        const current = stack.pop();
        if (!current || descendants.has(current)) continue;
        descendants.add(current);
        stack.push(...(childrenByParent.get(current) ?? []));
      }
      return descendants;
    },
    [pages]
  );

  const canDropOn = useCallback(
    (targetId: string, sourceId: string) => targetId !== sourceId && !descendantIdsOf(sourceId).has(targetId),
    [descendantIdsOf]
  );

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

  const handleAddSubPage = useCallback(
    async (parentId: string) => {
      const newPage = await pageStore.createPage({ parent: parentId } as never);
      if (newPage?.id) {
        setExpandedIds((prev) => new Set(prev).add(parentId));
        router.push(defaultHref(newPage.id));
      }
    },
    [pageStore, defaultHref, router]
  );

  /**
   * Resolve the sort_order the dropped page should take to land before/after
   * the target sibling, or at the end of a new parent's children.
   */
  const resolveSortOrder = useCallback(
    (target: TWikiDragData, position: TDropPosition): number => {
      if (position === "inside") {
        const children = pages.filter((page) => page.parent_id === target.pageId);
        if (!children.length) return DEFAULT_SORT_ORDER;
        return Math.max(...children.map((child) => child.sort_order ?? DEFAULT_SORT_ORDER)) + 1;
      }
      const parentId = target.parentId ?? null;
      const siblings = pages
        .filter((page) => (page.parent_id ?? null) === parentId)
        .slice()
        // oxlint-disable-next-line unicorn/no-array-sort -- Array#toSorted is not in this project's TS lib target
        .sort(sortByOrderThenName);
      const targetIndex = siblings.findIndex((page) => page.id === target.pageId);
      if (targetIndex === -1) return DEFAULT_SORT_ORDER;
      const insertAt = position === "before" ? targetIndex : targetIndex + 1;
      const before = siblings[insertAt - 1]?.sort_order;
      const after = siblings[insertAt]?.sort_order;
      if (before !== undefined && after !== undefined && before !== after) return (before + after) / 2;
      if (before !== undefined) return before + 1;
      if (after !== undefined) return after - 1;
      return DEFAULT_SORT_ORDER;
    },
    [pages]
  );

  const handleMove = useCallback(
    async (source: TWikiDragData, target: TWikiDragData, position: TDropPosition) => {
      if (!source.pageId || !target.pageId) return;
      const newParentId = position === "inside" ? target.pageId : (target.parentId ?? null);
      const sortOrder = resolveSortOrder(target, position);
      try {
        await pageStore.movePage({ pageId: source.pageId, newParentId, sortOrder });
        if (position === "inside") {
          setExpandedIds((prev) => new Set(prev).add(target.pageId));
        }
      } catch (error) {
        const message = (error as { error?: string } | undefined)?.error;
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("wiki.errors.move_failed"),
          message: message ?? t("wiki.errors.move_failed_description"),
        });
      }
    },
    [pageStore, resolveSortOrder, t]
  );

  if (pages.length === 0) return null;

  return (
    <ul className="flex flex-col gap-0.5" data-testid="wiki-tree">
      {tree.map((node) => (
        <Fragment key={node.id}>
          <WikiTreeItem
            node={node}
            pageHref={defaultHref}
            expandedIds={expandedIds}
            toggleExpanded={toggleExpanded}
            onAddSubPage={handleAddSubPage}
            onMove={handleMove}
            canDropOn={canDropOn}
            showAddChild={!!canCreatePage}
          />
        </Fragment>
      ))}
    </ul>
  );
});
