import type { TActivityEntityData, TPage, TPageCollection, TWikiScope } from "@plane/types";

export function buildWikiHomeModel({
  scope,
  pages,
  collections,
  recents,
}: {
  scope: TWikiScope;
  pages: TPage[];
  collections: TPageCollection[];
  recents: TActivityEntityData[];
}) {
  const visiblePages = pages.filter((page) => page.workspace === scope.id && !page.deleted_at && !page.archived_at);
  const pageIds = new Set(visiblePages.map((page) => page.id));
  const visibleRecents = recents.filter(
    (recent) => recent.entity_name === "workspace_page" && pageIds.has(recent.entity_identifier)
  );
  const orderedCollections = collections.toSorted((a, b) => a.sort_order - b.sort_order);
  return {
    pages: visiblePages,
    favorites: visiblePages.filter((page) => page.is_favorite),
    recents: visibleRecents,
    collections: orderedCollections,
    canCreate: scope.can_create,
    isEmpty: visiblePages.length === 0 && orderedCollections.length === 0,
  };
}
