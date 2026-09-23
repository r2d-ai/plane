/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// local imports
import { CustomMermaidBlock } from "./block";
import type { CustomMermaidNodeViewProps } from "./block";
import { CustomMermaidExtensionConfig } from "./extension-config";
import { generateMermaidBlockId } from "./utils";

export const CustomMermaidExtension = CustomMermaidExtensionConfig.extend({
  addCommands() {
    return {
      insertMermaid:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              id: generateMermaidBlockId(),
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <CustomMermaidBlock {...props} node={props.node as CustomMermaidNodeViewProps["node"]} />
    ));
  },
});
