/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
// services
import { WorkspacePageService } from "@/services/page/workspace-page.service";
// types
import type { TDocumentPayload } from "@plane/types";

const basePathOf = (service: unknown): string => (service as { basePath: string }).basePath;

const createService = (
  params: { workspaceSlug?: string | null; projectId?: string | null; cookie?: string | null } = {}
) =>
  new WorkspacePageService({
    workspaceSlug: "acme",
    cookie: "session-cookie",
    ...params,
  });

describe("WorkspacePageService", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requires a workspace slug", () => {
    expect(() => createService({ workspaceSlug: null })).toThrow(/Missing required fields/);
  });

  it("requires a cookie", () => {
    expect(() => createService({ cookie: null })).toThrow(/Cookie is required/);
  });

  it("targets the workspace-scoped page API and forwards the cookie", () => {
    const service = createService({ projectId: "ignored-project" });

    expect(basePathOf(service)).toBe("/api/workspaces/acme");
    expect(service.getHeader()).toEqual({ Cookie: "session-cookie" });
  });

  it("fetches a page from the workspace page route", async () => {
    const service = createService();
    const page = { id: "page-1", name: "Wiki Home" };
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({ data: page } as never);

    await expect(service.fetchDetails("page-1")).resolves.toBe(page);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/workspaces/acme/pages/page-1/",
      expect.objectContaining({ headers: { Cookie: "session-cookie" } })
    );
  });

  it("fetches the description binary from the workspace page route", async () => {
    const service = createService();
    const buffer = Buffer.from("binary");
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({ data: buffer } as never);

    await expect(service.fetchDescriptionBinary("page-1")).resolves.toBe(buffer);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/workspaces/acme/pages/page-1/description/",
      expect.objectContaining({ responseType: "arraybuffer" })
    );
  });

  it("persists description updates to the workspace page route", async () => {
    const service = createService();
    const payload: TDocumentPayload = {
      description_binary: "binary",
      description_html: "<p>hi</p>",
      description_json: { type: "doc" },
    };
    const patchSpy = vi.spyOn(service, "patch").mockResolvedValue({ data: {} } as never);

    await service.updateDescriptionBinary("page-1", payload);
    expect(patchSpy).toHaveBeenCalledWith("/api/workspaces/acme/pages/page-1/description/", payload, expect.anything());
  });

  it("persists title/property updates to the workspace page route", async () => {
    const service = createService({ projectId: "ignored-project" });
    const patchSpy = vi.spyOn(service, "patch").mockResolvedValue({ data: {} } as never);

    await service.updatePageProperties("page-1", { data: { name: "Renamed" } });
    expect(patchSpy).toHaveBeenCalledWith("/api/workspaces/acme/pages/page-1/", { name: "Renamed" }, expect.anything());
  });

  it("keeps every request inside the connection workspace scope (no BOLA across workspaces)", async () => {
    const service = createService({ workspaceSlug: "acme" });
    const getSpy = vi.spyOn(service, "get").mockResolvedValue({ data: Buffer.from("x") } as never);

    // A page UUID from another workspace can only be addressed under this
    // connection's slug, so the API resolves it as not-found instead of
    // leaking a foreign document.
    await service.fetchDescriptionBinary("11111111-2222-3333-4444-555555555555");
    expect(getSpy).toHaveBeenCalledWith(
      "/api/workspaces/acme/pages/11111111-2222-3333-4444-555555555555/description/",
      expect.anything()
    );
  });

  it("resolves workspace-scoped assets without a project segment", async () => {
    const service = createService();
    const getSpy = vi
      .spyOn(service, "get")
      .mockResolvedValue({ status: 302, headers: { location: "https://cdn.example/asset" } } as never);

    await expect(service.resolveImageAssetUrl("acme", "asset-1", null)).resolves.toBe("https://cdn.example/asset");
    expect(getSpy).toHaveBeenCalledWith(
      "/api/assets/v2/workspaces/acme/asset-1/?disposition=inline",
      expect.anything()
    );
  });
});
