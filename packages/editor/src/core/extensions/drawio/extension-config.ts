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
import { IDrawIOAttributeNames, DEFAULT_DRAWIO_ATTRIBUTES } from "./types";
import type { TDrawIOBlockAttributes } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.DRAWIO]: {
      insertDrawIO: () => ReturnType;
    };
  }
}

/**
 * Draw.io integration extension.
 *
 * This extension provides a placeholder node for Draw.io diagrams.
 * Full Draw.io integration requires external marketplace/app plumbing
 * (e.g., draw.io web plugin or hosted instance). This extension does not
 * block editor parity core — it establishes the integration path for
 * future development.
 */
export const CustomDrawIOExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.DRAWIO,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      [IDrawIOAttributeNames.ID]: {
        default: DEFAULT_DRAWIO_ATTRIBUTES[IDrawIOAttributeNames.ID],
      },
      [IDrawIOAttributeNames.XML]: {
        default: DEFAULT_DRAWIO_ATTRIBUTES[IDrawIOAttributeNames.XML],
      },
      [IDrawIOAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_DRAWIO_ATTRIBUTES[IDrawIOAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TDrawIOBlockAttributes;
          const xml = attrs[IDrawIOAttributeNames.XML] || "";
          if (xml) {
            state.write("```drawio\n");
            state.write(xml);
            state.write("\n```\n");
          } else {
            state.write("[Draw.io Diagram]\n");
          }
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_DRAWIO_ATTRIBUTES[IDrawIOAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes)];
  },
});
