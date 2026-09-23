/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum ILaTeXAttributeNames {
  ID = "id",
  CODE = "data-code",
  DISPLAY_MODE = "display-mode",
  BLOCK_TYPE = "data-block-type",
}

export type TLaTeXBlockAttributes = {
  [ILaTeXAttributeNames.ID]: string | null;
  [ILaTeXAttributeNames.CODE]: string;
  [ILaTeXAttributeNames.DISPLAY_MODE]: boolean;
  [ILaTeXAttributeNames.BLOCK_TYPE]: "latex-component";
};

export const DEFAULT_LATEX_ATTRIBUTES: TLaTeXBlockAttributes = {
  [ILaTeXAttributeNames.ID]: null,
  [ILaTeXAttributeNames.CODE]: "E = mc^2",
  [ILaTeXAttributeNames.DISPLAY_MODE]: true,
  [ILaTeXAttributeNames.BLOCK_TYPE]: "latex-component",
};
