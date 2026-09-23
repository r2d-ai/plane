/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { findParentNodeClosestToPos, ReactNodeViewRenderer } from "@tiptap/react";
import type { Predicate } from "@tiptap/react";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// local imports
import { CustomToggleBlock } from "./block";
import type { CustomToggleBlockNodeViewProps } from "./block";
import { CustomToggleBlockExtensionConfig } from "./extension-config";
import { generateToggleBlockId } from "./utils";

export const CustomToggleBlockExtension = CustomToggleBlockExtensionConfig.extend({
  selectable: true,
  draggable: true,

  addCommands() {
    return {
      insertToggleBlock:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            content: [
              {
                type: CORE_EXTENSIONS.PARAGRAPH,
              },
            ],
            attrs: {
              id: generateToggleBlockId(),
            },
          }),
    };
  },

  addKeyboardShortcuts() {
    return {
      Backspace: ({ editor }) => {
        const { $from, empty } = editor.state.selection;
        try {
          const isParentNodeToggle: Predicate = (node) => node.type === this.type;
          const parentNodeDetails = findParentNodeClosestToPos($from, isParentNodeToggle);
          if (empty && parentNodeDetails) {
            const isCursorAtToggleBeginning = $from.pos === parentNodeDetails.start + 1;
            if (parentNodeDetails.node.content.size > 2 && isCursorAtToggleBeginning) {
              editor.commands.setTextSelection(parentNodeDetails.pos - 1);
              return true;
            }
          }
        } catch (error) {
          console.error("Error in performing backspace action on toggle block", error);
        }
        return false;
      },
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <CustomToggleBlock {...props} node={props.node as CustomToggleBlockNodeViewProps["node"]} />
    ));
  },
});
