import { Navigate, useLocation } from "react-router";
import useSWR from "swr";
import { LogoSpinner } from "@/components/common/logo-spinner";
import { resolveDefaultWikiScope } from "../../../core/helpers/wiki-access";
import { resolveLegacyWikiPath } from "../../../core/helpers/wiki-routes";
import { WikiNotConfigured } from "@/layouts/auth-layout/wiki-wrapper";
import { WikiService } from "@/services/wiki.service";

const wikiService = new WikiService();

export default function LegacyWikiRedirect() {
  const location = useLocation();
  const { data: scopes, error, isLoading } = useSWR("WIKI_SCOPES", () => wikiService.fetchScopes());

  // `/:workspaceSlug/wiki` and `/:workspaceSlug/wiki/:pageId` carry the slug in
  // the URL, so they resolve without the scopes response.
  if (!location.pathname.startsWith("/company-wiki")) {
    const path = resolveLegacyWikiPath(location.pathname, "");
    return path ? <Navigate to={`${path}${location.search}`} replace /> : null;
  }

  // `/company-wiki[/:pageId]` resolves against the workspace the API designates
  // via COMPANY_WIKI_WORKSPACE_SLUG (the `is_default` scope) — never against a
  // separate frontend build-time constant.
  if (isLoading || (!scopes && !error))
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );
  if (error) return <div role="alert">Could not load Wiki access. Please try again.</div>;
  const defaultScope = resolveDefaultWikiScope(scopes ?? []);
  if (!defaultScope) return <WikiNotConfigured />;
  const path = resolveLegacyWikiPath(location.pathname, defaultScope.slug);
  return path ? <Navigate to={`${path}${location.search}`} replace /> : null;
}
