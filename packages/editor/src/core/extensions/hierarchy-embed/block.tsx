/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewWrapper } from "@tiptap/react";
// types
import { IHierarchyEmbedAttributeNames } from "./types";
import type { THierarchyEmbedAttributes } from "./types";

export type CustomHierarchyEmbedNodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: THierarchyEmbedAttributes;
  };
  updateAttributes: (attrs: Partial<THierarchyEmbedAttributes>) => void;
};

export function CustomHierarchyEmbedBlock(props: CustomHierarchyEmbedNodeViewProps) {
  const { node } = props;
  const pageId = node.attrs[IHierarchyEmbedAttributeNames.PAGE_ID];
  const depth = node.attrs[IHierarchyEmbedAttributeNames.DEPTH] ?? 2;
  const viewMode = node.attrs[IHierarchyEmbedAttributeNames.VIEW_MODE] ?? "children";

  return (
    <NodeViewWrapper
      className="editor-hierarchy-embed border-custom-border-300 my-2 rounded border border-dashed p-4"
      data-block-type="hierarchy-embed-component"
      contentEditable={false}
    >
      <div className="text-sm text-custom-text-300 flex items-center gap-2">
        <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M3 3h18v18H3z" />
          <path d="M3 9h18" />
          <path d="M9 21V9" />
        </svg>
        <span>
          Page Hierarchy ({viewMode}, depth: {depth})
        </span>
      </div>
      {!pageId && <div className="text-xs text-custom-text-400 mt-2">Configure page ID to display hierarchy</div>}
    </NodeViewWrapper>
  );
}
