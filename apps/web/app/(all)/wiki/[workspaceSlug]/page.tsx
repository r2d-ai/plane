import useSWR from "swr";
import { WikiHome } from "@/components/wiki/home";
import { WikiService } from "@/services/wiki.service";
import type { Route } from "./+types/page";

const wikiService = new WikiService();

export default function WikiHomeRoute({ params }: Route.ComponentProps) {
  const { data: scopes } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());
  const scope = scopes?.find((item) => item.slug === params.workspaceSlug);
  return scope ? <WikiHome scope={scope} /> : null;
}
