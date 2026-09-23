/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum IDrawIOAttributeNames {
  ID = "id",
  XML = "data-xml",
  BLOCK_TYPE = "data-block-type",
}

export type TDrawIOBlockAttributes = {
  [IDrawIOAttributeNames.ID]: string | null;
  [IDrawIOAttributeNames.XML]: string;
  [IDrawIOAttributeNames.BLOCK_TYPE]: "drawio-component";
};

export const DEFAULT_DRAWIO_ATTRIBUTES: TDrawIOBlockAttributes = {
  [IDrawIOAttributeNames.ID]: null,
  [IDrawIOAttributeNames.XML]: "",
  [IDrawIOAttributeNames.BLOCK_TYPE]: "drawio-component",
};
