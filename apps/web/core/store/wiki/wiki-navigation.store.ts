/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { makeObservable, observable, runInAction } from "mobx";
// types
import type { TPage, TPageCollection, TPageCollectionPage, TWikiNavigationScopeState } from "@plane/types";
// services
import { WorkspacePageCollectionService, WorkspacePageService } from "@/services/page";

/**
 * Narrow service contracts the navigation store depends on. The real
 * workspace page and collection services satisfy them structurally, so tests
 * can inject plain-object fakes instead.
 */
export type TWikiNavigationServices = {
  pageService: {
    fetchAll: (workspaceSlug: string) => Promise<TPage[]>;
  };
  collectionService: {
    fetchAll: (workspaceSlug: string) => Promise<TPageCollection[]>;
    fetchPages: (workspaceSlug: string, collectionId: string) => Promise<TPageCollectionPage[]>;
  };
};

export interface IWikiNavigationStore {
  scopes: Record<string, TWikiNavigationScopeState>;
  getScope: (workspaceSlug: string) => TWikiNavigationScopeState;
  fetchScope: (workspaceSlug: string) => Promise<TWikiNavigationScopeState>;
  fetchCollectionPages: (workspaceSlug: string, collectionId: string) => Promise<TPageCollectionPage[]>;
}

const createEmptyScope = (): TWikiNavigationScopeState => ({
  pagesById: {},
  pageIds: [],
  collectionsById: {},
  collectionIds: [],
  collectionPagesById: {},
  status: "idle",
  error: null,
});

/**
 * Wiki navigation state partitioned per workspace scope: each scope keeps its
 * own page and collection tree, so loading one workspace can never clobber
 * or leak into another.
 */
export class WikiNavigationStore implements IWikiNavigationStore {
  scopes: Record<string, TWikiNavigationScopeState> = {};
  services: TWikiNavigationServices;

  constructor(services?: TWikiNavigationServices) {
    makeObservable(this, { scopes: observable });
    this.services = {
      pageService: services?.pageService ?? new WorkspacePageService(),
      collectionService: services?.collectionService ?? new WorkspacePageCollectionService(),
    };
  }

  getScope = (workspaceSlug: string): TWikiNavigationScopeState => this.scopes[workspaceSlug] ?? createEmptyScope();

  /**
   * Load the page and collection lists for one workspace scope. A scope that
   * is already `loaded` is served from cache; a failure marks only the
   * requested scope and leaves the other scopes untouched.
   */
  fetchScope = async (workspaceSlug: string): Promise<TWikiNavigationScopeState> => {
    const cached = this.scopes[workspaceSlug];
    if (cached?.status === "loaded") return cached;

    runInAction(() => {
      const scope = this.scopes[workspaceSlug] ?? createEmptyScope();
      this.scopes[workspaceSlug] = { ...scope, status: "loading", error: null };
    });

    try {
      const [pages, collections] = await Promise.all([
        this.services.pageService.fetchAll(workspaceSlug),
        this.services.collectionService.fetchAll(workspaceSlug),
      ]);
      return runInAction(() => {
        const scope = this.scopes[workspaceSlug] ?? createEmptyScope();
        const pagesById: Record<string, TPage> = {};
        const pageIds: string[] = [];
        for (const page of pages) {
          if (page?.id) {
            pagesById[page.id] = page;
            pageIds.push(page.id);
          }
        }
        const collectionsById: Record<string, TPageCollection> = {};
        const collectionIds: string[] = [];
        for (const collection of collections) {
          collectionsById[collection.id] = collection;
          collectionIds.push(collection.id);
        }
        const loaded: TWikiNavigationScopeState = {
          ...scope,
          pagesById,
          pageIds,
          collectionsById,
          collectionIds,
          status: "loaded",
          error: null,
        };
        this.scopes[workspaceSlug] = loaded;
        return loaded;
      });
    } catch (error) {
      runInAction(() => {
        const scope = this.scopes[workspaceSlug] ?? createEmptyScope();
        this.scopes[workspaceSlug] = {
          ...scope,
          status: "error",
          error: error instanceof Error ? error.message : "Failed to load the Wiki navigation",
        };
      });
      throw error;
    }
  };

  /**
   * Load the pages of one collection, updating only
   * `scopes[workspaceSlug].collectionPagesById[collectionId]`.
   */
  fetchCollectionPages = async (workspaceSlug: string, collectionId: string): Promise<TPageCollectionPage[]> => {
    const pages = await this.services.collectionService.fetchPages(workspaceSlug, collectionId);
    runInAction(() => {
      const scope = this.scopes[workspaceSlug] ?? createEmptyScope();
      this.scopes[workspaceSlug] = {
        ...scope,
        collectionPagesById: { ...scope.collectionPagesById, [collectionId]: pages },
      };
    });
    return pages;
  };
}
