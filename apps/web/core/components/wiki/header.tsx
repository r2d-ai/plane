import { observer } from "mobx-react";
import { Breadcrumbs, Header } from "@plane/ui";
import { PageIcon } from "@plane/propel/icons";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { PageHeaderActions } from "@/components/pages/header/actions";
import { PageSyncingBadge } from "@/components/pages/header/syncing-badge";
import { WikiHierarchyBreadcrumb } from "@/components/pages/hierarchy-breadcrumb";
import { EPageStoreType, usePage, usePageStore } from "../../hooks/store";
import { getWikiHomePath, getWikiPagePath } from "../../helpers/wiki-routes";

export const WikiDetailHeader = observer(function WikiDetailHeader({
  workspaceSlug,
  pageId,
}: {
  workspaceSlug: string;
  pageId: string;
}) {
  const candidatePage = usePage({ pageId, storeType: EPageStoreType.WORKSPACE });
  const { activeWorkspaceSlug } = usePageStore(EPageStoreType.WORKSPACE);
  const page = activeWorkspaceSlug === workspaceSlug ? candidatePage : undefined;
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label="Wiki"
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
              <BreadcrumbLink label={page?.name || "Untitled"} href={getWikiPagePath(workspaceSlug, pageId)} isLast />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {page && (
        <Header.RightItem>
          <PageSyncingBadge syncStatus={page.isSyncingWithServer} />
          <PageHeaderActions page={page} storeType={EPageStoreType.WORKSPACE} />
        </Header.RightItem>
      )}
    </Header>
  );
});
