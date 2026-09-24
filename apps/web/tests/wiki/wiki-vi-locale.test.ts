import { describe, expect, test } from "vitest";
import en from "../../../../packages/i18n/src/locales/en/wiki.json";
import vi from "../../../../packages/i18n/src/locales/vi-VN/wiki.json";
import viNavigation from "../../../../packages/i18n/src/locales/vi-VN/navigation.json";
import viCommon from "../../../../packages/i18n/src/locales/vi-VN/common.json";
import viPage from "../../../../packages/i18n/src/locales/vi-VN/page.json";

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
    expect(vi.wiki.collections.section_title).toBe("Chuyên mục");
    expect(viNavigation.sidebar.work).toBe("Công việc");
  });

  test("translates Wiki page menu labels", () => {
    expect(viCommon.page_controls.full_width).toBe("Toàn chiều rộng");
    expect(viCommon.page_controls.sticky_toolbar).toBe("Cố định thanh công cụ");
    expect(viCommon.common.actions.copy_markdown).toBe("Sao chép Markdown");
    expect(viPage.page_navigation_pane.tabs.info.version_history.label).toBe("Lịch sử phiên bản");
    expect(viCommon.page_controls.export_page).toBe("Xuất trang");
  });

  test("uses the same term for Wiki page groups", () => {
    expect(JSON.stringify([vi, viPage, viCommon])).not.toMatch(/bộ sưu tập|nhóm trang/i);
  });
});
