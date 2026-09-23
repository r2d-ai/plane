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
import { IMediaEmbedAttributeNames, DEFAULT_MEDIA_EMBED_ATTRIBUTES } from "./types";
import type { TMediaEmbedAttributes } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.MEDIA_EMBED]: {
      insertMediaEmbed: (attrs: { src: string; mediaType?: "image" | "video" }) => ReturnType;
    };
  }
}

export const CustomMediaEmbedExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.MEDIA_EMBED,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      [IMediaEmbedAttributeNames.ID]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.ID],
      },
      [IMediaEmbedAttributeNames.SRC]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.SRC],
      },
      [IMediaEmbedAttributeNames.MEDIA_TYPE]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.MEDIA_TYPE],
      },
      [IMediaEmbedAttributeNames.ALT]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.ALT],
      },
      [IMediaEmbedAttributeNames.CAPTION]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.CAPTION],
      },
      [IMediaEmbedAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.BLOCK_TYPE],
      },
    };
  },

  addStorage() {
    return {
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TMediaEmbedAttributes;
          const src = attrs[IMediaEmbedAttributeNames.SRC] || "";
          const mediaType = attrs[IMediaEmbedAttributeNames.MEDIA_TYPE] || "image";
          if (mediaType === "video") {
            state.write(`[Video](${src})\n`);
          } else {
            state.write(`![${attrs[IMediaEmbedAttributeNames.ALT] || ""}](${src})`);
          }
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `div[data-block-type="${DEFAULT_MEDIA_EMBED_ATTRIBUTES[IMediaEmbedAttributeNames.BLOCK_TYPE]}"]`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes)];
  },
});
