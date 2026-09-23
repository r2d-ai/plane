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
import { ITabsBlockAttributeNames, DEFAULT_TABS_BLOCK_ATTRIBUTES } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.TABS_BLOCK]: {
      insertTabsBlock: () => ReturnType;
    };
  }
}

export const CustomTabsBlockExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.TABS_BLOCK,
  group: "block",
  content: "tabItem+",

  addAttributes() {
    return {
      [ITabsBlockAttributeNames.ID]: {
        default: DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ID],
      },
      [ITabsBlockAttributeNames.ORIENTATION]: {
        default: DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ORIENTATION],
      },
      [ITabsBlockAttributeNames.ACTIVE_TAB]: {
        default: DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ACTIVE_TAB],
      },
      [ITabsBlockAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          state.write(":::tabs\n");
          node.forEach((child) => {
            const label = child.attrs["data-tab-label"] || "Tab";
            state.write(`:::tab[${label}]\n`);
            state.renderContent(child);
            state.write("\n:::\n");
          });
          state.write(":::\n");
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-block-type": "tabs-block-component" }), 0];
  },
});
