/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * RD-482 / C.8 — the legacy `/:workspaceSlug/dashboards/:dashboardId` route.
 *
 * Spec §4.1: the route leaves navigation and, since the v3 dashboard is a
 * workspace view rather than a row, every id resolves to the one dashboard.
 * The route object stays registered on purpose — dropping it turns live
 * bookmarks into 404s — so this asserts the redirect, not a deletion.
 */

import { describe, expect, test, vi } from "vitest";

vi.mock("react-router", () => ({
  redirect: (url: string) => new Response(null, { status: 302, headers: { Location: url } }),
}));

import { clientLoader as legacyDashboardClientLoader } from "../../../app/(all)/[workspaceSlug]/(projects)/dashboards/[dashboardId]/page";
import { workspaceDashboardRoutePaths } from "../../../app/routes/workspace-dashboards";

const redirectTo = (params: { workspaceSlug: string; dashboardId: string }): string => {
  try {
    legacyDashboardClientLoader({ params } as never);
    expect.fail("expected redirect");
  } catch (error) {
    if (!(error instanceof Response)) throw error;
    return error.headers.get("Location") ?? "";
  }
  return "";
};

describe("legacy dashboard id route", () => {
  test("any id redirects to the single workspace dashboard", () => {
    expect(redirectTo({ workspaceSlug: "acme", dashboardId: "0195f0c2-1111-7000-8000-000000000000" })).toBe(
      "/acme/dashboards/"
    );
    expect(redirectTo({ workspaceSlug: "acme", dashboardId: "does-not-exist" })).toBe("/acme/dashboards/");
  });

  test("the route stays registered so old links redirect instead of 404", () => {
    expect(workspaceDashboardRoutePaths).toContain(":workspaceSlug/dashboards/:dashboardId");
  });
});
