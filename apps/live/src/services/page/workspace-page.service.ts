/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AppError } from "@/lib/errors";
import { PageService } from "./extended.service";

interface WorkspacePageServiceParams {
  workspaceSlug: string | null;
  projectId?: string | null;
  cookie: string | null;
  [key: string]: unknown;
}

/**
 * Live service for Workspace Wiki pages (Company Wiki included).
 *
 * Wiki pages are ordinary Page rows scoped to a workspace (`is_global=True`),
 * so they reuse the existing Page service against the workspace-scoped routes
 * under `/api/workspaces/{workspaceSlug}` (spec §29.6). Company Wiki is the
 * same service with `workspaceSlug = COMPANY_WIKI_WORKSPACE_SLUG`; there is no
 * separate instance service or document type.
 *
 * `projectId` is optional and intentionally ignored for the base path: a
 * workspace page is not project-scoped. Asset resolution still accepts it so
 * the shared core service signature stays unchanged.
 */
export class WorkspacePageService extends PageService {
  protected basePath: string;

  constructor(params: WorkspacePageServiceParams) {
    super();
    const { workspaceSlug } = params;
    // workspace slug is mandatory for workspace_page (spec §5.4)
    if (!workspaceSlug) throw new AppError("Missing required fields.");
    // validate cookie
    if (!params.cookie) throw new AppError("Cookie is required.");
    // set cookie
    this.setHeader("Cookie", params.cookie);
    // set base path
    this.basePath = `/api/workspaces/${workspaceSlug}`;
  }
}
