import { describe, expect, test } from "vitest";
import { resolveWikiScopeAccess } from "../../core/helpers/wiki-access";

const scopes = [
  { id: "1", slug: "home", name: "Instance", is_default: true, is_member: false, can_create: false },
  { id: "2", slug: "mkt", name: "Marketing", is_default: false, is_member: true, can_create: true },
];

describe("Wiki scope access", () => {
  test("allows only slugs returned by the server ACL endpoint", () => {
    expect(resolveWikiScopeAccess(scopes, "home")?.is_default).toBe(true);
    expect(resolveWikiScopeAccess(scopes, "mkt")?.can_create).toBe(true);
    expect(resolveWikiScopeAccess(scopes, "finance")).toBeUndefined();
  });

  test("does not allow a non-member ordinary workspace", () => {
    expect(
      resolveWikiScopeAccess(
        [{ id: "3", slug: "other", name: "Other", is_default: false, is_member: false, can_create: false }],
        "other"
      )
    ).toBeUndefined();
  });
});
