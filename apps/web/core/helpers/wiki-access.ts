import type { TWikiScope } from "@plane/types";

export const resolveWikiScopeAccess = (scopes: TWikiScope[], requestedSlug: string): TWikiScope | undefined =>
  scopes.find((scope) => scope.slug === requestedSlug && (scope.is_member || scope.is_default));
