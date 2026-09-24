import { useMemo } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
import { Globe2, Lock } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { PageIcon } from "@plane/propel/icons";
import { EPageCollectionAccess, type TPage, type TPageCollectionPage, type TWikiScope } from "@plane/types";
import { useWikiNavigation } from "../../hooks/store/use-wiki-navigation";
import { getWikiPagePath } from "../../helpers/wiki-routes";
import { WorkspacePageCollectionService } from "../../services/page/workspace-page-collection.service";

const collectionService = new WorkspacePageCollectionService();

function countNestedPages(pageId: string, pages: TPage[]): number {
  const childrenByParent = new Map<string, string[]>();
  for (const page of pages) {
    if (!page.id || !page.parent) continue;
    const children = childrenByParent.get(page.parent) ?? [];
    children.push(page.id);
    childrenByParent.set(page.parent, children);
  }

  let count = 0;
  const stack = [...(childrenByParent.get(pageId) ?? [])];
  const visited = new Set<string>();

  while (stack.length > 0) {
    const current = stack.pop();
    if (!current || visited.has(current)) continue;
    visited.add(current);
    count += 1;
    stack.push(...(childrenByParent.get(current) ?? []));
  }

  return count;
}

function formatLastActivity(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
  }).format(date);
}

function CollectionTableRow({
  item,
  workspaceSlug,
  nestedPages,
}: {
  item: TPageCollectionPage;
  workspaceSlug: string;
  nestedPages: number;
}) {
  const detail = item.page_detail;
  const owner = detail.owner_detail;

  return (
    <Link
      href={getWikiPagePath(workspaceSlug, detail.id)}
      className="grid min-h-12 grid-cols-[minmax(220px,1fr)_180px_120px_150px] items-center border-b border-subtle text-13 text-primary transition-colors last:border-b-0 hover:bg-layer-1"
    >
      <div className="flex min-w-0 items-center gap-2 px-3 py-2.5">
        <PageIcon className="size-4 flex-shrink-0 text-tertiary" />
        <span className="truncate">{detail.name || "Untitled"}</span>
      </div>
      <div className="flex min-w-0 items-center gap-2 px-3 py-2.5 text-secondary">
        <span className="grid size-5 flex-shrink-0 place-items-center rounded-full bg-layer-2 text-10 font-medium text-tertiary">
          {(owner?.display_name || "?").slice(0, 1).toUpperCase()}
        </span>
        <span className="truncate">{owner?.display_name || "—"}</span>
      </div>
      <div className="px-3 py-2.5 text-secondary">{nestedPages}</div>
      <div className="px-3 py-2.5 text-secondary">{formatLastActivity(detail.updated_at)}</div>
    </Link>
  );
}

export const WikiCollectionView = observer(function WikiCollectionView({
  scope,
  collectionId,
}: {
  scope: TWikiScope;
  collectionId: string;
}) {
  const { t } = useTranslation();
  const navigation = useWikiNavigation();

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWR(`WIKI_COLLECTION_${scope.slug}_${collectionId}`, async () => {
    const [collection, pages] = await Promise.all([
      collectionService.fetchById(scope.slug, collectionId),
      collectionService.fetchPages(scope.slug, collectionId),
      navigation.fetchScope(scope.slug),
    ]);
    return { collection, pages };
  });

  const scopeData = navigation.getScope(scope.slug);
  const visiblePages = useMemo(
    () => scopeData.pageIds.map((id) => scopeData.pagesById[id]).filter((page): page is TPage => !!page),
    [scopeData.pageIds, scopeData.pagesById]
  );

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-[1100px] px-6 py-8">
        <div className="h-7 w-48 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
        <div className="mt-6 h-64 animate-pulse rounded-lg bg-layer-1 motion-reduce:animate-none" />
      </div>
    );
  }

  if (error || !data?.collection) {
    return (
      <div className="mx-auto w-full max-w-[900px] px-6 py-12 text-center text-13 text-secondary">
        <p>Could not load this collection.</p>
        <button type="button" onClick={() => void mutate()} className="mt-2 text-accent-primary">
          {t("wiki.sidebar.retry")}
        </button>
      </div>
    );
  }

  const { collection, pages } = data;
  const sortedPages = pages.toSorted(
    (a, b) => (a.sort_order ?? a.page_detail.sort_order ?? 65535) - (b.sort_order ?? b.page_detail.sort_order ?? 65535)
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1100px] px-6 py-8">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid size-8 place-items-center rounded-md bg-layer-1 text-tertiary">
            {collection.access === EPageCollectionAccess.PUBLIC ? (
              <Globe2 className="size-4" />
            ) : (
              <Lock className="size-4" />
            )}
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-20 font-semibold text-primary">{collection.name}</h1>
            {collection.description && <p className="mt-1 text-13 text-secondary">{collection.description}</p>}
          </div>
        </div>

        <div className="mt-7 overflow-x-auto rounded-lg border border-subtle bg-surface-1">
          <div className="min-w-[760px]">
            <div className="grid h-10 grid-cols-[minmax(220px,1fr)_180px_120px_150px] items-center border-b border-subtle bg-layer-1 text-11 font-semibold text-tertiary">
              <div className="px-3">{t("wiki_collections.list.columns.page_name")}</div>
              <div className="px-3">{t("wiki_collections.list.columns.owner")}</div>
              <div className="px-3">{t("wiki_collections.list.columns.nested_pages")}</div>
              <div className="px-3">{t("wiki_collections.list.columns.last_activity")}</div>
            </div>

            {sortedPages.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-14 font-medium text-primary">{t("wiki_collections.list.no_pages_title")}</p>
                <p className="mt-1 text-13 text-secondary">{t("wiki_collections.list.no_pages_description")}</p>
              </div>
            ) : (
              sortedPages.map((item) => (
                <CollectionTableRow
                  key={item.id}
                  item={item}
                  workspaceSlug={scope.slug}
                  nestedPages={countNestedPages(item.page, visiblePages)}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
