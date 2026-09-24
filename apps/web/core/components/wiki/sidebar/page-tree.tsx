import { useState } from "react";
import Link from "next/link";
import type { TPage } from "@plane/types";
import { cn } from "@plane/utils";
import { getWikiPagePath } from "../../../helpers/wiki-routes";

type Props = {
  pages: TPage[];
  workspaceSlug: string;
  activePageId?: string;
  onNavigate: () => void;
  parentId?: string | null;
  depth?: number;
};

export function WikiPageTree({ pages, workspaceSlug, activePageId, onNavigate, parentId = null, depth = 0 }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const children = pages.filter((page) => {
    if (!page.id || page.deleted_at || page.archived_at) return false;
    const parent = page.parent ?? null;
    return (
      parent === parentId ||
      (parentId === null && parent !== null && !pages.some((candidate) => candidate.id === parent))
    );
  });
  if (depth > 20) return null;
  return (
    <ul className="space-y-0.5">
      {children.map((page) => {
        const pageId = page.id ?? "";
        const hasChildren = pages.some((candidate) => candidate.parent === pageId);
        return (
          <li key={pageId}>
            <div className="flex items-center" style={{ paddingLeft: depth * 12 }}>
              {hasChildren ? (
                <button
                  type="button"
                  aria-label={`${expanded[pageId] ? "Collapse" : "Expand"} ${page.name || "Untitled"}`}
                  aria-expanded={!!expanded[pageId]}
                  className="focus-visible:outline-accent-primary size-6 rounded focus-visible:outline-2"
                  onClick={() => setExpanded((current) => ({ ...current, [pageId]: !current[pageId] }))}
                >
                  {expanded[pageId] ? "⌄" : "›"}
                </button>
              ) : (
                <span className="size-6" />
              )}
              <Link
                href={getWikiPagePath(workspaceSlug, pageId)}
                onClick={onNavigate}
                aria-current={activePageId === pageId ? "page" : undefined}
                className={cn(
                  "focus-visible:outline-accent-primary min-w-0 flex-1 truncate rounded px-2 py-1 text-13 text-secondary hover:bg-layer-1 focus-visible:outline-2",
                  activePageId === pageId && "bg-layer-1 font-medium text-primary"
                )}
              >
                {page.name || "Untitled"}
              </Link>
            </div>
            {expanded[pageId] && (
              <WikiPageTree
                pages={pages}
                workspaceSlug={workspaceSlug}
                activePageId={activePageId}
                onNavigate={onNavigate}
                parentId={pageId}
                depth={depth + 1}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
