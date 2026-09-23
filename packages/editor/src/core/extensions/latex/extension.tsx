/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// local imports
import { LaTeXBlock } from "./block";
import type { LaTeXNodeViewProps } from "./block";
import { CustomLaTeXExtensionConfig } from "./extension-config";
import { generateLaTeXBlockId } from "./utils";

export const CustomLaTeXExtension = CustomLaTeXExtensionConfig.extend({
  addCommands() {
    return {
      insertLaTeX:
        () =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              id: generateLaTeXBlockId(),
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => <LaTeXBlock {...props} node={props.node as LaTeXNodeViewProps["node"]} />);
  },
});
