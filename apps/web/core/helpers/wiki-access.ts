import type { TWikiScope } from "@plane/types";

export const resolveWikiScopeAccess = (scopes: TWikiScope[], requestedSlug: string): TWikiScope | undefined =>
  scopes.find((scope) => scope.slug === requestedSlug && (scope.is_member || scope.is_default));

/**
 * The scope the API designates as the Company Wiki (spec §29). Derived from the
 * `is_default` flag in the scopes response, which the backend computes from
 * `COMPANY_WIKI_WORKSPACE_SLUG`. This is the single source of truth — the web
 * app must not require a separate build-time env var that can drift from it.
 */
export const resolveDefaultWikiScope = (scopes: TWikiScope[]): TWikiScope | undefined =>
  scopes.find((scope) => scope.is_default);
