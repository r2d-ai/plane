/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { RouteConfigEntry } from "@react-router/dev/routes";
import { layout, route } from "@react-router/dev/routes";

export const extendedRoutes: RouteConfigEntry[] = [
  layout("./(all)/layout.tsx", [
    layout("./(all)/wiki/layout.tsx", [
      route("wiki", "./(all)/wiki/redirect.tsx"),
      route("wiki/personal/:section", "./(all)/wiki/personal/[section]/page.tsx"),
      route("wiki/:workspaceSlug", "./(all)/wiki/[workspaceSlug]/page.tsx"),
      route(
        "wiki/:workspaceSlug/collections/:collectionId",
        "./(all)/wiki/[workspaceSlug]/collections/[collectionId]/page.tsx"
      ),
      route("wiki/:workspaceSlug/:pageId", "./(all)/wiki/[workspaceSlug]/[pageId]/page.tsx"),
    ]),
    route("company-wiki", "./(all)/wiki/legacy-company-redirect.tsx"),
    route("company-wiki/:pageId", "./(all)/wiki/legacy-company-page-redirect.tsx"),
    route(":workspaceSlug/wiki", "./(all)/wiki/legacy-workspace-redirect.tsx"),
    route(":workspaceSlug/wiki/:pageId", "./(all)/wiki/legacy-redirect.tsx"),
  ]),
];
