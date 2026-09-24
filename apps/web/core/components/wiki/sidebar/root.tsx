import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EPageStoreType, usePageStore } from "../../../hooks/store";
import { useAppRouter } from "../../../hooks/use-app-router";
import { resolveDefaultWikiScope } from "../../../helpers/wiki-access";
import { getWikiPagePath } from "../../../helpers/wiki-routes";
import { WikiService } from "../../../services/wiki.service";
import { buildWikiSidebarModel } from "./model";
import { WikiPersonalSections } from "./personal-sections";
import { WikiWorkspaceSection } from "./workspace-section";

const wikiService = new WikiService();

export const WikiSidebar = observer(function WikiSidebar({ onNavigate }: { onNavigate: () => void }) {
  const { workspaceSlug, pageId } = useParams();
  const { data: scopes, error, isLoading, mutate } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());
  const pageStore = usePageStore(EPageStoreType.WORKSPACE);
  const { t } = useTranslation();
  const router = useAppRouter();
  const [isCreating, setCreating] = useState(false);
  const defaultSlug = resolveDefaultWikiScope(scopes ?? [])?.slug ?? "";
  const model = buildWikiSidebarModel(scopes ?? [], defaultSlug, workspaceSlug, pageId);
  const activeScope = scopes?.find((scope) => scope.slug === workspaceSlug);

  const createPage = async () => {
    if (!activeScope?.can_create || isCreating) return;
    setCreating(true);
    try {
      pageStore.activateScope(activeScope.slug);
      const page = await pageStore.createPage({ name: "Untitled", access: EPageAccess.PUBLIC });
      if (page?.id) {
        router.push(getWikiPagePath(activeScope.slug, page.id));
        onNavigate();
      }
    } catch (creationError) {
      console.error("Could not create Wiki page", creationError);
    } finally {
      setCreating(false);
    }
  };

  return (
    <nav aria-label="Wiki" className="h-full overflow-y-auto px-2 py-3">
      <div className="mb-3 flex items-center justify-between px-2">
        <h2 className="text-14 font-semibold text-primary">{t("wiki.sidebar.title")}</h2>
      </div>
      {activeScope?.can_create && (
        <button
          type="button"
          disabled={isCreating}
          onClick={() => void createPage()}
          className="focus-visible:outline-accent-primary mb-3 w-full rounded-md bg-accent-primary px-3 py-2 text-left text-13 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50"
        >
          + {t("wiki.sidebar.new_page")}
        </button>
      )}
      {isLoading && (
        <div className="space-y-2 p-2" aria-label="Loading Wiki">
          <div className="h-5 w-4/5 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
          <div className="h-5 w-2/3 animate-pulse rounded bg-layer-1 motion-reduce:animate-none" />
        </div>
      )}
      {error && (
        <div role="alert" className="p-2 text-12">
          Could not load Wiki scopes.{" "}
          <button type="button" onClick={() => void mutate()} className="text-accent-primary">
            Retry
          </button>
        </div>
      )}
      {model.defaultScope && (
        <WikiWorkspaceSection
          scope={model.defaultScope}
          label={model.defaultScope.label}
          activeSlug={workspaceSlug}
          activePageId={pageId}
          initiallyExpanded
          isDefaultScope
          onNavigate={onNavigate}
        />
      )}
      {model.workspaces.length > 0 && (
        <div className="my-3 border-t border-subtle pt-2">
          <p className="px-2 py-1 text-11 font-semibold tracking-wide text-tertiary uppercase">
            {t("wiki.sidebar.workspaces")}
          </p>
          {model.workspaces.map((scope) => (
            <WikiWorkspaceSection
              key={scope.id}
              scope={scope}
              label={scope.label}
              activeSlug={workspaceSlug}
              activePageId={pageId}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
      <WikiPersonalSections onNavigate={onNavigate} />
    </nav>
  );
});
