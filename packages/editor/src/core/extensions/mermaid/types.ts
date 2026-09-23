/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export enum IMermaidAttributeNames {
  ID = "id",
  CODE = "data-code",
  BLOCK_TYPE = "data-block-type",
}

export type TMermaidBlockAttributes = {
  [IMermaidAttributeNames.ID]: string | null;
  [IMermaidAttributeNames.CODE]: string;
  [IMermaidAttributeNames.BLOCK_TYPE]: "mermaid-component";
};

export const DEFAULT_MERMAID_ATTRIBUTES: TMermaidBlockAttributes = {
  [IMermaidAttributeNames.ID]: null,
  [IMermaidAttributeNames.CODE]: "graph TD\n    A[Start] --> B[End]",
  [IMermaidAttributeNames.BLOCK_TYPE]: "mermaid-component",
};
