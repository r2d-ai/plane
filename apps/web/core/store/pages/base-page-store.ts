/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPage, TPageFilters, TPageNavigationTabs } from "@plane/types";

/**
 * Shared surface across Project Page and Workspace Wiki page stores.
 * Both `IProjectPageStore` and `IWorkspacePageStore` extend this so that
 * components dispatching on `EPageStoreType` can call the common methods
 * (data, loader, filters, canCurrentUserCreatePage, getPageById,
 * createPage, removePage, etc.) without having to discriminate the union.
 *
 * Scoped actions (`fetchPageDetails` with the per-scope arg shape,
 * project id filtering, workspace wiki tabs) are still defined on the
 * per-scope interface so the type system can validate the right arity.
 */
export interface IBasePageStore<TInstance> {
  // observables
  loader: "init-loader" | "mutation-loader" | undefined;
  data: Record<string, TInstance>;
  error: { title: string; description: string } | undefined;
  filters: TPageFilters;
  // computed
  isAnyPageAvailable: boolean;
  canCurrentUserCreatePage: boolean;
  // helper actions
  getPageById: (pageId: string) => TInstance | undefined;
  updateFilters: <K extends keyof TPageFilters>(filterKey: K, filterValue: TPageFilters[K]) => void;
  clearAllFilters: () => void;
  // actions
  createPage: (pageData: Partial<TPage>) => Promise<TPage | undefined>;
  removePage: (params: { pageId: string; shouldSync?: boolean }) => Promise<void>;
}

/**
 * Shared workspace page type alias so consumers can refer to the common
 * shape without importing either store.
 */
export type TAnyPage = TPage;

/**
 * Common navigation tab keys; both stores consume the same `TPageNavigationTabs`.
 */
export type TAnyPageNavigationTabs = TPageNavigationTabs;
