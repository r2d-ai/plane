import useSWR from "swr";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";
import { WikiDetailHeader } from "@/components/wiki/header";
import { WorkspaceWikiPageView } from "@/components/wiki/page-view";
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { Route } from "./+types/page";

export default function WikiDetailRoute({ params }: Route.ComponentProps) {
  const { workspaceSlug, pageId } = params;
  const { fetchPagesList } = usePageStore(EPageStoreType.WORKSPACE);
  useSWR(`WORKSPACE_PAGES_${workspaceSlug}`, () => fetchPagesList(workspaceSlug));
  return (
    <>
      <AppHeader header={<WikiDetailHeader workspaceSlug={workspaceSlug} pageId={pageId} />} />
      <ContentWrapper>
        <WorkspaceWikiPageView key={`${workspaceSlug}:${pageId}`} workspaceSlug={workspaceSlug} pageId={pageId} />
      </ContentWrapper>
    </>
  );
}
