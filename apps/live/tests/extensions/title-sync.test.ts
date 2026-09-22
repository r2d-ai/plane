/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
// types
import type { HocusPocusServerContext } from "@/types";

const { getPageServiceMock } = vi.hoisted(() => ({ getPageServiceMock: vi.fn() }));

vi.mock("@/services/page/handler", () => ({ getPageService: getPageServiceMock }));
vi.mock("@/utils/broadcast-message", () => ({ broadcastMessageToPage: vi.fn() }));
vi.mock("@plane/editor", () => ({
  TITLE_EDITOR_EXTENSIONS: [],
  createRealtimeEvent: vi.fn(() => ({})),
  extractTextFromHTML: vi.fn((html: string) => html),
  generateTitleProsemirrorJson: vi.fn((text: string) => ({ type: "doc", content: [{ type: "text", text }] })),
}));
vi.mock("@hocuspocus/transformer", () => ({
  TiptapTransformer: { toYdoc: vi.fn(() => ({ fake: "title-field" })) },
}));

import { TitleSyncExtension } from "@/extensions/title-sync";
import { TitleUpdateManager, isTitleWriteForbidden } from "@/extensions/title-update/title-update-manager";
import { AppError } from "@/lib/errors";

const makeContext = (overrides: Partial<HocusPocusServerContext> = {}): HocusPocusServerContext => ({
  cookie: "session-cookie",
  documentType: "workspace_page",
  projectId: null,
  userId: "user-1",
  workspaceSlug: "acme",
  ...overrides,
});

describe("isTitleWriteForbidden", () => {
  it("treats lock/denied/locked/private statuses as authorization outcomes", () => {
    expect(isTitleWriteForbidden(new AppError("locked", { statusCode: 400 }))).toBe(true);
    expect(isTitleWriteForbidden(new AppError("denied", { statusCode: 403 }))).toBe(true);
    expect(isTitleWriteForbidden(new AppError("missing", { statusCode: 404 }))).toBe(true);
    expect(isTitleWriteForbidden(new AppError("unauthorized", { statusCode: 401 }))).toBe(true);
  });

  it("treats transport/server errors as retryable", () => {
    expect(isTitleWriteForbidden(new AppError("server", { statusCode: 500 }))).toBe(false);
    expect(isTitleWriteForbidden(new AppError("generic"))).toBe(false);
  });
});

describe("TitleUpdateManager", () => {
  beforeEach(() => {
    getPageServiceMock.mockReset();
  });

  it("persists the title through the dispatched workspace page service", async () => {
    const service = { updatePageProperties: vi.fn().mockResolvedValue({}) };
    getPageServiceMock.mockReturnValue(service);

    const manager = new TitleUpdateManager("page-1", makeContext(), 100000);
    manager.scheduleUpdate("Renamed Wiki Page");
    await manager.forceSave();
    manager.cancel();

    expect(getPageServiceMock).toHaveBeenCalledWith(
      "workspace_page",
      expect.objectContaining({ workspaceSlug: "acme" })
    );
    expect(service.updatePageProperties).toHaveBeenCalledWith(
      "page-1",
      expect.objectContaining({ data: { name: "Renamed Wiki Page" } })
    );
  });

  it("swallows a forbidden title write instead of retrying it as a transient error", async () => {
    const service = {
      updatePageProperties: vi.fn().mockRejectedValue(new AppError("forbidden", { statusCode: 403 })),
    };
    getPageServiceMock.mockReturnValue(service);

    const manager = new TitleUpdateManager("page-1", makeContext(), 100000);
    manager.scheduleUpdate("Renamed Wiki Page");
    await expect(manager.forceSave()).resolves.toBeUndefined();
    manager.cancel();
  });
});

describe("TitleSyncExtension", () => {
  beforeEach(() => {
    getPageServiceMock.mockReset();
  });

  it("migrates the title for an authorized workspace page", async () => {
    const service = { fetchDetails: vi.fn().mockResolvedValue({ name: "Wiki Home" }) };
    getPageServiceMock.mockReturnValue(service);
    const document = { isEmpty: vi.fn(() => true), merge: vi.fn() };

    const extension = new TitleSyncExtension();
    await extension.onLoadDocument({
      context: makeContext(),
      document,
      documentName: "page-1",
    } as never);

    expect(document.merge).toHaveBeenCalledTimes(1);
    expect(getPageServiceMock).toHaveBeenCalledWith(
      "workspace_page",
      expect.objectContaining({ workspaceSlug: "acme" })
    );
  });

  it("skips title migration when the effective page permission denies access", async () => {
    const service = { fetchDetails: vi.fn().mockRejectedValue(new AppError("forbidden", { statusCode: 403 })) };
    getPageServiceMock.mockReturnValue(service);
    const document = { isEmpty: vi.fn(() => true), merge: vi.fn() };

    const extension = new TitleSyncExtension();
    await expect(
      extension.onLoadDocument({ context: makeContext(), document, documentName: "page-1" } as never)
    ).resolves.toBeUndefined();

    expect(document.merge).not.toHaveBeenCalled();
  });
});
