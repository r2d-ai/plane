/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ReactNodeViewRenderer } from "@tiptap/react";
// local imports
import { CustomHierarchyEmbedBlock } from "./block";
import type { CustomHierarchyEmbedNodeViewProps } from "./block";
import { HierarchyEmbedExtensionConfig } from "./extension-config";
import { generateHierarchyEmbedId } from "./utils";

export const HierarchyEmbedExtension = HierarchyEmbedExtensionConfig.extend({
  addCommands() {
    return {
      insertHierarchyEmbed:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({
            type: this.name,
            attrs: {
              id: generateHierarchyEmbedId(),
              "data-page-id": attrs.pageId,
              "data-workspace-slug": attrs.workspaceSlug,
              "data-project-id": attrs.projectId,
            },
          }),
    };
  },

  addNodeView() {
    return ReactNodeViewRenderer((props) => (
      <CustomHierarchyEmbedBlock
        {...props}
        node={props.node as CustomHierarchyEmbedNodeViewProps["node"]}
      />
    ));
  },
});
