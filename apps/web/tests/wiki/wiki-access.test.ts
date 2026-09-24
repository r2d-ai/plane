import { describe, expect, test } from "vitest";
import { resolveDefaultWikiScope, resolveWikiScopeAccess } from "../../core/helpers/wiki-access";

const scopes = [
  {
    id: "1",
    slug: "home",
    name: "Instance",
    is_default: true,
    is_member: false,
    can_create: false,
    can_manage_collections: false,
  },
  {
    id: "2",
    slug: "mkt",
    name: "Marketing",
    is_default: false,
    is_member: true,
    can_create: true,
    can_manage_collections: false,
  },
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
        [
          {
            id: "3",
            slug: "other",
            name: "Other",
            is_default: false,
            is_member: false,
            can_create: false,
            can_manage_collections: false,
          },
        ],
        "other"
      )
    ).toBeUndefined();
  });
});

describe("Default Wiki scope resolution", () => {
  test("picks the scope the API marks as default, independent of any frontend constant", () => {
    const mixedScopes = [
      {
        id: "1",
        slug: "acme",
        name: "Acme",
        is_default: true,
        is_member: false,
        can_create: false,
        can_manage_collections: false,
      },
      {
        id: "2",
        slug: "mkt",
        name: "Marketing",
        is_default: false,
        is_member: true,
        can_create: true,
        can_manage_collections: false,
      },
    ];
    expect(resolveDefaultWikiScope(mixedScopes)?.slug).toBe("acme");
    expect(resolveDefaultWikiScope(mixedScopes)?.is_default).toBe(true);
  });

  test("returns undefined when no workspace is designated for Company Wiki", () => {
    const memberOnlyScopes = [
      {
        id: "2",
        slug: "mkt",
        name: "Marketing",
        is_default: false,
        is_member: true,
        can_create: true,
        can_manage_collections: false,
      },
    ];
    expect(resolveDefaultWikiScope(memberOnlyScopes)).toBeUndefined();
  });

  test("returns undefined for an empty scope list", () => {
    expect(resolveDefaultWikiScope([])).toBeUndefined();
  });
});
