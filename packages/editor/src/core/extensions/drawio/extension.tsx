/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// local imports
import { DrawIOBlock } from "./block";
import type { DrawIONodeViewProps } from "./block";
import { CustomDrawIOExtensionConfig } from "./extension-config";
import { generateDrawIOBlockId } from "./utils";

export const CustomDrawIOExtension = CustomDrawIOExtensionConfig.extend({
  addCommands() {
    return {
      insertDrawIO:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              id: generateDrawIOBlockId(),
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <DrawIOBlock {...props} node={props.node as DrawIONodeViewProps["node"]} />
    ));
  },
});
