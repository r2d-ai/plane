import { describe, it, expect } from "vitest";
import { buildWikiPageMentionPath, isWorkspaceWikiPage } from "../src/core/helpers/wiki-page-mention";

describe("wiki page mention helpers", () => {
  describe("isWorkspaceWikiPage", () => {
    it("returns true when the page has no project ids", () => {
      expect(
        isWorkspaceWikiPage({ id: "p1", name: "Doc", logo_props: null, projects__id: [], workspace__slug: "acme" })
      ).toBe(true);
      expect(
        isWorkspaceWikiPage({
          id: "p1",
          name: "Doc",
          logo_props: null,
          projects__id: undefined,
          workspace__slug: "acme",
        })
      ).toBe(true);
    });

    it("returns false when the page belongs to a project", () => {
      expect(
        isWorkspaceWikiPage({
          id: "p1",
          name: "Doc",
          logo_props: null,
          projects__id: ["proj-1"],
          workspace__slug: "acme",
        })
      ).toBe(false);
    });
  });

  describe("buildWikiPageMentionPath", () => {
    it("routes workspace wiki pages to the wiki surface", () => {
      expect(
        buildWikiPageMentionPath({
          id: "page-1",
          workspace__slug: "acme",
          projects__id: [],
        })
      ).toBe("/acme/wiki/page-1");
    });

    it("routes company wiki surface pages to /company-wiki", () => {
      expect(
        buildWikiPageMentionPath(
          {
            id: "page-1",
            workspace__slug: "acme",
            projects__id: [],
          },
          { companyWikiSurface: true }
        )
      ).toBe("/company-wiki/page-1");
    });

    it("routes project pages to the project pages surface", () => {
      expect(
        buildWikiPageMentionPath({
          id: "page-1",
          workspace__slug: "acme",
          projects__id: ["proj-1", "proj-2"],
        })
      ).toBe("/acme/projects/proj-1/pages/page-1");
    });

    it("prefers the active project when provided", () => {
      expect(
        buildWikiPageMentionPath(
          {
            id: "page-1",
            workspace__slug: "acme",
            projects__id: ["proj-1", "proj-2"],
          },
          { projectId: "proj-2" }
        )
      ).toBe("/acme/projects/proj-2/pages/page-1");
    });
  });
});
