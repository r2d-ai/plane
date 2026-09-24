import type { TWikiScope } from "@plane/types";
import { getWikiHomePath, getWikiPagePath } from "../../../helpers/wiki-routes";
import type { IWikiNavigationStore } from "../../../store/wiki/wiki-navigation.store";

export type WikiSidebarScope = TWikiScope & { label: string; href: string; active: boolean };

export function buildWikiSidebarModel(
  scopes: TWikiScope[],
  defaultSlug: string,
  activeSlug?: string,
  _activePageId?: string
): {
  defaultScope: WikiSidebarScope | undefined;
  workspaces: WikiSidebarScope[];
  pageHref: (slug: string, pageId: string) => string;
} {
  const available = scopes.filter((scope) => scope.is_default || scope.is_member);
  const decorate = (scope: TWikiScope): WikiSidebarScope => ({
    ...scope,
    label: scope.name,
    href: getWikiHomePath(scope.slug),
    active: scope.slug === activeSlug,
  });
  const defaultScope = available.find((scope) => scope.slug === defaultSlug && scope.is_default);
  return {
    defaultScope: defaultScope ? decorate(defaultScope) : undefined,
    workspaces: available.filter((scope) => scope.slug !== defaultSlug && scope.is_member).map(decorate),
    pageHref: getWikiPagePath,
  };
}

export async function expandWikiWorkspace(store: IWikiNavigationStore, slug: string): Promise<void> {
  if (store.getScope(slug).status === "idle" || store.getScope(slug).status === "error") {
    await store.fetchScope(slug);
  }
}
