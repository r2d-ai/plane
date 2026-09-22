/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment } from "react";
import { observer } from "mobx-react";
// plane imports
import { PageIcon } from "@plane/propel/icons";
import type { TLogoProps } from "@plane/types";
import { Breadcrumbs } from "@plane/ui";
import { getPageName } from "@plane/utils";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { SwitcherIcon } from "@/components/common/switcher-label";
// plane web imports
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";

/** Ancestors shown before collapsing the middle of a deep chain into "…". */
const MAX_VISIBLE_ANCESTORS = 4;

type TProps = {
  /** Slug used by {@link buildPageHref}; Company Wiki passes an empty string. */
  workspaceSlug: string;
  pageId: string;
  /** Build the absolute URL of an ancestor page. */
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
};

export type TWikiAncestor = { id: string; name?: string; logo_props?: TLogoProps };

/**
 * @description Hierarchy breadcrumb (WIKI-04a §7.3).
 *
 * Renders the ancestor chain (root → immediate parent) of the active Wiki page
 * as `Breadcrumbs.Item`s so it can be embedded inside a parent `Breadcrumbs`.
 * The current page is rendered by the header; this component never renders it.
 * Deep chains collapse their middle segment into an overflow "…" marker.
 * Malformed cycles are broken by the store's visited-set guard.
 */
export const WikiHierarchyBreadcrumb = observer(function WikiHierarchyBreadcrumb(props: TProps) {
  const { workspaceSlug, pageId, buildPageHref } = props;
  const { getPageParentChain } = usePageStore(EPageStoreType.WORKSPACE);
  const currentPage = usePage({ pageId, storeType: EPageStoreType.WORKSPACE });
  const ancestors = (getPageParentChain(pageId) ?? []) as TWikiAncestor[];

  if (!currentPage || ancestors.length === 0) return null;

  const visibleAncestors: (TWikiAncestor | null)[] =
    ancestors.length > MAX_VISIBLE_ANCESTORS
      ? [...ancestors.slice(0, MAX_VISIBLE_ANCESTORS - 1), null, ...ancestors.slice(-1)]
      : ancestors;

  return (
    <Fragment>
      {visibleAncestors.map((ancestor) => {
        if (!ancestor) {
          return (
            <Breadcrumbs.Item
              key="wiki-hierarchy-overflow"
              component={<span className="px-1 text-13 text-tertiary">…</span>}
            />
          );
        }
        return (
          <Breadcrumbs.Item
            key={ancestor.id}
            component={
              <BreadcrumbLink
                label={getPageName(ancestor.name)}
                href={buildPageHref ? buildPageHref({ workspaceSlug, pageId: ancestor.id }) : undefined}
                icon={<SwitcherIcon logo_props={ancestor.logo_props} LabelIcon={PageIcon} size={16} />}
              />
            }
          />
        );
      })}
    </Fragment>
  );
});
