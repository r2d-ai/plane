import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import type { TWikiScope } from "@plane/types";
import { cn } from "@plane/utils";
import { useWikiNavigation } from "../../../hooks/store/use-wiki-navigation";
import { getWikiPagePath } from "../../../helpers/wiki-routes";
import { expandWikiWorkspace } from "./model";
import { WikiPageTree } from "./page-tree";

type Props = {
  scope: TWikiScope;
  label: string;
  activeSlug?: string;
  activePageId?: string;
  onNavigate: () => void;
  initiallyExpanded?: boolean;
};

export const WikiWorkspaceSection = observer(function WikiWorkspaceSection({
  scope,
  label,
  activeSlug,
  activePageId,
  onNavigate,
  initiallyExpanded = false,
}: Props) {
  const navigation = useWikiNavigation();
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const [expandedCollections, setExpandedCollections] = useState<Record<string, boolean>>({});
  const [collectionErrors, setCollectionErrors] = useState<Record<string, string>>({});
  const [collectionLoading, setCollectionLoading] = useState<Record<string, boolean>>({});
  const data = navigation.getScope(scope.slug);

  useEffect(() => {
    if (initiallyExpanded || activeSlug === scope.slug) {
      setExpanded(true);
      void expandWikiWorkspace(navigation, scope.slug).catch(() => {});
    }
  }, [initiallyExpanded, activeSlug, navigation, scope.slug]);

  const toggleWorkspace = () => {
    setExpanded((current) => !current);
    if (!expanded) void expandWikiWorkspace(navigation, scope.slug).catch(() => {});
  };

  const loadCollection = (collectionId: string) => {
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
  };

  const toggleCollection = (collectionId: string) => {
    setExpandedCollections((current) => ({ ...current, [collectionId]: !current[collectionId] }));
    if (expandedCollections[collectionId] || data.collectionPagesById[collectionId]) return;
    loadCollection(collectionId);
  };

  return (
    <div>
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
      {expanded && (
        <div className="pl-2">
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
                Retry
              </button>
            </div>
          )}
          {data.status === "loaded" && (
            <>
              {data.collectionIds.map((id) => {
                const collection = data.collectionsById[id];
                if (!collection) return null;
                return (
                  <div key={id}>
                    <button
                      type="button"
                      aria-expanded={!!expandedCollections[id]}
                      onClick={() => toggleCollection(id)}
                      className="focus-visible:outline-accent-primary w-full rounded px-3 py-1 text-left text-13 text-secondary hover:bg-layer-1 focus-visible:outline-2"
                    >
                      {expandedCollections[id] ? "⌄" : "›"} {collection.name}
                    </button>
                    {expandedCollections[id] && (
                      <div className="pl-5">
                        {collectionLoading[id] && (
                          <div className="h-4 w-3/4 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
                        )}
                        {collectionErrors[id] && (
                          <button
                            type="button"
                            onClick={() => loadCollection(id)}
                            className="text-12 text-accent-primary"
                          >
                            Retry collection
                          </button>
                        )}
                        {data.collectionPagesById[id]?.map((item) => (
                          <Link
                            key={item.id}
                            href={getWikiPagePath(scope.slug, item.page)}
                            onClick={onNavigate}
                            className="focus-visible:outline-accent-primary block truncate rounded px-2 py-1 text-13 text-secondary hover:bg-layer-1 focus-visible:outline-2"
                          >
                            {item.page_detail.name || "Untitled"}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
              <WikiPageTree
                pages={data.pageIds.map((id) => data.pagesById[id]).filter((page) => !!page)}
                workspaceSlug={scope.slug}
                activePageId={activePageId}
                onNavigate={onNavigate}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
});
