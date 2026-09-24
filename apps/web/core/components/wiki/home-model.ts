import type { TPage, TWikiScope } from "@plane/types";

const pageTimestamp = (value: string | Date | undefined): number => {
  if (!value) return 0;
  const timestamp = value instanceof Date ? value.getTime() : Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
};

export function buildWikiHomeModel({ scope, pages, limit = 6 }: { scope: TWikiScope; pages: TPage[]; limit?: number }) {
  const recentlyUpdated = pages
    .filter((page) => page.workspace === scope.id && !page.deleted_at && !page.archived_at)
    .toSorted((a, b) => {
      const aTime = pageTimestamp(a.updated_at ?? a.created_at);
      const bTime = pageTimestamp(b.updated_at ?? b.created_at);
      return bTime - aTime;
    })
    .slice(0, limit);

  return { recentlyUpdated };
}
