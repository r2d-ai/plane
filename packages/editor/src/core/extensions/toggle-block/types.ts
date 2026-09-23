/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum IToggleBlockAttributeNames {
  ID = "id",
  OPEN = "data-open",
  BLOCK_TYPE = "data-block-type",
}

export type TToggleBlockAttributes = {
  [IToggleBlockAttributeNames.ID]: string | null;
  [IToggleBlockAttributeNames.OPEN]: boolean;
  [IToggleBlockAttributeNames.BLOCK_TYPE]: "toggle-block-component";
};

export const DEFAULT_TOGGLE_BLOCK_ATTRIBUTES: TToggleBlockAttributes = {
  [IToggleBlockAttributeNames.ID]: null,
  [IToggleBlockAttributeNames.OPEN]: true,
  [IToggleBlockAttributeNames.BLOCK_TYPE]: "toggle-block-component",
};
