/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewContent, NodeViewWrapper } from "@tiptap/react";
// types
import { IToggleBlockAttributeNames } from "./types";
import type { TToggleBlockAttributes } from "./types";

export type CustomToggleBlockNodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: TToggleBlockAttributes;
  };
  updateAttributes: (attrs: Partial<TToggleBlockAttributes>) => void;
};

export function CustomToggleBlock(props: CustomToggleBlockNodeViewProps) {
  const { editor, node, updateAttributes } = props;
  const isOpen = node.attrs[IToggleBlockAttributeNames.OPEN] ?? true;

  return (
    <NodeViewWrapper
      className="editor-toggle-block border-custom-border-200 my-2 rounded border"
      data-block-type="toggle-block-component"
    >
      <button
        type="button"
        className="text-sm text-custom-text-200 hover:bg-custom-bg-80 flex w-full items-center gap-2 px-3 py-2 text-left font-medium"
        onClick={() => {
          if (!editor.isEditable) return;
          updateAttributes({
            [IToggleBlockAttributeNames.OPEN]: !isOpen,
          });
        }}
        contentEditable={false}
      >
        <svg
          className={`size-4 shrink-0 transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M9 18l6-6-6-6" />
        </svg>
        <span>Toggle</span>
      </button>
      {isOpen && (
        <div className="border-custom-border-200 border-t px-3 py-2">
          <NodeViewContent as="div" className="w-full break-words" />
        </div>
      )}
    </NodeViewWrapper>
  );
}
