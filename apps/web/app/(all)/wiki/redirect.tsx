import { Navigate } from "react-router";
import useSWR from "swr";
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { LogoSpinner } from "@/components/common/logo-spinner";
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
  const defaultScope = scopes?.find(
    (scope) => scope.is_default && scope.slug === COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG
  );
  if (!defaultScope) return <WikiNotConfigured />;
  return <Navigate to={getDefaultWikiPath(defaultScope.slug)} replace />;
}
