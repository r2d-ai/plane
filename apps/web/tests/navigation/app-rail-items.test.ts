import { describe, expect, test } from "vitest";
import { buildAppRailItems } from "@/components/navigation/app-rail-items";

describe("App rail items", () => {
  test("builds independent Work and Wiki destinations", () => {
    expect(
      buildAppRailItems({ workWorkspaceSlug: "test", wikiWorkspaceSlug: "home", pathname: "/wiki/home" }).map(
        ({ label, href, isActive }) => ({ label, href, isActive })
      )
    ).toEqual([
      { label: "Work", href: "/test/", isActive: false },
      { label: "Wiki", href: "/wiki/home", isActive: true },
    ]);
  });

  test("activates Work and not Wiki on workspace project routes", () => {
    expect(
      buildAppRailItems({ workWorkspaceSlug: "test", wikiWorkspaceSlug: "home", pathname: "/test/projects" }).map(
        ({ label, href, isActive }) => ({ label, href, isActive })
      )
    ).toEqual([
      { label: "Work", href: "/test/", isActive: true },
      { label: "Wiki", href: "/wiki/home", isActive: false },
    ]);
  });
});
