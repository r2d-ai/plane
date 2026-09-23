/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum ITabsBlockAttributeNames {
  ID = "id",
  ORIENTATION = "data-orientation",
  ACTIVE_TAB = "data-active-tab",
  BLOCK_TYPE = "data-block-type",
}

export type TTabsBlockAttributes = {
  [ITabsBlockAttributeNames.ID]: string | null;
  [ITabsBlockAttributeNames.ORIENTATION]: "horizontal" | "vertical";
  [ITabsBlockAttributeNames.ACTIVE_TAB]: number;
  [ITabsBlockAttributeNames.BLOCK_TYPE]: "tabs-block-component";
};

export const DEFAULT_TABS_BLOCK_ATTRIBUTES: TTabsBlockAttributes = {
  [ITabsBlockAttributeNames.ID]: null,
  [ITabsBlockAttributeNames.ORIENTATION]: "horizontal",
  [ITabsBlockAttributeNames.ACTIVE_TAB]: 0,
  [ITabsBlockAttributeNames.BLOCK_TYPE]: "tabs-block-component",
};

export enum ITabItemAttributeNames {
  LABEL = "data-tab-label",
}

export type TTabItemAttributes = {
  [ITabItemAttributeNames.LABEL]: string;
};

export const DEFAULT_TAB_ITEM_ATTRIBUTES: TTabItemAttributes = {
  [ITabItemAttributeNames.LABEL]: "Tab",
};
