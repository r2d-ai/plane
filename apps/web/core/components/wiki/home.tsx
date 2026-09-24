import { useRef } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { PageIcon } from "@plane/propel/icons";
import type { TWikiScope } from "@plane/types";
import { UserGreetingsView } from "@/components/home/user-greetings";
import { RecentsEmptyState } from "@/components/home/widgets/empty-states";
import { RecentPage } from "@/components/home/widgets/recents/page";
import { StickiesWidget } from "@/components/stickies/widget";
import { useUser } from "@/hooks/store/user";
import { useWikiNavigation } from "../../hooks/store/use-wiki-navigation";
import { getWikiPagePath } from "../../helpers/wiki-routes";
import { WorkspacePageService } from "../../services/page/workspace-page.service";
import { WorkspaceService } from "../../services/workspace.service";
import { buildWikiHomeModel } from "./home-model";

const workspaceService = new WorkspaceService();
const workspacePageService = new WorkspacePageService();

export const WikiHome = observer(function WikiHome({ scope }: { scope: TWikiScope }) {
  const navigation = useWikiNavigation();
  const { data: currentUser } = useUser();
  const searchParams = useSearchParams();
  const archivedView = searchParams.get("view") === "archived";
  const recentRef = useRef<HTMLDivElement>(null);

  const {
    data: recents,
    error: recentsError,
    isLoading: recentsLoading,
    mutate: mutateRecents,
  } = useSWR(scope.is_member && !archivedView ? `WIKI_RECENTS_${scope.slug}` : null, () =>
    workspaceService.fetchWorkspaceRecents(scope.slug, "workspace_page")
  );

  const {
    error: navigationError,
    isLoading: navigationLoading,
    mutate: mutateNavigation,
  } = useSWR(!scope.is_member && !archivedView ? `WIKI_HOME_SCOPE_${scope.slug}` : null, () => navigation.fetchScope(scope.slug));

  const scopeData = navigation.getScope(scope.slug);
  const model = buildWikiHomeModel({
    scope,
    pages: scopeData.pageIds.map((id) => scopeData.pagesById[id]).filter((page) => !!page),
  });

  const {
    data: archivedPages,
    error: archivedError,
    isLoading: archivedLoading,
    mutate: mutateArchived,
  } = useSWR(archivedView ? `WIKI_ARCHIVED_${scope.slug}` : null, () =>
    workspacePageService.fetchArchived(scope.slug)
  );

  if (archivedView) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="mx-auto w-full max-w-[800px] px-6 py-8">
          <h1 className="text-20 font-semibold text-primary">Archived</h1>
          <p className="mt-1 text-13 text-secondary">Pages archived from this Wiki.</p>

          <div className="mt-6">
            {archivedLoading && (
              <div className="space-y-2" aria-label="Loading archived Wiki pages">
                <div className="h-10 w-full animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
                <div className="h-10 w-4/5 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
              </div>
            )}
            {archivedError && (
              <div className="rounded-lg bg-layer-1 p-6 text-center text-13 text-secondary">
                <p>Could not load archived Wiki pages.</p>
                <button type="button" onClick={() => void mutateArchived()} className="mt-2 text-accent-primary">
                  Retry
                </button>
              </div>
            )}
            {!archivedLoading && !archivedError && (archivedPages?.length ?? 0) === 0 && (
              <div className="rounded-lg bg-layer-1 p-8 text-center text-13 text-secondary">No archived pages.</div>
            )}
            {!archivedLoading &&
              !archivedError &&
              archivedPages?.map((page) => (
                <Link
                  key={page.id}
                  href={getWikiPagePath(scope.slug, page.id ?? "")}
                  className="flex items-center gap-3 border-b border-subtle px-2 py-3 text-13 text-primary hover:bg-layer-1"
                >
                  <span className="grid size-8 flex-shrink-0 place-items-center rounded-sm bg-layer-2">
                    <PageIcon className="size-4 text-tertiary" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">{page.name || "Untitled"}</span>
                </Link>
              ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[800px] px-6 pb-10">
        {currentUser && <UserGreetingsView user={currentUser} />}

        <section ref={recentRef} className="py-4">
          <div className="mb-4 text-14 font-semibold text-tertiary">
            {scope.is_member ? "Recents" : "Recently updated"}
          </div>

          {scope.is_member ? (
            <>
              {recentsLoading && (
                <div className="space-y-2 rounded-lg bg-layer-1 p-4" aria-label="Loading Wiki recents">
                  <div className="h-8 w-full animate-pulse rounded bg-layer-2 motion-reduce:animate-none" />
                  <div className="h-8 w-4/5 animate-pulse rounded bg-layer-2 motion-reduce:animate-none" />
                </div>
              )}
              {recentsError && (
                <div className="rounded-lg bg-layer-1 p-6 text-center text-13 text-secondary">
                  <p>Could not load recent Wiki pages.</p>
                  <button type="button" onClick={() => void mutateRecents()} className="mt-2 text-accent-primary">
                    Retry
                  </button>
                </div>
              )}
              {!recentsLoading && !recentsError && (recents?.length ?? 0) === 0 && <RecentsEmptyState type="page" />}
              {!recentsLoading &&
                !recentsError &&
                recents
                  ?.filter((activity) => activity.entity_name === "workspace_page" && activity.entity_data)
                  .slice(0, 6)
                  .map((activity) => (
                    <RecentPage
                      key={activity.id}
                      activity={activity}
                      ref={recentRef}
                      workspaceSlug={scope.slug}
                    />
                  ))}
            </>
          ) : (
            <>
              {navigationLoading && scopeData.status !== "loaded" && (
                <div className="space-y-2 rounded-lg bg-layer-1 p-4" aria-label="Loading recently updated Wiki pages">
                  <div className="h-8 w-full animate-pulse rounded bg-layer-2 motion-reduce:animate-none" />
                  <div className="h-8 w-4/5 animate-pulse rounded bg-layer-2 motion-reduce:animate-none" />
                </div>
              )}
              {navigationError && scopeData.status !== "loaded" && (
                <div className="rounded-lg bg-layer-1 p-6 text-center text-13 text-secondary">
                  <p>Could not load recently updated Wiki pages.</p>
                  <button type="button" onClick={() => void mutateNavigation()} className="mt-2 text-accent-primary">
                    Retry
                  </button>
                </div>
              )}
              {scopeData.status === "loaded" && model.recentlyUpdated.length === 0 && (
                <RecentsEmptyState type="page" />
              )}
              {scopeData.status === "loaded" &&
                model.recentlyUpdated.map((page) => (
                  <Link
                    key={page.id}
                    href={getWikiPagePath(scope.slug, page.id ?? "")}
                    className="flex items-center gap-3 rounded-lg px-2 py-3 text-13 text-primary hover:bg-layer-1"
                  >
                    <span className="grid size-8 flex-shrink-0 place-items-center rounded-sm bg-layer-2">
                      <PageIcon className="size-4 text-tertiary" />
                    </span>
                    <span className="min-w-0 flex-1 truncate">{page.name || "Untitled"}</span>
                  </Link>
                ))}
            </>
          )}
        </section>

        {scope.is_member && (
          <div className="border-t border-subtle py-6">
            <StickiesWidget />
          </div>
        )}
      </div>
    </div>
  );
});
