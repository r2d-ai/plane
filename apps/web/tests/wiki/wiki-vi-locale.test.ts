import { describe, expect, test } from "vitest";
import en from "../../../../packages/i18n/src/locales/en/wiki.json";
import vi from "../../../../packages/i18n/src/locales/vi-VN/wiki.json";
import viNavigation from "../../../../packages/i18n/src/locales/vi-VN/navigation.json";

const leafKeys = (value: Record<string, unknown>, prefix = ""): string[] =>
  Object.entries(value).flatMap(([key, entry]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return entry && typeof entry === "object" && !Array.isArray(entry)
      ? leafKeys(entry as Record<string, unknown>, path)
      : [path];
  });

describe("Vietnamese Wiki translations", () => {
  test("covers every English Wiki key", () => {
    expect(leafKeys(vi)).toEqual(expect.arrayContaining(leafKeys(en)));
  });

  test("translates the primary Wiki navigation", () => {
    expect(vi.wiki.sidebar.new_page).toBe("Trang mới");
    expect(vi.wiki.sidebar.workspaces).toBe("Không gian làm việc");
    expect(vi.wiki.collections.section_title).toBe("Bộ sưu tập");
    expect(viNavigation.sidebar.work).toBe("Công việc");
  });
});
