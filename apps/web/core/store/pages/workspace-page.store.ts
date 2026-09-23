/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { unset, set } from "lodash-es";
import { makeObservable, observable, runInAction, action, reaction, computed } from "mobx";
import { computedFn } from "mobx-utils";
// types
import { EUserPermissions } from "@plane/constants";
import type { TPage, TPageFilters, TPageNavigationTabs } from "@plane/types";
// helpers
import { filterPagesByPageType, getPageName, orderPages, shouldFilterPage } from "@plane/utils";
// plane web constants
// plane web store
// services
import { WorkspacePageService } from "@/services/page";
// store
import type { CoreRootStore } from "../root.store";
import type { IBasePageStore } from "./base-page-store";
import type { TWorkspacePage } from "./workspace-page";
import { WorkspacePage } from "./workspace-page";

type TLoader = "init-loader" | "mutation-loader" | undefined;

type TError = { title: string; description: string };

const DEFAULT_PAGE_FILTERS: TPageFilters = {
  searchQuery: "",
  sortKey: "updated_at",
  sortBy: "desc",
};

export const WORKSPACE_WIKI_CREATE_PAGE_ROLES: EUserPermissions[] = [EUserPermissions.ADMIN, EUserPermissions.MEMBER];

/**
 * Scope contract: fetches implicitly activate their scope; a response whose
 * slug differs from the active scope is ignored.
 */
export interface IWorkspacePageStore extends IBasePageStore<TWorkspacePage> {
  // scope
  activeWorkspaceSlug: string | undefined;
  /** Switch the store to a workspace scope, clearing stale active data. */
  activateScope: (workspaceSlug: string) => void;
  // helper actions
  getCurrentWorkspacePageIdsByTab: (pageType: TPageNavigationTabs) => string[] | undefined;
  getCurrentWorkspaceFilteredPageIdsByTab: (pageType: TPageNavigationTabs) => string[] | undefined;
  /** Returns the parent chain of a Wiki page from root → immediate parent. */
  getPageParentChain: (pageId: string) => TWorkspacePage[];
  // actions
  fetchPagesList: (workspaceSlug: string, pageType?: TPageNavigationTabs) => Promise<TPage[] | undefined>;
  fetchPageDetails: (
    workspaceSlug: string,
    pageId: string,
    options?: { trackVisit?: boolean }
  ) => Promise<TPage | undefined>;
  /**
   * Move a Wiki page in the hierarchy. `newParentId === null` detaches the page
   * from its current parent. `sortOrder` optionally reorders it among its new
   * siblings. The update is optimistic on the local store, but the server is
   * the source of truth: any hierarchy violation rolls the UI back.
   */
  movePage: (params: { pageId: string; newParentId: string | null; sortOrder?: number }) => Promise<TPage | undefined>;
}

export class WorkspacePageStore implements IWorkspacePageStore {
  // observables
  loader: TLoader = "init-loader";
  data: Record<string, TWorkspacePage> = {}; // pageId => Page
  error: TError | undefined = undefined;
  filters: TPageFilters = { ...DEFAULT_PAGE_FILTERS };
  // active workspace scope
  activeWorkspaceSlug: string | undefined = undefined;
  // service
  service: WorkspacePageService;
  rootStore: CoreRootStore;

  constructor(private store: CoreRootStore) {
    makeObservable(this, {
      // observables
      loader: observable.ref,
      data: observable,
      error: observable,
      filters: observable,
      activeWorkspaceSlug: observable.ref,
      // computed
      isAnyPageAvailable: computed,
      canCurrentUserCreatePage: computed,
      // helper actions
      updateFilters: action,
      clearAllFilters: action,
      activateScope: action,
      // actions
      fetchPagesList: action,
      fetchPageDetails: action,
      createPage: action,
      removePage: action,
      movePage: action,
    });
    this.rootStore = store;
    // service
    this.service = new WorkspacePageService();
    // reset filters when the workspace slug changes
    reaction(
      () => this.store.router.workspaceSlug,
      () => {
        this.filters.searchQuery = "";
      }
    );
  }

  /**
   * @description check if any page is available
   */
  get isAnyPageAvailable() {
    if (this.loader) return true;
    return Object.keys(this.data).length > 0;
  }

  /**
   * @description returns true if the current logged in user can create a page
   */
  get canCurrentUserCreatePage() {
    const workspaceSlug = this.activeWorkspaceSlug ?? this.store.router.workspaceSlug;
    const workspaceRole = this.store.user.permission.getWorkspaceRoleByWorkspaceSlug(workspaceSlug?.toString() || "");
    if (!workspaceRole) return false;
    if (typeof workspaceRole === "number") {
      return WORKSPACE_WIKI_CREATE_PAGE_ROLES.includes(workspaceRole as EUserPermissions);
    }
    return false;
  }

