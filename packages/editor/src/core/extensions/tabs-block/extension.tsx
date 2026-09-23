/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// local imports
import { CustomTabsBlock } from "./block";
import type { CustomTabsBlockNodeViewProps } from "./block";
import { CustomTabsBlockExtensionConfig } from "./extension-config";
import { TabItemExtensionConfig } from "./tab-item-config";
import { generateTabsBlockId } from "./utils";

export const CustomTabsBlockExtension = CustomTabsBlockExtensionConfig.extend({
  selectable: true,
  draggable: true,

  addCommands() {
    return {
      insertTabsBlock:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            content: [
              {
                type: "tabItem",
                attrs: { "data-tab-label": "Tab 1" },
                content: [{ type: CORE_EXTENSIONS.PARAGRAPH }],
              },
              {
                type: "tabItem",
                attrs: { "data-tab-label": "Tab 2" },
                content: [{ type: CORE_EXTENSIONS.PARAGRAPH }],
              },
            ],
            attrs: {
              id: generateTabsBlockId(),
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <CustomTabsBlock {...props} node={props.node as CustomTabsBlockNodeViewProps["node"]} />
    ));
  },
});

export { TabItemExtensionConfig };
