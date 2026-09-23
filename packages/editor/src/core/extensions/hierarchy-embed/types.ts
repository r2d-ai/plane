/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum IHierarchyEmbedAttributeNames {
  ID = "id",
  PAGE_ID = "data-page-id",
  WORKSPACE_SLUG = "data-workspace-slug",
  PROJECT_ID = "data-project-id",
  DEPTH = "data-depth",
  VIEW_MODE = "data-view-mode",
  GROUP_BY_CREATOR = "data-group-by-creator",
  BLOCK_TYPE = "data-block-type",
}

export type THierarchyEmbedAttributes = {
  [IHierarchyEmbedAttributeNames.ID]: string | null;
  [IHierarchyEmbedAttributeNames.PAGE_ID]: string | undefined;
  [IHierarchyEmbedAttributeNames.WORKSPACE_SLUG]: string | undefined;
  [IHierarchyEmbedAttributeNames.PROJECT_ID]: string | undefined;
  [IHierarchyEmbedAttributeNames.DEPTH]: number;
  [IHierarchyEmbedAttributeNames.VIEW_MODE]: "children" | "parent" | "flat";
  [IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR]: boolean;
  [IHierarchyEmbedAttributeNames.BLOCK_TYPE]: "hierarchy-embed-component";
};

export const DEFAULT_HIERARCHY_EMBED_ATTRIBUTES: THierarchyEmbedAttributes = {
  [IHierarchyEmbedAttributeNames.ID]: null,
  [IHierarchyEmbedAttributeNames.PAGE_ID]: undefined,
  [IHierarchyEmbedAttributeNames.WORKSPACE_SLUG]: undefined,
  [IHierarchyEmbedAttributeNames.PROJECT_ID]: undefined,
  [IHierarchyEmbedAttributeNames.DEPTH]: 2,
  [IHierarchyEmbedAttributeNames.VIEW_MODE]: "children",
  [IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR]: false,
  [IHierarchyEmbedAttributeNames.BLOCK_TYPE]: "hierarchy-embed-component",
};
