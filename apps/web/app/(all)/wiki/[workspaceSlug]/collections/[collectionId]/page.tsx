import useSWR from "swr";
import { WikiCollectionView } from "@/components/wiki/collection-view";
import { WikiService } from "@/services/wiki.service";
import type { Route } from "./+types/page";

const wikiService = new WikiService();

export default function WikiCollectionRoute({ params }: Route.ComponentProps) {
  const { data: scopes } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());
  const scope = scopes?.find((item) => item.slug === params.workspaceSlug);

  return scope ? <WikiCollectionView scope={scope} collectionId={params.collectionId} /> : null;
}
