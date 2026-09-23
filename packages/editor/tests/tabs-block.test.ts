import { describe, it, expect } from "vitest";
import { CORE_EXTENSIONS } from "../src/core/constants/extension";
import { ITabsBlockAttributeNames, DEFAULT_TABS_BLOCK_ATTRIBUTES } from "../src/core/extensions/tabs-block/types";
import { generateTabsBlockId } from "../src/core/extensions/tabs-block/utils";

describe("Tabs Block", () => {
  describe("types", () => {
    it("has correct attribute names", () => {
      expect(ITabsBlockAttributeNames.ID).toBe("id");
      expect(ITabsBlockAttributeNames.ORIENTATION).toBe("data-orientation");
      expect(ITabsBlockAttributeNames.ACTIVE_TAB).toBe("data-active-tab");
      expect(ITabsBlockAttributeNames.BLOCK_TYPE).toBe("data-block-type");
    });

    it("has correct default attributes", () => {
      expect(DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ID]).toBeNull();
      expect(DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ORIENTATION]).toBe("horizontal");
      expect(DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.ACTIVE_TAB]).toBe(0);
      expect(DEFAULT_TABS_BLOCK_ATTRIBUTES[ITabsBlockAttributeNames.BLOCK_TYPE]).toBe("tabs-block-component");
    });
  });

  describe("utils", () => {
    it("generates a unique id", () => {
      const id1 = generateTabsBlockId();
      const id2 = generateTabsBlockId();
      expect(id1).toBeDefined();
      expect(id1).not.toBe(id2);
    });
  });

  describe("extension config", () => {
    it("registers the correct extension name", () => {
      expect(CORE_EXTENSIONS.TABS_BLOCK).toBe("tabsBlockComponent");
    });
  });
});
