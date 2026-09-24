import { describe, expect, test } from "vitest";
import {
  getDefaultWikiPath,
  getWikiHomePath,
  getWikiPagePath,
  resolveLegacyWikiPath,
} from "../../core/helpers/wiki-routes";

describe("Wiki routes", () => {
  test("uses the configured workspace slug for Home and page routes", () => {
    expect(getDefaultWikiPath("home")).toBe("/wiki/home");
    expect(getWikiHomePath("mkt")).toBe("/wiki/mkt");
    expect(getWikiPagePath("mkt", "page-1")).toBe("/wiki/mkt/page-1");
  });

  test("maps legacy company and workspace Wiki URLs", () => {
    expect(resolveLegacyWikiPath("/company-wiki", "home")).toBe("/wiki/home");
    expect(resolveLegacyWikiPath("/company-wiki/page-1", "home")).toBe("/wiki/home/page-1");
    expect(resolveLegacyWikiPath("/mkt/wiki", "home")).toBe("/wiki/mkt");
    expect(resolveLegacyWikiPath("/mkt/wiki/page-2", "home")).toBe("/wiki/mkt/page-2");
  });

  test("rejects empty path segments", () => {
    expect(() => getDefaultWikiPath("")).toThrow("Default Wiki workspace slug is not configured");
    expect(() => getWikiPagePath("mkt", "")).toThrow("Wiki page id is required");
  });
});
