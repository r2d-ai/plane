import { Navigate } from "react-router";
import useSWR from "swr";
import { LogoSpinner } from "@/components/common/logo-spinner";
import { resolveDefaultWikiScope } from "../../../core/helpers/wiki-access";
import { getDefaultWikiPath } from "../../../core/helpers/wiki-routes";
import { WikiNotConfigured } from "@/layouts/auth-layout/wiki-wrapper";
import { WikiService } from "@/services/wiki.service";

const wikiService = new WikiService();

export default function WikiRootRedirect() {
  const { data: scopes, error, isLoading } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());
  if (isLoading || (!scopes && !error))
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );
  if (error) return <div role="alert">Could not load Wiki access. Please try again.</div>;
  const defaultScope = resolveDefaultWikiScope(scopes ?? []);
  if (!defaultScope) return <WikiNotConfigured />;
  return <Navigate to={getDefaultWikiPath(defaultScope.slug)} replace />;
}
