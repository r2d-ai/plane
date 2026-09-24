import { describe, expect, test } from "vitest";
import {
  isWikiPath,
  wikiSearchResultPath,
  wikiSearchResultValue,
  workPageSearchResultPath,
} from "../../core/components/power-k/ui/modal/wiki-search-map";

describe("Wiki search routes", () => {
  test("selects aggregate Wiki search for canonical paths", () => {
    expect(isWikiPath("/wiki/home/page-1")).toBe(true);
    expect(isWikiPath("/mkt/projects/project-1/pages")).toBe(false);
  });

  test("maps aggregate results to the source workspace", () => {
    expect(wikiSearchResultPath({ workspace_slug: "mkt", page_id: "page-1" })).toBe("/wiki/mkt/page-1");
  });

  test("keeps body matches visible to the command palette filter", () => {
    expect(
      wikiSearchResultValue({
        workspace_slug: "mkt",
        workspace_name: "Marketing",
        page_id: "page-1",
        page_name: "Radio notes",
        matched_content_summary: "Đây là đài tiếng nói Việt Nam",
      })
    ).toContain("Đây là đài tiếng nói Việt Nam");
  });

  test("keeps project Pages in Work", () => {
    expect(
      workPageSearchResultPath({ workspace__slug: "mkt", id: "page-1", project_ids: ["project-1"] }, "project-1")
    ).toBe("/mkt/projects/project-1/pages/page-1");
  });
});
