/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
// types
import type { HocusPocusServerContext, TDocumentTypes } from "@/types";

const { currentUserMock } = vi.hoisted(() => ({ currentUserMock: vi.fn() }));

vi.mock("@/services/user.service", () => ({
  UserService: class UserServiceMock {
    currentUser = currentUserMock;
  },
}));

import { onAuthenticate, validateDocumentConnection } from "@/lib/auth";

const makeParams = (values: Record<string, string>) => new URLSearchParams(values);
const anonymousParams = (values: Record<string, string>) => ({
  requestHeaders: {},
  requestParameters: makeParams(values),
});

describe("validateDocumentConnection", () => {
  it("accepts workspace_page with a slug and no projectId", () => {
    expect(() =>
      validateDocumentConnection({ documentType: "workspace_page", workspaceSlug: "acme", projectId: null })
    ).not.toThrow();
  });

  it("rejects workspace_page without a workspace slug", () => {
    expect(() =>
      validateDocumentConnection({ documentType: "workspace_page", workspaceSlug: null, projectId: null })
    ).toThrow(/Workspace slug is required/);
  });

  it("accepts project_page with a slug and a project id", () => {
    expect(() =>
      validateDocumentConnection({ documentType: "project_page", workspaceSlug: "acme", projectId: "project-1" })
    ).not.toThrow();
  });

  it("rejects project_page without a project id", () => {
    expect(() =>
      validateDocumentConnection({ documentType: "project_page", workspaceSlug: "acme", projectId: null })
    ).toThrow(/Project ID is required/);
  });

  it("rejects an unknown document type", () => {
    expect(() =>
      validateDocumentConnection({
        documentType: "instance_page" as TDocumentTypes,
        workspaceSlug: "acme",
        projectId: null,
      })
    ).toThrow(/Invalid document type/);
  });
});

describe("onAuthenticate", () => {
  beforeEach(() => {
    currentUserMock.mockReset();
    currentUserMock.mockResolvedValue({ id: "user-1", display_name: "Wiki Reader" });
  });

  it("denies anonymous connections so document bytes are never returned", async () => {
    await expect(
      onAuthenticate({
        ...anonymousParams({ documentType: "workspace_page", workspaceSlug: "acme" }),
        context: {} as HocusPocusServerContext,
        token: "",
      })
    ).rejects.toThrow(/Credentials not provided/);
    expect(currentUserMock).not.toHaveBeenCalled();
  });

  it("rejects unknown document types before authenticating", async () => {
    await expect(
      onAuthenticate({
        ...anonymousParams({ documentType: "instance_page", workspaceSlug: "acme" }),
        context: {} as HocusPocusServerContext,
        token: JSON.stringify({ id: "user-1", cookie: "session-cookie" }),
      })
    ).rejects.toThrow(/Invalid document type/);
  });

  it("requires a workspace slug for a workspace_page connection", async () => {
    await expect(
      onAuthenticate({
        ...anonymousParams({ documentType: "workspace_page" }),
        context: {} as HocusPocusServerContext,
        token: JSON.stringify({ id: "user-1", cookie: "session-cookie" }),
      })
    ).rejects.toThrow(/Workspace slug is required/);
  });

  it("accepts a workspace_page connection with an optional projectId", async () => {
    const context = {} as HocusPocusServerContext;

    const result = await onAuthenticate({
      ...anonymousParams({ documentType: "workspace_page", workspaceSlug: "acme" }),
      context,
      token: JSON.stringify({ id: "user-1", cookie: "session-cookie" }),
    });

    expect(context.documentType).toBe("workspace_page");
    expect(context.workspaceSlug).toBe("acme");
    expect(context.projectId).toBeNull();
    expect(context.cookie).toBe("session-cookie");
    expect(result).toEqual({ user: { id: "user-1", name: "Wiki Reader" } });
  });
});