  /**
   * @description get the current workspace page ids based on the pageType
   * @param {TPageNavigationTabs} pageType
   */
  getCurrentWorkspacePageIdsByTab = computedFn((pageType: TPageNavigationTabs) => {
    const pagesByType = filterPagesByPageType(pageType, Object.values(this?.data || {}));
    const pages = (pagesByType.map((page) => page.id) as string[]) || undefined;
    return pages ?? undefined;
  });

  /**
   * @description get the current workspace filtered page ids based on the pageType
   * @param {TPageNavigationTabs} pageType
   */
  getCurrentWorkspaceFilteredPageIdsByTab = computedFn((pageType: TPageNavigationTabs) => {
    const pagesByType = filterPagesByPageType(pageType, Object.values(this?.data || {}));
    let filteredPages = pagesByType.filter(
      (p) =>
        getPageName(p.name).toLowerCase().includes(this.filters.searchQuery.toLowerCase()) &&
        shouldFilterPage(p, this.filters.filters)
    );
    filteredPages = orderPages(filteredPages, this.filters.sortKey, this.filters.sortBy);

    const pages = (filteredPages.map((page) => page.id) as string[]) || undefined;
    return pages ?? undefined;
  });

  /**
   * @description get the page store by id
   * @param {string} pageId
   */
  getPageById = computedFn((pageId: string) => this.data?.[pageId] || undefined);

  /**
   * @description walk the parent chain of a Wiki page from root to immediate parent.
   * Malformed cycles are detected with a visited set and broken by ignoring the
   * offending link — this matches the server-side hierarchy guard so the UI
   * never renders a corrupt breadcrumb.
   */
  getPageParentChain = computedFn((pageId: string): TWorkspacePage[] => {
    const chain: TWorkspacePage[] = [];
    const seen = new Set<string>();
    let cursor = this.getPageById(pageId);
    while (cursor?.parent_id) {
      if (seen.has(cursor.parent_id)) break;
      seen.add(cursor.parent_id);
      const parent = this.getPageById(cursor.parent_id);
      if (!parent) break;
      chain.unshift(parent);
      cursor = parent;
    }
    return chain;
  });

  updateFilters = <T extends keyof TPageFilters>(filterKey: T, filterValue: TPageFilters[T]) => {
    runInAction(() => {
      set(this.filters, [filterKey], filterValue);
    });
  };

  /**
   * @description clear all the filters
   */
  clearAllFilters = () =>
    runInAction(() => {
      set(this.filters, ["filters"], {});
    });

  /**
   * @description switch the store to a workspace scope: stale data, filters,
   * loader and error are cleared and the active slug recorded atomically
   * before the caller fetches the new scope
   */
  activateScope = (workspaceSlug: string) => {
    runInAction(() => {
      this.data = {};
      this.filters = { ...DEFAULT_PAGE_FILTERS };
      this.activeWorkspaceSlug = workspaceSlug;
      this.loader = undefined;
      this.error = undefined;
    });
  };

