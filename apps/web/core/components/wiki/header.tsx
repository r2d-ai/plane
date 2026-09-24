import { useState } from "react";
import { observer } from "mobx-react";
import { FolderPlus } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Breadcrumbs, Header } from "@plane/ui";
import { PageIcon } from "@plane/propel/icons";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { PageHeaderActions } from "@/components/pages/header/actions";
import { PageSyncingBadge } from "@/components/pages/header/syncing-badge";
import { WikiHierarchyBreadcrumb } from "@/components/pages/hierarchy-breadcrumb";
import { MovePageToCollectionModal } from "@/components/pages/collections";
import { EPageStoreType, usePage, usePageStore } from "../../hooks/store";
import { useWikiNavigation } from "../../hooks/store/use-wiki-navigation";
import { getWikiHomePath, getWikiPagePath } from "../../helpers/wiki-routes";

export const WikiDetailHeader = observer(function WikiDetailHeader({
  workspaceSlug,
  pageId,
}: {
  workspaceSlug: string;
  pageId: string;
}) {
  const { t } = useTranslation();
  const navigation = useWikiNavigation();
  const [collectionModalOpen, setCollectionModalOpen] = useState(false);
  const candidatePage = usePage({ pageId, storeType: EPageStoreType.WORKSPACE });
  const { activeWorkspaceSlug } = usePageStore(EPageStoreType.WORKSPACE);
  const page = activeWorkspaceSlug === workspaceSlug ? candidatePage : undefined;
  return (
    <>
      <Header>
        <Header.LeftItem>
          <Breadcrumbs>
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label={t("wiki.sidebar.title")}
                  href={getWikiHomePath(workspaceSlug)}
                  icon={<PageIcon className="h-4 w-4 text-tertiary" />}
                />
              }
            />
            <WikiHierarchyBreadcrumb
              workspaceSlug={workspaceSlug}
              pageId={pageId}
              buildPageHref={({ workspaceSlug: slug, pageId: id }) => getWikiPagePath(slug, id)}
            />
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label={page?.name || t("wiki.untitled")}
                  href={getWikiPagePath(workspaceSlug, pageId)}
                  isLast
                />
              }
              isLast
            />
          </Breadcrumbs>
        </Header.LeftItem>
        {page && (
          <Header.RightItem>
            <PageSyncingBadge syncStatus={page.isSyncingWithServer} />
            {page.isContentEditable && (
              <button
                type="button"
                title={t("wiki.collections.move_page_to_collection")}
                aria-label={t("wiki.collections.move_page_to_collection")}
                onClick={() => setCollectionModalOpen(true)}
                className="focus-visible:outline-accent-primary grid size-7 place-items-center rounded text-secondary hover:bg-layer-1 hover:text-primary focus-visible:outline-2"
              >
                <FolderPlus className="size-4" />
              </button>
            )}
            <PageHeaderActions page={page} storeType={EPageStoreType.WORKSPACE} />
          </Header.RightItem>
        )}
      </Header>
      {page && (
        <MovePageToCollectionModal
          isOpen={collectionModalOpen}
          onClose={() => setCollectionModalOpen(false)}
          workspaceSlug={workspaceSlug}
          pageId={pageId}
          onMoved={async (affectedCollectionId) => {
            await navigation.invalidateScope(workspaceSlug, affectedCollectionId ? [affectedCollectionId] : undefined);
          }}
        />
      )}
    </>
  );
});
