/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// local imports
import { MediaEmbedBlock } from "./block";
import type { MediaEmbedNodeViewProps } from "./block";
import { CustomMediaEmbedExtensionConfig } from "./extension-config";
import { generateMediaEmbedBlockId } from "./utils";

export const CustomMediaEmbedExtension = CustomMediaEmbedExtensionConfig.extend({
  addCommands() {
    return {
      insertMediaEmbed:
        (attrs: { src: string; mediaType?: "image" | "video" }) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              id: generateMediaEmbedBlockId(),
              src: attrs.src,
              mediaType: attrs.mediaType ?? "image",
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <MediaEmbedBlock {...props} node={props.node as MediaEmbedNodeViewProps["node"]} />
    ));
  },
});
