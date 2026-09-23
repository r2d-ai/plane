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
import { IMermaidAttributeNames, DEFAULT_MERMAID_ATTRIBUTES } from "./types";
import type { TMermaidBlockAttributes } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.MERMAID]: {
      insertMermaid: () => ReturnType;
    };
  }
}

export const CustomMermaidExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.MERMAID,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      [IMermaidAttributeNames.ID]: {
        default: DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.ID],
      },
      [IMermaidAttributeNames.CODE]: {
        default: DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.CODE],
      },
      [IMermaidAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TMermaidBlockAttributes;
          const code = attrs[IMermaidAttributeNames.CODE] || "";
          state.write("```mermaid\n");
          state.write(code);
          state.write("\n```\n");
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes)];
  },
});
