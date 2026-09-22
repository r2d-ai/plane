/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { observer } from "mobx-react";
import { Search } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPageSearchResponse } from "@plane/types";
// plane ui
import { Input } from "@plane/ui";
// components
import { PageAccessIcon } from "@/components/common/page-access-icon";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { WorkspaceService } from "@/services/workspace.service";

type TWikiSearchResult = TPageSearchResponse & {
  workspace__slug: string;
};

type TProps = {
  workspaceSlug: string;
  /** Build the URL of a result. */
  buildPageHref: (params: { workspaceSlug: string; pageId: string }) => string;
};

const workspaceService = new WorkspaceService();

/** Build a short, plain-text preview around the matched term (never renders HTML). */
function getSearchSnippet(snippet: string | null | undefined, query: string, maxLength = 90): string {
  if (!snippet) return "";
  const text = snippet.replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  const matchIndex = query ? text.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (matchIndex === -1) return `${text.slice(0, maxLength)}…`;
  const start = Math.max(0, matchIndex - Math.floor(maxLength / 3));
  const end = Math.min(text.length, start + maxLength);
  return `${start > 0 ? "…" : ""}${text.slice(start, end)}${end < text.length ? "…" : ""}`;
}

/** Highlight the query inside plain text without ever injecting HTML. */
function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const parts: ReactNode[] = [];
  let cursor = 0;
  let index = lowerText.indexOf(lowerQuery);
  let key = 0;
  while (index !== -1) {
    if (index > cursor) parts.push(text.slice(cursor, index));
    parts.push(
      <mark key={key} className="bg-accent-primary/20 text-primary">
        {text.slice(index, index + query.length)}
      </mark>
    );
    key += 1;
    cursor = index + query.length;
    index = lowerText.indexOf(lowerQuery, cursor);
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <>{parts}</>;
}

/**
 * @description Top-level Wiki search (WIKI-04a §7.7).
 *
 * Live-searches the workspace via the entity-search API for `query_type=page`
 * (Wiki pages and project pages, both filtered by access). Results carry the
 * page id and workspace slug so the caller can route to the page detail
 * surface (`/${workspaceSlug}/wiki/${pageId}` for workspace wiki,
 * `/company-wiki/${pageId}` for company wiki).
 */
export const WikiSearchInput = observer(function WikiSearchInput(props: TProps) {
  const { workspaceSlug, buildPageHref } = props;
  const router = useAppRouter();
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TWikiSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!workspaceSlug || query.trim().length < 2) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    workspaceService
      .searchEntity(workspaceSlug, {
        count: 20,
        query: query.trim(),
        query_type: ["page"],
      })
      .then((response: any) => {
        if (cancelled) return response;
        setResults((response?.page ?? []) as TWikiSearchResult[]);
        setIsLoading(false);
        return response;
      })
      .catch((error: any) => {
        if (cancelled) return;
        setIsLoading(false);
        const message = error?.error || t("wiki.search_no_results");
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("common.error.label"),
          message,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [query, workspaceSlug, t]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSelect = useCallback(
    (result: TWikiSearchResult) => {
      setIsOpen(false);
      setQuery("");
      const resultWorkspaceSlug = result.workspace__slug ?? "";
      const pageId = result.id ?? "";
      if (!resultWorkspaceSlug || !pageId) return;
      router.push(buildPageHref({ workspaceSlug: resultWorkspaceSlug, pageId }));
    },
    [router, buildPageHref]
  );

  const hasQuery = useMemo(() => query.trim().length >= 2, [query]);

  return (
    <div ref={containerRef} className="relative flex w-full max-w-sm items-center" data-testid="wiki-search-input">
      <div className="relative w-full">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-tertiary" />
        <Input
          value={query}
          placeholder={t("wiki.search_placeholder")}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          className="h-8 pl-7 text-13"
          aria-label={t("wiki.search_placeholder")}
        />
      </div>
      {isOpen && hasQuery && (
        <div
          className="shadow-lg absolute top-full left-0 z-30 mt-1 w-full overflow-hidden rounded-md border border-subtle bg-surface-1"
          data-testid="wiki-search-results"
        >
          {isLoading ? (
            <div className="px-3 py-2 text-12 text-tertiary">Loading…</div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-12 text-tertiary">{t("wiki.search_no_results")}</div>
          ) : (
            <ul className="flex flex-col divide-y divide-subtle">
              {results.map((result) => (
                <li key={result.id}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-13 transition-colors hover:bg-layer-1"
                    onClick={() => handleSelect(result)}
                    data-testid="wiki-search-result"
                  >
                    {result.logo_props?.in_use ? (
                      <Logo logo={result.logo_props} size={14} type="lucide" />
                    ) : (
                      <PageIcon className="h-3.5 w-3.5 text-tertiary" />
                    )}
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-primary">
                        <HighlightText text={result.name || t("wiki.untitled")} query={query.trim()} />
                      </span>
                      {getSearchSnippet(result.description_stripped, query.trim()) && (
                        <span className="truncate text-11 text-tertiary">
                          <HighlightText
                            text={getSearchSnippet(result.description_stripped, query.trim())}
                            query={query.trim()}
                          />
                        </span>
                      )}
                    </span>
                    <PageAccessIcon {...({ archived_at: null, access: 0 } as any)} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
});
