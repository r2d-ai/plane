/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
// types
import type { HocusPocusServerContext } from "@/types";
import { CloseCode, ForceCloseReason } from "@/types/admin-commands";

const { getPageServiceMock } = vi.hoisted(() => ({ getPageServiceMock: vi.fn() }));
const { broadcastErrorMock } = vi.hoisted(() => ({ broadcastErrorMock: vi.fn() }));
const { forceCloseMock } = vi.hoisted(() => ({ forceCloseMock: vi.fn() }));

vi.mock("@/services/page/handler", () => ({ getPageService: getPageServiceMock }));
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

const makeContext = (overrides: Partial<HocusPocusServerContext> = {}): HocusPocusServerContext => ({
  cookie: "session-cookie",
  documentType: "workspace_page",
  projectId: null,
  userId: "user-1",
  workspaceSlug: "acme",
  ...overrides,
});

const makeService = (overrides: Record<string, unknown> = {}) => ({
  fetchDescriptionBinary: vi.fn(),
  fetchDetails: vi.fn(),
  updateDescriptionBinary: vi.fn(),
  fetchUserMentions: vi.fn(),
  updatePageProperties: vi.fn(),
  resolveImageAssetUrl: vi.fn(),
  resolveImageAssetUrls: vi.fn(),
  ...overrides,
});

const httpError = (status: number) =>
  Object.assign(new Error(`HTTP ${status}`), {
    isAxiosError: true,
    response: { status, data: { error: "nope" } },
    config: { method: "patch", url: "/api/workspaces/acme/pages/page-1/description/" },
  });

const instance = { documents: new Map() } as never;

describe("fetchDocument", () => {
  beforeEach(() => {
    getPageServiceMock.mockReset();
    broadcastErrorMock.mockReset();
  });

  it("loads an existing workspace page through the workspace service", async () => {
    const service = makeService({
      fetchDescriptionBinary: vi.fn().mockResolvedValue(Buffer.from([9, 8, 7])),
    });
    getPageServiceMock.mockReturnValue(service);

    const result = await fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never);

    expect(Array.from(result as Uint8Array)).toEqual([9, 8, 7]);
    expect(getPageServiceMock).toHaveBeenCalledWith(
      "workspace_page",
      expect.objectContaining({ workspaceSlug: "acme" })
    );
    expect(service.updateDescriptionBinary).not.toHaveBeenCalled();
  });

  it("initializes HTML to a Yjs binary and persists it when a page has no binary yet", async () => {
    const service = makeService({
      fetchDescriptionBinary: vi.fn().mockResolvedValue(Buffer.alloc(0)),
      fetchDetails: vi.fn().mockResolvedValue({ description_html: "<p>hi</p>", name: "Wiki Home" }),
      updateDescriptionBinary: vi.fn().mockResolvedValue({ message: "Updated successfully" }),
    });
    getPageServiceMock.mockReturnValue(service);

    const result = await fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never);

    expect(Array.from(result as Uint8Array)).toEqual([1, 2, 3]);
    expect(service.updateDescriptionBinary).toHaveBeenCalledWith(
      "page-1",
      expect.objectContaining({ description_binary: "encoded-binary", description_html: "<p>converted</p>" })
    );
  });

  it("never returns bytes for an unauthorized workspace or a private page", async () => {
    const service = makeService({
      fetchDescriptionBinary: vi.fn().mockRejectedValue(httpError(404)),
    });
    getPageServiceMock.mockReturnValue(service);

    await expect(fetchDocument({ context: makeContext(), documentName: "page-1", instance } as never)).rejects.toThrow(
      AppError
    );
    expect(broadcastErrorMock).toHaveBeenCalledWith(
      instance,
      "page-1",
      "Unable to load the page. Please try refreshing.",
      "fetch",
      expect.anything()
    );
  });

  it("still loads a Company Wiki page for an open-read non-member (read allowed, write denied)", async () => {
    const service = makeService({
      fetchDescriptionBinary: vi.fn().mockResolvedValue(Buffer.from([4, 2])),
    });
    getPageServiceMock.mockReturnValue(service);

    const result = await fetchDocument({
      context: makeContext({ documentType: "workspace_page" }),
      documentName: "page-1",
      instance,
    } as never);

    expect(Array.from(result as Uint8Array)).toEqual([4, 2]);
  });
});

describe("storeDocument", () => {
  beforeEach(() => {
    getPageServiceMock.mockReset();
    broadcastErrorMock.mockReset();
    forceCloseMock.mockReset();
  });

  it("persists a workspace page update", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockResolvedValue({ message: "Updated successfully" }),
    });
    getPageServiceMock.mockReturnValue(service);

    await storeDocument({
      context: makeContext(),
      state: new Uint8Array([1]),
      documentName: "page-1",
      instance,
    } as never);

    expect(service.updateDescriptionBinary).toHaveBeenCalledWith(
      "page-1",
      expect.objectContaining({ description_binary: "encoded-binary" })
    );
    expect(forceCloseMock).not.toHaveBeenCalled();
  });

  it("rejects a locked page write without disconnecting", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockRejectedValue(httpError(400)),
    });
    getPageServiceMock.mockReturnValue(service);

    await expect(
      storeDocument({ context: makeContext(), state: new Uint8Array([1]), documentName: "page-1", instance } as never)
    ).rejects.toThrow(AppError);

    expect(forceCloseMock).not.toHaveBeenCalled();
    expect(broadcastErrorMock).toHaveBeenCalledWith(
      instance,
      "page-1",
      expect.any(String),
      "store",
      expect.anything(),
      undefined,
      false
    );
  });

  it("force closes a workspace page session when persistence becomes forbidden (revocation)", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockRejectedValue(httpError(403)),
    });
    getPageServiceMock.mockReturnValue(service);

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

  it("force closes a Company Wiki open-read non-member that tries to persist", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockRejectedValue(httpError(403)),
    });
    getPageServiceMock.mockReturnValue(service);

    await storeDocument({
      context: makeContext({ documentType: "workspace_page" }),
      state: new Uint8Array([1]),
      documentName: "page-1",
      instance,
    } as never);

    expect(forceCloseMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the existing project_page store behavior on a forbidden write (regression)", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockRejectedValue(httpError(403)),
    });
    getPageServiceMock.mockReturnValue(service);

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

  it("still force closes with the document-too-large reason on a 413", async () => {
    const service = makeService({
      updateDescriptionBinary: vi.fn().mockRejectedValue(httpError(413)),
    });
    getPageServiceMock.mockReturnValue(service);

    await storeDocument({
      context: makeContext({ documentType: "project_page", projectId: "project-1" }),
      state: new Uint8Array([1]),
      documentName: "page-1",
      instance,
    } as never);

    expect(forceCloseMock).toHaveBeenCalledWith(
      instance,
      "page-1",
      ForceCloseReason.DOCUMENT_TOO_LARGE,
      CloseCode.DOCUMENT_TOO_LARGE
    );
  });
});
