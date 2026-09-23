/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * WIKI-06c realtime sharing permission matrix (plan §9.5, spec §22.6).
 *
 * The live layer never decides authorization itself: `WorkspacePageService`
 * loads and persists through the workspace Page API, and `storeDocument` turns
 * a forbidden persistence (401/403/404) into a force-close (WIKI-02 §5.5).
 * These tests drive the real handler + service chain against an HTTP layer that
 * answers per share role, so the matrix is pinned end to end at the live seam:
 *
 *   VIEW    -> load allowed, persist forbidden
 *   COMMENT -> load allowed, persist forbidden
 *   EDIT    -> load + persist allowed
 *   revoked -> load + persist forbidden (session force-closed)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
// types
import type { HocusPocusServerContext } from "@/types";
import { CloseCode, ForceCloseReason } from "@/types/admin-commands";

const { broadcastErrorMock } = vi.hoisted(() => ({ broadcastErrorMock: vi.fn() }));
const { forceCloseMock } = vi.hoisted(() => ({ forceCloseMock: vi.fn() }));

vi.mock("@/utils/broadcast-error", () => ({ broadcastError: broadcastErrorMock }));
vi.mock("@/extensions/force-close-handler", () => ({ forceCloseDocumentAcrossServers: forceCloseMock }));
vi.mock("@plane/editor", () => ({
  getAllDocumentFormatsFromDocumentEditorBinaryData: vi.fn(() => ({
    contentBinaryEncoded: "encoded-binary",
    contentHTML: "<p>converted</p>",
    contentJSON: { type: "doc" },
  })),
  getBinaryDataFromDocumentEditorHTMLString: vi.fn(() => new Uint8Array([1, 2, 3])),
}));

import { fetchDocument, storeDocument } from "@/extensions/database";
import { AppError } from "@/lib/errors";
import { ProjectPageService } from "@/services/page/project-page.service";
import { WorkspacePageService } from "@/services/page/workspace-page.service";

const makeContext = (overrides: Partial<HocusPocusServerContext> = {}): HocusPocusServerContext => ({
  cookie: "session-cookie",
  documentType: "workspace_page",
  projectId: null,
  userId: "user-1",
  workspaceSlug: "acme",
  ...overrides,
});

const instance = { documents: new Map() } as never;

/** An axios-shaped failure so AppError extracts the HTTP status. */
const httpError = (status: number) =>
  Object.assign(new Error(`HTTP ${status}`), {
    isAxiosError: true,
    response: { status, data: { error: "nope" } },
    config: { method: "patch", url: "/api/workspaces/acme/pages/page-1/description/" },
  });

const getSpy = () => vi.spyOn(WorkspacePageService.prototype, "get");
const patchSpy = () => vi.spyOn(WorkspacePageService.prototype, "patch");

describe("realtime sharing permission matrix", () => {
  beforeEach(() => {
    broadcastErrorMock.mockReset();
    forceCloseMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("VIEW: loads the document but cannot persist (session force-closed)", async () => {
    getSpy().mockResolvedValue({ data: Buffer.from([7, 7, 7]) } as never);
    patchSpy().mockRejectedValue(httpError(403));

    const loaded = await fetchDocument({
      context: makeContext(),
      documentName: "page-1",
      instance,
    } as never);
    expect(Array.from(loaded as Uint8Array)).toEqual([7, 7, 7]);

    await expect(
      storeDocument({ context: makeContext(), state: new Uint8Array([1]), documentName: "page-1", instance } as never)
    ).resolves.toBeUndefined();
    expect(forceCloseMock).toHaveBeenCalledWith(
      instance,
      "page-1",
      ForceCloseReason.SECURITY_VIOLATION,
      CloseCode.SECURITY_VIOLATION
    );
    expect(broadcastErrorMock).toHaveBeenCalledWith(
      instance,
      "page-1",
      "You no longer have permission to edit this page. Live editing has been stopped.",
      "store",
      expect.anything(),
      undefined,
      true
    );
  });

  it("COMMENT: loads the document but cannot edit the document body", async () => {
    getSpy().mockResolvedValue({ data: Buffer.from([1, 2]) } as never);
    patchSpy().mockRejectedValue(httpError(403));

    await expect(
      fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never)
    ).resolves.toBeInstanceOf(Uint8Array);

    await expect(
      storeDocument({ context: makeContext(), state: new Uint8Array([1]), documentName: "page-1", instance } as never)
    ).resolves.toBeUndefined();
    expect(forceCloseMock).toHaveBeenCalledTimes(1);
  });

  it("EDIT: loads and persists without a force-close", async () => {
    getSpy().mockResolvedValue({ data: Buffer.from([3, 3]) } as never);
    patchSpy().mockResolvedValue({ data: { message: "Updated successfully" } } as never);

    await fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never);
    await expect(
      storeDocument({ context: makeContext(), state: new Uint8Array([1]), documentName: "page-1", instance } as never)
    ).resolves.toBeUndefined();

    expect(patchSpy()).toHaveBeenCalledWith(
      "/api/workspaces/acme/pages/page-1/description/",
      expect.objectContaining({ description_binary: "encoded-binary" }),
      expect.anything()
    );
    expect(forceCloseMock).not.toHaveBeenCalled();
  });

  it("revoked share: denies the next load and force-closes the next write", async () => {
    // Access revocation makes the private page resolve as not-found.
    getSpy().mockRejectedValue(httpError(404));
    patchSpy().mockRejectedValue(httpError(404));

    await expect(fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never)).rejects.toThrow(
      AppError
    );

    await expect(
      storeDocument({ context: makeContext(), state: new Uint8Array([1]), documentName: "page-1", instance } as never)
    ).resolves.toBeUndefined();
    expect(forceCloseMock).toHaveBeenCalledTimes(1);
  });

  it("project_page realtime behavior is unchanged on a forbidden write (regression)", async () => {
    vi.spyOn(ProjectPageService.prototype, "patch").mockRejectedValue(httpError(403));

    await expect(
      storeDocument({
        context: makeContext({ documentType: "project_page", projectId: "project-1" }),
        state: new Uint8Array([1]),
        documentName: "page-1",
        instance,
      } as never)
    ).rejects.toThrow(AppError);
    expect(forceCloseMock).not.toHaveBeenCalled();
  });
});
