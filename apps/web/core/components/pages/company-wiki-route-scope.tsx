/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
// plane imports
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
// hooks
import { useRouterParams } from "@/hooks/store/use-router-params";

/**
 * Scope the router store to the Company Wiki designated workspace.
 *
 * The Workspace Wiki store and `WorkspacePage` entity read the workspace
 * slug from `router.workspaceSlug`, which is populated from the URL by
 * `StoreWrapper`. Company Wiki is intentionally a canonical route
 * (`/company-wiki/:pageId`) with no workspace slug in the URL, but the
 * entity/store still need to operate against the designated workspace
 * (spec §29.13). This component overrides `router.query.workspaceSlug`
 * for as long as Company Wiki pages are mounted so the existing store,
 * services and entity keep working without forking.
 *
 * The override is removed when the user navigates away (either the
 * designated slug is cleared, or the URL params no longer match Company
 * Wiki surfaces and the outer `StoreWrapper` overwrites the query).
 */
export const CompanyWikiRouteScope = observer(function CompanyWikiRouteScope() {
  const { setQuery, query } = useRouterParams();
  const designatedWorkspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;

  useEffect(() => {
    if (!designatedWorkspaceSlug) return;
    if (query?.workspaceSlug === designatedWorkspaceSlug) return;
    setQuery({ ...query, workspaceSlug: designatedWorkspaceSlug });
  }, [designatedWorkspaceSlug, query, setQuery]);

  return null;
});
