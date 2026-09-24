import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import type { TWikiPersonalSection } from "@plane/types";
import { getWikiPagePath } from "../../../helpers/wiki-routes";
import { WikiService } from "../../../services/wiki.service";

const wikiService = new WikiService();
const sections: { key: TWikiPersonalSection; labelKey: string }[] = [
  { key: "favorites", labelKey: "wiki.sidebar.favorites" },
  { key: "owned", labelKey: "wiki.sidebar.my_pages" },
  { key: "shared", labelKey: "wiki.sidebar.shared_with_me" },
];

function PersonalSection({
  section,
  label,
  onNavigate,
}: {
  section: TWikiPersonalSection;
  label: string;
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const { data, error, isLoading, mutate } = useSWR(expanded ? `WIKI_PERSONAL_${section}` : null, () =>
    wikiService.fetchPersonalPages(section)
  );
  return (
    <section>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="focus-visible:outline-accent-primary w-full rounded px-2 py-1.5 text-left text-13 font-medium text-secondary hover:bg-layer-1 focus-visible:outline-2"
      >
        {expanded ? "⌄" : "›"} {label}
      </button>
      {expanded && (
        <div className="pl-5">
          {isLoading && <div className="h-4 w-3/4 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />}
          {error && (
            <button type="button" onClick={() => void mutate()} className="text-12 text-accent-primary">
              {t("wiki.sidebar.retry")}
            </button>
          )}
          {data?.results.map((page) => (
            <Link
              key={`${page.workspace_slug}:${page.page_id}`}
              href={getWikiPagePath(page.workspace_slug, page.page_id)}
              onClick={onNavigate}
              className="focus-visible:outline-accent-primary block truncate rounded px-2 py-1 text-13 text-secondary hover:bg-layer-1 focus-visible:outline-2"
            >
              {page.page_name || t("wiki.untitled")}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function WikiPersonalSections({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-0.5 border-t border-subtle pt-2">
      {sections.map(({ key, labelKey }) => (
        <PersonalSection key={key} section={key} label={t(labelKey)} onNavigate={onNavigate} />
      ))}
    </div>
  );
}
