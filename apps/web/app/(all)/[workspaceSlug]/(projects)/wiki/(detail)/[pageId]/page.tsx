import { WorkspaceWikiPageView } from "@/components/wiki/page-view";

export default function LegacyWorkspaceWikiPage({ params }: { params: { workspaceSlug: string; pageId: string } }) {
  return <WorkspaceWikiPageView workspaceSlug={params.workspaceSlug} pageId={params.pageId} />;
}
