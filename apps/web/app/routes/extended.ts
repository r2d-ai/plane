/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RouteConfigEntry } from "@react-router/dev/routes";
import { layout, route } from "@react-router/dev/routes";

/**
 * Workspace Wiki + Company Wiki web routes (WIKI-03a).
 *
 * Routes are registered through the existing extension seam so the upstream
 * core routes file stays untouched. The merge helper resolves these alongside
 * the core routes at build time, deep-merging by `file` so the wiki children
 * attach to the workspace layout already declared in core.
 *
 * - `/:workspaceSlug/wiki` and `/:workspaceSlug/wiki/:pageId` live inside the
 *   existing `[workspaceSlug]`/(projects) layout so they pick up the workspace
 *   sidebar and authentication gate.
 * - `/company-wiki` and `/company-wiki/:pageId` are top-level authenticated
 *   routes that resolve `COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG` and render
 *   the workspace Wiki UI against that workspace (spec §29.1, §29.13).
 */
export const extendedRoutes: RouteConfigEntry[] = [
  // Workspace Wiki — attach to the existing workspace layout via file key
  layout("./(all)/[workspaceSlug]/(projects)/layout.tsx", [
    layout("./(all)/[workspaceSlug]/(projects)/wiki/(list)/layout.tsx", [
      route(":workspaceSlug/wiki", "./(all)/[workspaceSlug]/(projects)/wiki/(list)/page.tsx"),
    ]),
    layout("./(all)/[workspaceSlug]/(projects)/wiki/(detail)/layout.tsx", [
      route(":workspaceSlug/wiki/:pageId", "./(all)/[workspaceSlug]/(projects)/wiki/(detail)/[pageId]/page.tsx"),
    ]),
  ]),
  // Company Wiki — standalone authenticated route (no workspace in URL).
  layout("./(all)/layout.tsx", [
    layout("./(all)/company-wiki/(list)/layout.tsx", [route("company-wiki", "./(all)/company-wiki/(list)/page.tsx")]),
    layout("./(all)/company-wiki/(detail)/layout.tsx", [
      route("company-wiki/:pageId", "./(all)/company-wiki/(detail)/[pageId]/page.tsx"),
    ]),
  ]),
];
