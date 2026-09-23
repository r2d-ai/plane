/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes, Node } from "@tiptap/core";
// types
import { CORE_EXTENSIONS } from "@/constants/extension";
// types
import { IHierarchyEmbedAttributeNames, DEFAULT_HIERARCHY_EMBED_ATTRIBUTES } from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.HIERARCHY_EMBED]: {
      insertHierarchyEmbed: (attrs: {
        pageId: string;
        workspaceSlug: string;
        projectId: string;
      }) => ReturnType;
    };
  }
}

export const HierarchyEmbedExtensionConfig = Node.create({
  name: CORE_EXTENSIONS.HIERARCHY_EMBED,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      [IHierarchyEmbedAttributeNames.ID]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.ID],
      },
      [IHierarchyEmbedAttributeNames.PAGE_ID]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.PAGE_ID],
      },
      [IHierarchyEmbedAttributeNames.WORKSPACE_SLUG]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.WORKSPACE_SLUG],
      },
      [IHierarchyEmbedAttributeNames.PROJECT_ID]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.PROJECT_ID],
      },
      [IHierarchyEmbedAttributeNames.DEPTH]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.DEPTH],
      },
      [IHierarchyEmbedAttributeNames.VIEW_MODE]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.VIEW_MODE],
      },
      [IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR],
      },
      [IHierarchyEmbedAttributeNames.BLOCK_TYPE]: {
        default: DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.BLOCK_TYPE],
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: `hierarchy-embed-component`,
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["hierarchy-embed-component", mergeAttributes(HTMLAttributes)];
  },
});
