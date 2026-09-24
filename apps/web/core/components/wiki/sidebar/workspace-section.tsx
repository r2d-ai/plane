import { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import type { TWikiScope } from "@plane/types";
import { cn } from "@plane/utils";
import { useTranslation } from "@plane/i18n";
import { getWikiCollectionPath } from "../../../helpers/wiki-routes";
import { useWikiNavigation } from "../../../hooks/store/use-wiki-navigation";
import {
  expandWikiWorkspace,
  getCollectionSubtreePages,
  getLooseWikiPages,
} from "./model";
import { WikiPageTree } from "./page-tree";

type Props = {
  scope: TWikiScope;
  label: string;
  activeSlug?: string;
  activePageId?: string;
  activeCollectionId?: string;
  onNavigate: () => void;
  initiallyExpanded?: boolean;
  isDefaultScope?: boolean;
};

export const WikiWorkspaceSection = observer(function WikiWorkspaceSection({
  scope,
  label,
  activeSlug,
  activePageId,
  activeCollectionId,
  onNavigate,
  initiallyExpanded = false,
  isDefaultScope = false,
}: Props) {
  const navigation = useWikiNavigation();
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(initiallyExpanded || isDefaultScope);
  const [expandedCollections, setExpandedCollections] = useState<Record<string, boolean>>({});
  const [collectionErrors, setCollectionErrors] = useState<Record<string, string>>({});
  const [collectionLoading, setCollectionLoading] = useState<Record<string, boolean>>({});
  const data = navigation.getScope(scope.slug);
  const showContents = isDefaultScope || expanded;

  useEffect(() => {
    if (isDefaultScope || initiallyExpanded || activeSlug === scope.slug) {
      setExpanded(true);
      void expandWikiWorkspace(navigation, scope.slug).catch(() => {});
    }
  }, [isDefaultScope, initiallyExpanded, activeSlug, navigation, scope.slug]);

  const toggleWorkspace = () => {
    setExpanded((current) => !current);
    if (!expanded) void expandWikiWorkspace(navigation, scope.slug).catch(() => {});
  };

  const loadCollection = useCallback(
    (collectionId: string) => {
      setCollectionLoading((current) => ({ ...current, [collectionId]: true }));
      setCollectionErrors((current) => ({ ...current, [collectionId]: "" }));
      void navigation
        .fetchCollectionPages(scope.slug, collectionId)
        .catch((error: unknown) =>
          setCollectionErrors((current) => ({
            ...current,
            [collectionId]: error instanceof Error ? error.message : "Could not load collection",
          }))
        )
        .finally(() => setCollectionLoading((current) => ({ ...current, [collectionId]: false })));
    },
    [navigation, scope.slug]
  );

  useEffect(() => {
    if (!showContents || data.status !== "loaded") return;
    const defaultCollection = data.collectionIds
      .map((id) => data.collectionsById[id])
      .find((collection) => collection?.is_default);
    if (!defaultCollection || expandedCollections[defaultCollection.id] !== undefined) return;

    setExpandedCollections((current) => ({ ...current, [defaultCollection.id]: true }));
    if (!data.collectionPagesById[defaultCollection.id]) loadCollection(defaultCollection.id);
  }, [
    showContents,
    data.status,
    data.collectionIds,
    data.collectionsById,
    data.collectionPagesById,
    expandedCollections,
    loadCollection,
  ]);

  const toggleCollection = (collectionId: string) => {
    setExpandedCollections((current) => ({ ...current, [collectionId]: !current[collectionId] }));
    if (expandedCollections[collectionId] || data.collectionPagesById[collectionId]) return;
    loadCollection(collectionId);
  };

  const allPages = data.pageIds.map((id) => data.pagesById[id]).filter((page) => !!page);
  const loosePages = getLooseWikiPages(allPages, data.collectionPagesById);

  return (
    <div>
      {isDefaultScope ? (
        <Link
          href={`/wiki/${scope.slug}`}
          onClick={onNavigate}
          aria-current={activeSlug === scope.slug && !activePageId ? "page" : undefined}
          className={cn(
            "focus-visible:outline-accent-primary mb-2 flex items-center gap-2 rounded px-2 py-1.5 text-13 hover:bg-layer-1 focus-visible:outline-2",
            activeSlug === scope.slug && !activePageId ? "bg-layer-1 font-medium text-primary" : "text-secondary"
          )}
        >
          <span aria-hidden>⌂</span>
          <span>{t("wiki.sidebar.home")}</span>
        </Link>
      ) : (
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
            aria-expanded={expanded}
            onClick={toggleWorkspace}
            className="focus-visible:outline-accent-primary size-7 rounded focus-visible:outline-2"
          >
            {expanded ? "⌄" : "›"}
          </button>
          <Link
            href={`/wiki/${scope.slug}`}
            onClick={onNavigate}
            aria-current={activeSlug === scope.slug && !activePageId ? "page" : undefined}
            className={cn(
              "focus-visible:outline-accent-primary min-w-0 flex-1 truncate rounded px-2 py-1.5 text-13 hover:bg-layer-1 focus-visible:outline-2",
              activeSlug === scope.slug ? "bg-layer-1 font-medium text-primary" : "text-secondary"
            )}
          >
            {label}
          </Link>
        </div>
      )}

      {showContents && (
        <div className={isDefaultScope ? "" : "pl-2"}>
          {data.status === "loading" && (
            <div className="space-y-2 p-2" aria-label={`Loading ${label}`}>
              <div className="h-4 w-4/5 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
              <div className="h-4 w-3/5 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
            </div>
          )}
          {data.status === "error" && (
            <div className="px-2 text-12 text-secondary">
              <p>{data.error}</p>
              <button
                type="button"
                onClick={() => void expandWikiWorkspace(navigation, scope.slug).catch(() => {})}
                className="rounded text-accent-primary focus-visible:outline-2"
              >
                {t("wiki.sidebar.retry")}
              </button>
            </div>
          )}
          {data.status === "loaded" && (
            <>
              {isDefaultScope && data.collectionIds.length > 0 && (
                <p className="px-2 py-1 text-11 font-semibold tracking-wide text-tertiary">
                  {t("wiki.collections.section_title")}
                </p>
              )}
              {data.collectionIds.map((id) => {
                const collection = data.collectionsById[id];
                if (!collection) return null;
                const collectionPages = getCollectionSubtreePages(allPages, data.collectionPagesById[id] ?? []);
                return (
                  <div key={id}>
                    <div
                      className={cn(
                        "flex items-center rounded text-13 text-secondary hover:bg-layer-1",
                        activeCollectionId === id && "bg-layer-1 font-medium text-primary"
                      )}
                    >
                      <button
                        type="button"
                        aria-label={`${expandedCollections[id] ? "Collapse" : "Expand"} ${collection.name}`}
                        aria-expanded={!!expandedCollections[id]}
                        onClick={() => toggleCollection(id)}
                        className="focus-visible:outline-accent-primary grid size-7 flex-shrink-0 place-items-center rounded focus-visible:outline-2"
                      >
                        {expandedCollections[id] ? "⌄" : "›"}
                      </button>
                      <Link
                        href={getWikiCollectionPath(scope.slug, id)}
                        onClick={onNavigate}
                        aria-current={activeCollectionId === id ? "page" : undefined}
                        className="focus-visible:outline-accent-primary min-w-0 flex-1 truncate rounded py-1 pr-2 focus-visible:outline-2"
                      >
                        {collection.name}
                      </Link>
                    </div>
                    {expandedCollections[id] && (
                      <div className="pl-5">
                        {collectionLoading[id] && (
                          <div className="h-4 w-3/4 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
                        )}
                        {collectionErrors[id] && (
                          <button type="button" onClick={() => loadCollection(id)} className="text-12 text-accent-primary">
                            {t("wiki.sidebar.retry")}
                          </button>
                        )}
                        {!collectionLoading[id] && !collectionErrors[id] && (
                          <WikiPageTree
                            pages={collectionPages}
                            workspaceSlug={scope.slug}
                            activePageId={activePageId}
                            onNavigate={onNavigate}
                          />
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              {loosePages.length > 0 && (
                <WikiPageTree
                  pages={loosePages}
                  workspaceSlug={scope.slug}
                  activePageId={activePageId}
                  onNavigate={onNavigate}
                />
              )}
              <Link
                href={`/wiki/${scope.slug}?view=archived`}
                onClick={onNavigate}
                className="focus-visible:outline-accent-primary mt-1 block rounded px-3 py-1.5 text-13 text-secondary hover:bg-layer-1 focus-visible:outline-2"
              >
                {t("wiki.sidebar.archived")}
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
});
