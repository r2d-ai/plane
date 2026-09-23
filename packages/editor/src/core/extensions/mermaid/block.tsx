/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewWrapper } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";
// types
import { IMermaidAttributeNames } from "./types";
import type { TMermaidBlockAttributes } from "./types";

export type CustomMermaidNodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: TMermaidBlockAttributes;
  };
  updateAttributes: (attrs: Partial<TMermaidBlockAttributes>) => void;
};

export function CustomMermaidBlock(props: CustomMermaidNodeViewProps) {
  const { editor, node, updateAttributes } = props;
  const code = node.attrs[IMermaidAttributeNames.CODE] ?? "";
  const [isEditing, setIsEditing] = useState(false);
  const [svgContent, setSvgContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const renderDiagram = useCallback(async (diagramCode: string) => {
    if (!diagramCode.trim()) {
      setSvgContent("");
      setError(null);
      return;
    }
    try {
      const { default: mermaid } = await import("mermaid");
      mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "strict",
        logLevel: "error",
      });
      const id = `mermaid-${node.attrs[IMermaidAttributeNames.ID] || Date.now()}`;
      const { svg } = await mermaid.render(id, diagramCode);
      setSvgContent(svg);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to render diagram");
      setSvgContent("");
    }
  }, [node.attrs]);

  useEffect(() => {
    if (!isEditing) {
      renderDiagram(code);
    }
  }, [code, isEditing, renderDiagram]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
    }
  }, [isEditing]);

  return (
    <NodeViewWrapper
      className="editor-mermaid-block my-2 rounded border border-custom-border-200 overflow-hidden"
      data-block-type="mermaid-component"
    >
      <div className="flex items-center justify-between border-b border-custom-border-200 px-3 py-1.5">
        <span className="text-xs font-medium text-custom-text-300">Mermaid Diagram</span>
        <div className="flex gap-1">
          <button
            type="button"
            className="rounded px-2 py-0.5 text-xs text-custom-text-200 hover:bg-custom-bg-80"
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
        <div className="p-2" contentEditable={false}>
          <textarea
            ref={textareaRef}
            className="w-full min-h-[120px] resize-y rounded border border-custom-border-300 bg-custom-bg-100 p-2 font-mono text-xs text-custom-text-100 focus:border-custom-primary focus:outline-none"
            value={code}
            onChange={(e) => {
              updateAttributes({
                [IMermaidAttributeNames.CODE]: e.target.value,
              });
            }}
            spellCheck={false}
          />
        </div>
      ) : (
        <div className="p-4" contentEditable={false}>
          {error ? (
            <div className="rounded bg-red-50 p-3 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400">
              {error}
            </div>
          ) : svgContent ? (
            <div
              className="mermaid-preview flex justify-center [&>svg]:max-w-full"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          ) : (
            <div className="py-8 text-center text-xs text-custom-text-300">No diagram to display</div>
          )}
        </div>
      )}
    </NodeViewWrapper>
  );
}