  /**
   * @description fetch all the pages
   */
  fetchPagesList = async (workspaceSlug: string, pageType?: TPageNavigationTabs) => {
    try {
      if (!workspaceSlug) return undefined;
      // fetches implicitly activate their scope; a same-scope refetch keeps
      // the displayed data and the user's filters
      if (this.activeWorkspaceSlug !== workspaceSlug) this.activateScope(workspaceSlug);

      const currentPageIds = pageType ? this.getCurrentWorkspacePageIdsByTab(pageType) : undefined;
      runInAction(() => {
        this.loader = currentPageIds && currentPageIds.length > 0 ? `mutation-loader` : `init-loader`;
        this.error = undefined;
      });

      const pages = await this.service.fetchAll(workspaceSlug);
      // ignore a late response for a scope that is no longer active
      if (this.activeWorkspaceSlug && this.activeWorkspaceSlug !== workspaceSlug) return undefined;
      runInAction(() => {
        for (const page of pages) {
          if (page?.id) {
            const existingPage = this.getPageById(page.id);
            if (existingPage) {
              const { name, ...otherFields } = page;
              existingPage.mutateProperties(otherFields, false);
            } else {
              set(this.data, [page.id], new WorkspacePage(this.store, page, workspaceSlug));
            }
          }
        }
        this.loader = undefined;
      });

      return pages;
    } catch (error) {
      // ignore a late failure for a scope that is no longer active
      if (this.activeWorkspaceSlug && this.activeWorkspaceSlug !== workspaceSlug) throw error;
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to fetch the pages, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description fetch the details of a page
   * @param {string} pageId
   */
  fetchPageDetails = async (...args: Parameters<IWorkspacePageStore["fetchPageDetails"]>) => {
    const [workspaceSlug, pageId, options] = args;
    const { trackVisit } = options || {};
    try {
      if (!workspaceSlug || !pageId) return undefined;
      // fetches implicitly activate their scope; a same-scope refetch keeps
      // the displayed data and the user's filters
      if (this.activeWorkspaceSlug !== workspaceSlug) this.activateScope(workspaceSlug);

      const currentPageId = this.getPageById(pageId);
      runInAction(() => {
        this.loader = currentPageId ? `mutation-loader` : `init-loader`;
        this.error = undefined;
      });

      const page = await this.service.fetchById(workspaceSlug, pageId, trackVisit ?? true);
      // ignore a late response for a scope that is no longer active
      if (this.activeWorkspaceSlug && this.activeWorkspaceSlug !== workspaceSlug) return undefined;

      runInAction(() => {
        if (page?.id) {
          const pageInstance = this.getPageById(page.id);
          if (pageInstance) {
            pageInstance.mutateProperties(page, false);
          } else {
            set(this.data, [page.id], new WorkspacePage(this.store, page, workspaceSlug));
          }
        }
        this.loader = undefined;
      });

      return page;
    } catch (error) {
      // ignore a late failure for a scope that is no longer active
      if (this.activeWorkspaceSlug && this.activeWorkspaceSlug !== workspaceSlug) throw error;
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to fetch the page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description create a page
   * @param {Partial<TPage>} pageData
   */
  createPage = async (pageData: Partial<TPage>) => {
    try {
      const workspaceSlug = this.activeWorkspaceSlug ?? this.store.router.workspaceSlug;
      if (!workspaceSlug) return undefined;

      runInAction(() => {
        this.loader = "mutation-loader";
        this.error = undefined;
      });

      const page = await this.service.create(workspaceSlug, pageData);
      runInAction(() => {
        if (page?.id) set(this.data, [page.id], new WorkspacePage(this.store, page, workspaceSlug));
        this.loader = undefined;
      });

      return page;
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to create a page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description delete a page
   * @param {string} pageId
   */
  removePage = async ({ pageId, shouldSync: _shouldSync = true }: { pageId: string; shouldSync?: boolean }) => {
    try {
      // entity mutations target the page's immutable source workspace, never
      // the mutable active/router scope
      const workspaceSlug = this.data?.[pageId]?.sourceWorkspaceSlug;
      if (!workspaceSlug || !pageId) return undefined;

      await this.service.remove(workspaceSlug, pageId);
      runInAction(() => {
        unset(this.data, [pageId]);
        if (this.rootStore.favorite.entityMap[pageId]) this.rootStore.favorite.removeFavoriteFromStore(pageId);
      });
    } catch (error) {
      runInAction(() => {
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to delete a page, Please try again later.",
        };
      });
      throw error;
    }
  };

  /**
   * @description Reparent a Wiki page (WIKI-04a §7.2).
   *
   * The new parent id is applied optimistically to the in-memory page so the
   * tree view can re-render before the round-trip completes. The server is
   * authoritative: any hierarchy violation surfaces here and we roll the
   * local store back to its previous `parent_id`.
   */
  movePage = async (params: {
    pageId: string;
    newParentId: string | null;
    sortOrder?: number;
  }): Promise<TPage | undefined> => {
    const { pageId, newParentId, sortOrder } = params;
    const page = this.data?.[pageId];
    if (!page) return undefined;
    // entity mutations target the page's immutable source workspace, never
    // the mutable active/router scope
    const workspaceSlug = page.sourceWorkspaceSlug;
    const previousParentId = page.parent_id ?? null;
    const previousSortOrder = page.sort_order;

    runInAction(() => {
      page.parent_id = newParentId;
      if (sortOrder !== undefined) page.sort_order = sortOrder;
      this.loader = "mutation-loader";
    });

    try {
      const updated = await this.service.move(workspaceSlug, pageId, {
        parent: newParentId,
        ...(sortOrder !== undefined ? { sort_order: sortOrder } : {}),
      });
      runInAction(() => {
        if (updated) page.mutateProperties(updated, false);
        this.loader = undefined;
      });
      return updated;
    } catch (error) {
      runInAction(() => {
        // server rejected the move; restore prior position and order
        page.parent_id = previousParentId;
        page.sort_order = previousSortOrder;
        this.loader = undefined;
        this.error = {
          title: "Failed",
          description: "Failed to move the page, Please try again later.",
        };
      });
      throw error;
    }
  };
}
