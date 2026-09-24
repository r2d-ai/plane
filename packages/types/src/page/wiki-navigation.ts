/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "../common";
import type { TPageCollection, TPageCollectionPage } from "./collection";
import type { TPage } from "./core";

export type TWikiScope = {
  id: string;
  slug: string;
  name: string;
  is_default: boolean;
  is_member: boolean;
  can_create: boolean;
  can_manage_collections: boolean;
};

export type TWikiSearchResult = {
  page_id: string;
  page_name: string;
  workspace_slug: string;
  workspace_name: string;
  logo_props: TLogoProps | null;
  matched_content_summary: string;
};

export type TWikiSearchResponse = { results: TWikiSearchResult[] };

export type TWikiPersonalSection = "favorites" | "owned" | "shared";
export type TWikiPersonalPage = Pick<
  TWikiSearchResult,
  "page_id" | "page_name" | "workspace_slug" | "workspace_name" | "logo_props"
>;
export type TWikiPersonalPageResponse = { results: TWikiPersonalPage[]; next_cursor: string | null };

export type TWikiNavigationScopeState = {
  pagesById: Record<string, TPage>;
  pageIds: string[];
  collectionsById: Record<string, TPageCollection>;
  collectionIds: string[];
  collectionPagesById: Record<string, TPageCollectionPage[]>;
  status: "idle" | "loading" | "loaded" | "error";
  error: string | null;
};
