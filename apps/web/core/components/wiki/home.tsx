import { useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { EPageAccess } from "@plane/constants";
import { EPageCollectionAccess } from "@plane/types";
import type { TWikiScope } from "@plane/types";
import { PageTemplatesModal } from "@/components/pages/templates";
import { EPageStoreType, usePageStore } from "../../hooks/store";
import { useWikiNavigation } from "../../hooks/store/use-wiki-navigation";
import { useAppRouter } from "../../hooks/use-app-router";
import { getWikiPagePath } from "../../helpers/wiki-routes";
import { WorkspaceService } from "../../services/workspace.service";
import { buildWikiHomeModel } from "./home-model";

const workspaceService = new WorkspaceService();

export const WikiHome = observer(function WikiHome({ scope }: { scope: TWikiScope }) {
  const navigation = useWikiNavigation();
  const pageStore = usePageStore(EPageStoreType.WORKSPACE);
  const router = useAppRouter();
  const searchParams = useSearchParams();
  const archivedView = searchParams.get("view") === "archived";
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const { error, isLoading, mutate } = useSWR(`WIKI_SCOPE_${scope.slug}`, () => navigation.fetchScope(scope.slug));
  const { data: recents } = useSWR(scope.is_member ? `WIKI_RECENTS_${scope.slug}` : null, () =>
    workspaceService.fetchWorkspaceRecents(scope.slug, "workspace_page")
  );
  const data = navigation.getScope(scope.slug);
  const model = buildWikiHomeModel({
    scope,
    pages: data.pageIds.map((id) => data.pagesById[id]).filter((page) => !!page),
    collections: data.collectionIds.map((id) => data.collectionsById[id]).filter((collection) => !!collection),
    recents: recents ?? [],
  });

  const createPage = async () => {
    if (!scope.can_create || creating) return;
    setCreating(true);
    try {
      pageStore.activateScope(scope.slug);
      const page = await pageStore.createPage({ access: EPageAccess.PUBLIC });
      if (page?.id) router.push(getWikiPagePath(scope.slug, page.id));
    } catch (creationError) {
      console.error("Could not create Wiki page", creationError);
    } finally {
      setCreating(false);
    }
  };

  if (isLoading && data.status !== "loaded")
    return (
      <div className="space-y-3 p-6" aria-label="Loading Wiki Home">
        <div className="h-6 w-1/3 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
        <div className="h-24 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
      </div>
    );
  if (error || data.status === "error")
    return (
      <div role="alert" className="p-6">
        Could not load Wiki Home.{" "}
        <button type="button" onClick={() => void mutate()} className="text-accent-primary">
          Retry
        </button>
      </div>
    );

  const archivedPages = data.pageIds
    .map((id) => data.pagesById[id])
    .filter((page) => page && page.workspace === scope.id && !!page.archived_at && !page.deleted_at);
  const pageLink = (id: string) => getWikiPagePath(scope.slug, id);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-20 font-semibold text-primary">{scope.name}</h1>
          <p className="text-13 text-secondary">Browse pages and collections in this workspace.</p>
        </div>
        <div className="flex items-center gap-2">
          {scope.can_create && (
            <>
              <button
                type="button"
                onClick={() => setTemplatesOpen(true)}
                className="focus-visible:outline-accent-primary rounded border border-subtle px-3 py-1.5 text-13 focus-visible:outline-2"
              >
                Templates
              </button>
              <button
                type="button"
                disabled={creating}
                onClick={() => void createPage()}
                className="focus-visible:outline-accent-primary rounded bg-accent-primary px-3 py-1.5 text-13 text-white focus-visible:outline-2 disabled:opacity-50"
              >
                New page
              </button>
            </>
          )}
          <Link
            href={archivedView ? `/wiki/${scope.slug}` : `/wiki/${scope.slug}?view=archived`}
            className="focus-visible:outline-accent-primary rounded border border-subtle px-3 py-1.5 text-13 focus-visible:outline-2"
          >
            {archivedView ? "Home" : "Archived"}
          </Link>
        </div>
      </div>
      {archivedView ? (
        <section>
          <h2 className="text-15 mb-3 font-semibold">Archived pages</h2>
          {archivedPages.length ? (
            archivedPages.map((page) => (
              <Link
                key={page.id}
                href={pageLink(page.id ?? "")}
                className="block rounded border-b border-subtle px-2 py-2 text-13 hover:bg-layer-1"
              >
                {page.name || "Untitled"}
              </Link>
            ))
          ) : (
            <p className="text-13 text-secondary">No archived pages.</p>
          )}
        </section>
      ) : (
        <>
          {model.isEmpty && (
            <div className="rounded-lg border border-dashed border-subtle p-8 text-center text-13 text-secondary">
              <p>No pages or collections yet.</p>
              {scope.can_create && (
                <button
                  type="button"
                  onClick={() => void createPage()}
                  className="focus-visible:outline-accent-primary mt-3 rounded bg-accent-primary px-3 py-1.5 text-white focus-visible:outline-2"
                >
                  Create a page
                </button>
              )}
            </div>
          )}
          {model.recents.length > 0 && (
            <section className="mb-6">
              <h2 className="text-15 mb-2 font-semibold">Recently viewed</h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {model.recents.slice(0, 6).map((recent) => (
                  <Link
                    key={recent.id}
                    href={pageLink(recent.entity_identifier)}
                    className="truncate rounded-lg border border-subtle p-3 text-13 hover:bg-layer-1"
                  >
                    {(recent.entity_data as { name?: string }).name || "Untitled"}
                  </Link>
                ))}
              </div>
            </section>
          )}
          {model.favorites.length > 0 && (
            <section className="mb-6">
              <h2 className="text-15 mb-2 font-semibold">Favorites</h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {model.favorites.map((page) => (
                  <Link
                    key={page.id}
                    href={pageLink(page.id ?? "")}
                    className="truncate rounded-lg border border-subtle p-3 text-13 hover:bg-layer-1"
                  >
                    {page.name || "Untitled"}
                  </Link>
                ))}
              </div>
            </section>
          )}
          {model.collections.length > 0 && (
            <section>
              <h2 className="text-15 mb-2 font-semibold">Collections</h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {model.collections.map((collection) => (
                  <div key={collection.id} className="rounded-lg border border-subtle p-3 text-13">
                    <p className="font-medium">{collection.name}</p>
                    <p className="mt-1 text-11 text-secondary">
                      {collection.page_count} pages ·{" "}
                      {collection.access === EPageCollectionAccess.PRIVATE ? "Private" : "Public"}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
      {scope.can_create && (
        <PageTemplatesModal
          workspaceSlug={scope.slug}
          isOpen={templatesOpen}
          onClose={() => setTemplatesOpen(false)}
          buildPageHref={({ workspaceSlug, pageId }) => getWikiPagePath(workspaceSlug, pageId)}
          canCreatePage
        />
      )}
    </div>
  );
});
