/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { NodeViewProps } from "@tiptap/react";
import { NodeViewWrapper } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";
// types
import { ILaTeXAttributeNames } from "./types";
import type { TLaTeXBlockAttributes } from "./types";

export type LaTeXNodeViewProps = NodeViewProps & {
  node: NodeViewProps["node"] & {
    attrs: TLaTeXBlockAttributes;
  };
  updateAttributes: (attrs: Partial<TLaTeXBlockAttributes>) => void;
};

export function LaTeXBlock(props: LaTeXNodeViewProps) {
  const { editor, node, updateAttributes } = props;
  const code = node.attrs[ILaTeXAttributeNames.CODE] ?? "";
  const [isEditing, setIsEditing] = useState(false);
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const renderLatex = useCallback(async (latexCode: string) => {
    if (!latexCode.trim()) {
      setHtmlContent("");
      setError(null);
      return;
    }
    try {
      const katex = (await import("katex")).default;
      const html = katex.renderToString(latexCode, {
        displayMode: true,
        throwOnError: false,
        strict: true,
        trust: false,
        output: "html",
      });
      setHtmlContent(html);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to render LaTeX");
      setHtmlContent("");
    }
  }, []);

  useEffect(() => {
    if (!isEditing) {
      renderLatex(code);
    }
  }, [code, isEditing, renderLatex]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
    }
  }, [isEditing]);

  return (
    <NodeViewWrapper
      className="editor-latex-block border-custom-border-200 my-2 overflow-hidden rounded border"
      data-block-type="latex-component"
    >
      <div className="border-custom-border-200 flex items-center justify-between border-b px-3 py-1.5">
        <span className="text-xs text-custom-text-300 font-medium">LaTeX</span>
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
        <div className="p-2" contentEditable={false}>
          <textarea
            ref={textareaRef}
            className="border-custom-border-300 bg-custom-bg-100 font-mono text-xs text-custom-text-100 focus:border-custom-primary min-h-[80px] w-full resize-y rounded border p-2 focus:outline-none"
            value={code}
            onChange={(e) => {
              updateAttributes({
                [ILaTeXAttributeNames.CODE]: e.target.value,
              });
            }}
            spellCheck={false}
          />
        </div>
      ) : (
        <div className="p-4" contentEditable={false}>
          {error ? (
            <div className="bg-red-50 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-400 rounded p-3">
              {error}
            </div>
          ) : htmlContent ? (
            <div
              className="latex-preview flex justify-center overflow-x-auto"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
          ) : (
            <div className="text-xs text-custom-text-300 py-8 text-center">No LaTeX to display</div>
          )}
        </div>
      )}
    </NodeViewWrapper>
  );
}
