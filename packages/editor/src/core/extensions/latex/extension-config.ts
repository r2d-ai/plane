/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Node, mergeAttributes } from "@tiptap/core";
import type { MarkdownSerializerState } from "@tiptap/pm/markdown";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// types
import { ILaTeXAttributeNames, DEFAULT_LATEX_ATTRIBUTES } from "./types";
import type { TLaTeXBlockAttributes } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.LATEX]: {
      insertLaTeX: () => ReturnType;
    };
  }
}

export const CustomLaTeXExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.LATEX,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      [ILaTeXAttributeNames.ID]: {
        default: DEFAULT_LATEX_ATTRIBUTES[ILaTeXAttributeNames.ID],
      },
      [ILaTeXAttributeNames.CODE]: {
        default: DEFAULT_LATEX_ATTRIBUTES[ILaTeXAttributeNames.CODE],
      },
      [ILaTeXAttributeNames.DISPLAY_MODE]: {
        default: DEFAULT_LATEX_ATTRIBUTES[ILaTeXAttributeNames.DISPLAY_MODE],
      },
      [ILaTeXAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_LATEX_ATTRIBUTES[ILaTeXAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TLaTeXBlockAttributes;
          const code = attrs[ILaTeXAttributeNames.CODE] || "";
          state.write(`$$\n${code}\n$$\n`);
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_LATEX_ATTRIBUTES[ILaTeXAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes)];
  },
});
