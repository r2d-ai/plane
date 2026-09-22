/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, it, expect } from "vitest";
// services
import { getPageService } from "@/services/page/handler";
import { ProjectPageService } from "@/services/page/project-page.service";
import { WorkspacePageService } from "@/services/page/workspace-page.service";
// types
import type { HocusPocusServerContext, TDocumentTypes } from "@/types";

const basePathOf = (service: unknown): string => (service as { basePath: string }).basePath;

const makeContext = (overrides: Partial<HocusPocusServerContext> = {}): HocusPocusServerContext => ({
  projectId: "project-1",
  cookie: "session-cookie",
  documentType: "project_page",
  workspaceSlug: "acme",
  userId: "user-1",
  ...overrides,
});

describe("getPageService", () => {
  it("dispatches project_page to the project-scoped service", () => {
    const service = getPageService("project_page", makeContext());

    expect(service).toBeInstanceOf(ProjectPageService);
    expect(basePathOf(service)).toBe("/api/workspaces/acme/projects/project-1");
  });

  it("dispatches workspace_page to the workspace-scoped service without a project", () => {
    const service = getPageService("workspace_page", makeContext({ projectId: null }));

    expect(service).toBeInstanceOf(WorkspacePageService);
    expect(basePathOf(service)).toBe("/api/workspaces/acme");
  });

  it("rejects unknown document types", () => {
    expect(() => getPageService("instance_page" as TDocumentTypes, makeContext())).toThrow(/Invalid document type/);
  });

  it("rejects a malformed workspace_page context instead of routing it", () => {
    expect(() => getPageService("workspace_page", makeContext({ projectId: null, workspaceSlug: null }))).toThrow(
      /Missing required fields/
    );
  });
});
