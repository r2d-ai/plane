/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/** Collection access level (spec §5.5). */
export enum EPageCollectionAccess {
  PUBLIC = 0,
  PRIVATE = 1,
}

/** Collection member role (spec §5.5). */
export enum EPageCollectionRole {
  VIEW = 10,
  COMMENT = 20,
  EDIT = 30,
}

/** A workspace-level Wiki collection (spec §5.5, backend PageCollection). */
export type TPageCollection = {
  id: string;
  workspace: string;
  name: string;
  description: string;
  logo_props: Record<string, unknown> | null;
  access: EPageCollectionAccess;
  sort_order: number;
  is_default: boolean;
  member_count: number;
  page_count: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
};

/** A collection member with resolved user details. */
export type TPageCollectionMember = {
  id: string;
  collection: string;
  member: string;
  member_detail: {
    id: string;
    email: string;
    display_name: string;
    avatar_url: string | null;
  };
  role: EPageCollectionRole;
  workspace: string;
  created_at: string;
  updated_at: string;
};

/** A page-to-collection association with sort order. */
export type TPageCollectionPage = {
  id: string;
  collection: string;
  page: string;
  page_detail: {
    id: string;
    name: string;
    access: number;
    parent: string | null;
    sort_order: number;
  };
  workspace: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

/** Payload for creating a collection. */
export type TPageCollectionCreatePayload = {
  name: string;
  description?: string;
  access?: EPageCollectionAccess;
  logo_props?: Record<string, unknown> | null;
};

/** Payload for updating a collection. */
export type TPageCollectionUpdatePayload = Partial<
  Pick<TPageCollectionCreatePayload, "name" | "description" | "access" | "logo_props">
>;

/** Payload for adding/updating a collection member. */
export type TPageCollectionMemberPayload = {
  member: string;
  role: EPageCollectionRole;
};

/** Payload for reordering collections. */
export type TPageCollectionReorderPayload = {
  collections: { id: string; sort_order: number }[];
};

/** Payload for reordering pages within a collection. */
export type TPageCollectionPageReorderPayload = {
  pages: { page: string; sort_order: number }[];
};
