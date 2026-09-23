/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewWrapper } from "@tiptap/react";
import { useState } from "react";
// types
import { IDrawIOAttributeNames } from "./types";
import type { TDrawIOBlockAttributes } from "./types";

export type DrawIONodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: TDrawIOBlockAttributes;
  };
  updateAttributes: (attrs: Partial<TDrawIOBlockAttributes>) => void;
};

/**
 * Draw.io integration block.
 *
 * This is a placeholder for future Draw.io integration.
 * Full integration requires external plumbing (draw.io web plugin,
 * hosted instance, or marketplace app). This block establishes the
 * node structure and UI for when that integration is available.
 */
export function DrawIOBlock(props: DrawIONodeViewProps) {
  const { editor, node, updateAttributes } = props;
  const xml = node.attrs[IDrawIOAttributeNames.XML] ?? "";
  const [isEditing, setIsEditing] = useState(false);

  return (
    <NodeViewWrapper
      className="editor-drawio-component border-custom-border-200 my-2 overflow-hidden rounded border"
      data-block-type="drawio-component"
    >
      <div className="border-custom-border-200 flex items-center justify-between border-b px-3 py-1.5">
        <span className="text-xs text-custom-text-300 font-medium">Draw.io Diagram</span>
        <div className="flex gap-1">
          <button
            type="button"
            className="text-xs text-custom-text-200 hover:bg-custom-bg-80 rounded px-2 py-0.5"
            onClick={() => {
              if (!editor.isEditable) return;
              setIsEditing(!isEditing);
            }}
            contentEditable={false}
          >
            {isEditing ? "Preview" : "Edit"}
          </button>
        </div>
      </div>
      {isEditing ? (
        <div className="p-3" contentEditable={false}>
          <div className="bg-custom-bg-80 rounded p-4 text-center">
            <p className="text-sm text-custom-text-200">Draw.io integration requires external app plumbing.</p>
            <p className="text-xs text-custom-text-300 mt-2">
              Full integration will be available via the marketplace/app system.
            </p>
            <div className="mt-4">
              <label htmlFor="drawio-xml" className="text-xs text-custom-text-200 mb-1 block text-left font-medium">
                Draw.io XML (optional)
              </label>
              <textarea
                id="drawio-xml"
                className="border-custom-border-300 bg-custom-bg-100 font-mono text-xs text-custom-text-100 focus:border-custom-primary min-h-[100px] w-full resize-y rounded border p-2 focus:outline-none"
                value={xml}
                onChange={(e) => {
                  updateAttributes({
                    [IDrawIOAttributeNames.XML]: e.target.value,
                  });
                }}
                placeholder="Paste Draw.io XML here..."
                spellCheck={false}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4" contentEditable={false}>
          {xml ? (
            <div className="bg-custom-bg-80 rounded p-4 text-center">
              <p className="text-xs text-custom-text-300">
                Draw.io diagram (XML stored — full rendering requires integration)
              </p>
            </div>
          ) : (
            <div className="border-custom-border-300 bg-custom-bg-50 rounded border-2 border-dashed py-8 text-center">
              <p className="text-sm text-custom-text-300">Click Edit to add Draw.io diagram XML</p>
              <p className="text-xs text-custom-text-400 mt-1">Full Draw.io editor integration coming soon</p>
            </div>
          )}
        </div>
      )}
    </NodeViewWrapper>
  );
}
