import { Navigate, useLocation } from "react-router";
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { resolveLegacyWikiPath } from "../../../core/helpers/wiki-routes";
import { WikiNotConfigured } from "@/layouts/auth-layout/wiki-wrapper";

export default function LegacyWikiRedirect() {
  const location = useLocation();
  if (location.pathname.startsWith("/company-wiki") && !COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG) {
    return <WikiNotConfigured />;
  }
  const path = resolveLegacyWikiPath(location.pathname, COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG);
  return path ? <Navigate to={`${path}${location.search}`} replace /> : null;
}
