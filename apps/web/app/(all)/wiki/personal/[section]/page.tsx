import { useEffect, useState } from "react";
import Link from "next/link";
import useSWRInfinite from "swr/infinite";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import type { TWikiPersonalPageResponse, TWikiPersonalSection } from "@plane/types";
import { getWikiPagePath } from "../../../../../core/helpers/wiki-routes";
import { WikiService } from "@/services/wiki.service";
import type { Route } from "./+types/page";

const wikiService = new WikiService();
const labels: Record<TWikiPersonalSection, string> = {
  favorites: "wiki.sidebar.favorites",
  owned: "wiki.sidebar.my_pages",
  shared: "wiki.sidebar.shared_with_me",
};

export default function WikiPersonalPageRoute({ params }: Route.ComponentProps) {
  const { t } = useTranslation();
  const section = params.section as TWikiPersonalSection;
  const valid = Object.hasOwn(labels, section);
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [input]);

  const { data, error, isLoading, isValidating, size, setSize, mutate } = useSWRInfinite<TWikiPersonalPageResponse>(
    (index, previous) => {
      if (!valid || (index > 0 && !previous?.next_cursor)) return null;
      return ["WIKI_PERSONAL", section, query, index > 0 ? previous?.next_cursor : ""] as const;
    },
    ([, currentSection, currentQuery, cursor]) =>
      wikiService.fetchPersonalPages(
        currentSection as TWikiPersonalSection,
        currentQuery as string,
        (cursor as string) || undefined
      ),
    { revalidateFirstPage: false }
  );
  const pages = data?.flatMap((response) => response.results) ?? [];
  const hasMore = !!data?.at(-1)?.next_cursor;

  if (!valid) return <div className="p-8 text-13 text-secondary">{t("wiki.personal.invalid_section")}</div>;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[800px] px-6 py-8">
        <h1 className="text-20 font-semibold text-primary">{t(labels[section])}</h1>
        <input
          type="search"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t("wiki.personal.search_placeholder")}
          aria-label={t("wiki.personal.search_placeholder")}
          className="focus:border-accent-primary mt-6 w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary outline-none"
        />
        <div className="mt-5" aria-live="polite">
          {isLoading && <div className="h-10 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />}
          {error && (
            <div role="alert" className="text-13 text-secondary">
              {t("wiki.personal.load_failed")}{" "}
              <button type="button" onClick={() => void mutate()} className="text-accent-primary">
                {t("wiki.sidebar.retry")}
              </button>
            </div>
          )}
          {!isLoading && !error && pages.length === 0 && (
            <p className="py-10 text-center text-13 text-secondary">
              {t(query ? "wiki.personal.no_results" : "wiki.personal.empty")}
            </p>
          )}
          {pages.map((page) => (
            <Link
              key={`${page.workspace_slug}:${page.page_id}`}
              href={getWikiPagePath(page.workspace_slug, page.page_id)}
              className="flex items-center gap-3 border-b border-subtle px-2 py-3 text-13 text-primary hover:bg-layer-1"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-sm bg-layer-2">
                <PageIcon className="size-4 text-tertiary" />
              </span>
              <span className="min-w-0 flex-1 truncate">{page.page_name || t("wiki.untitled")}</span>
              <span className="max-w-1/3 truncate text-12 text-secondary">{page.workspace_name}</span>
            </Link>
          ))}
          {hasMore && !error && (
            <button
              type="button"
              disabled={isValidating}
              onClick={() => void setSize(size + 1)}
              className="mt-5 rounded-md border border-subtle px-4 py-2 text-13 text-primary hover:bg-layer-1 disabled:opacity-50"
            >
              {isValidating ? t("wiki.personal.loading") : t("wiki.personal.load_more")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
