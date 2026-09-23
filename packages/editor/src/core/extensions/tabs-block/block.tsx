/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewContent, NodeViewWrapper } from "@tiptap/react";
// types
import { ITabsBlockAttributeNames } from "./types";
import type { TTabsBlockAttributes } from "./types";

export type CustomTabsBlockNodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: TTabsBlockAttributes;
  };
  updateAttributes: (attrs: Partial<TTabsBlockAttributes>) => void;
};

export function CustomTabsBlock(props: CustomTabsBlockNodeViewProps) {
  const { editor, node, updateAttributes } = props;
  const orientation = node.attrs[ITabsBlockAttributeNames.ORIENTATION] ?? "horizontal";
  const activeTab = node.attrs[ITabsBlockAttributeNames.ACTIVE_TAB] ?? 0;

  // Extract tab labels from child nodes
  const tabLabels: string[] = [];
  node.forEach((child) => {
    tabLabels.push(child.attrs["data-tab-label"] || "Tab");
  });

  if (tabLabels.length === 0) {
    tabLabels.push("Tab");
  }

  return (
    <NodeViewWrapper
      className="editor-tabs-block border-custom-border-200 my-2 rounded border"
      data-block-type="tabs-block-component"
      data-orientation={orientation}
    >
      <div className={`flex ${orientation === "vertical" ? "flex-row" : "flex-col"}`}>
        <div
          className={`flex ${orientation === "vertical" ? "border-custom-border-200 flex-col border-r" : "border-custom-border-200 border-b"}`}
          contentEditable={false}
        >
          {tabLabels.map((label, index) => (
            <button
              key={label}
              type="button"
              className={`text-sm px-3 py-2 text-left font-medium transition-colors ${
                index === activeTab
                  ? "border-custom-primary text-custom-primary border-b-2"
                  : "text-custom-text-200 hover:text-custom-text-100"
              }`}
              onClick={() => {
                if (!editor.isEditable) return;
                updateAttributes({
                  [ITabsBlockAttributeNames.ACTIVE_TAB]: index,
                });
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className={`flex-1 ${orientation === "vertical" ? "p-3" : "p-3"}`}>
          <NodeViewContent as="div" className="w-full break-words" />
        </div>
      </div>
    </NodeViewWrapper>
  );
}
