/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Node, mergeAttributes } from "@tiptap/core";
import type { MarkdownSerializerState } from "@tiptap/pm/markdown";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
// types
import { CORE_EXTENSIONS } from "@/constants/extension";
// types
import { IToggleBlockAttributeNames, DEFAULT_TOGGLE_BLOCK_ATTRIBUTES } from "./types";
import type { TToggleBlockAttributes } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.TOGGLE_BLOCK]: {
      insertToggleBlock: () => ReturnType;
    };
  }
}

export const CustomToggleBlockExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.TOGGLE_BLOCK,
  group: "block",
  content: "block+",

  addAttributes() {
    return {
      [IToggleBlockAttributeNames.ID]: {
        default: DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.ID],
      },
      [IToggleBlockAttributeNames.OPEN]: {
        default: DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.OPEN],
        parseHTML: (element) => element.getAttribute(IToggleBlockAttributeNames.OPEN) !== "false",
        renderHTML: (attributes) => ({
          [IToggleBlockAttributeNames.OPEN]: attributes[IToggleBlockAttributeNames.OPEN] ? "true" : "false",
        }),
      },
      [IToggleBlockAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TToggleBlockAttributes;
          const open = attrs[IToggleBlockAttributeNames.OPEN];
          state.write(`<details${open ? "" : " open"}>\n`);
          state.write("<summary>Toggle</summary>\n\n");
          state.renderContent(node);
          state.write("\n</details>\n");
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes), 0];
  },
});
