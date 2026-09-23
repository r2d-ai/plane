/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Node, mergeAttributes } from "@tiptap/core";
// types
import { ITabItemAttributeNames, DEFAULT_TAB_ITEM_ATTRIBUTES } from "./types";

export const TabItemExtensionConfig = Node.create({
  name: "tabItem",
  group: "block",
  content: "block+",

  addAttributes() {
    return {
      [ITabItemAttributeNames.LABEL]: {
        default: DEFAULT_TAB_ITEM_ATTRIBUTES[ITabItemAttributeNames.LABEL],
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'div[data-block-type="tab-item"]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-block-type": "tab-item" }), 0];
  },
});
