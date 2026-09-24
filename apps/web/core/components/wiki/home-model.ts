import type { TPage, TWikiScope } from "@plane/types";

export function buildWikiHomeModel({
  scope,
  pages,
  limit = 6,
}: {
  scope: TWikiScope;
  pages: TPage[];
  limit?: number;
}) {
  const recentlyUpdated = pages
    .filter((page) => page.workspace === scope.id && !page.deleted_at && !page.archived_at)
    .toSorted((a, b) => {
      const aTime = Date.parse(a.updated_at ?? a.created_at ?? "") || 0;
      const bTime = Date.parse(b.updated_at ?? b.created_at ?? "") || 0;
      return bTime - aTime;
    })
    .slice(0, limit);

  return { recentlyUpdated };
}
