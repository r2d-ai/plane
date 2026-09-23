import { describe, it, expect } from "vitest";
import { CORE_EXTENSIONS } from "../src/core/constants/extension";
import { IToggleBlockAttributeNames, DEFAULT_TOGGLE_BLOCK_ATTRIBUTES } from "../src/core/extensions/toggle-block/types";
import { generateToggleBlockId } from "../src/core/extensions/toggle-block/utils";

describe("Toggle Block", () => {
  describe("types", () => {
    it("has correct attribute names", () => {
      expect(IToggleBlockAttributeNames.ID).toBe("id");
      expect(IToggleBlockAttributeNames.OPEN).toBe("data-open");
      expect(IToggleBlockAttributeNames.BLOCK_TYPE).toBe("data-block-type");
    });

    it("has correct default attributes", () => {
      expect(DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.ID]).toBeNull();
      expect(DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.OPEN]).toBe(true);
      expect(DEFAULT_TOGGLE_BLOCK_ATTRIBUTES[IToggleBlockAttributeNames.BLOCK_TYPE]).toBe("toggle-block-component");
    });
  });

  describe("utils", () => {
    it("generates a unique id", () => {
      const id1 = generateToggleBlockId();
      const id2 = generateToggleBlockId();
      expect(id1).toBeDefined();
      expect(id1).not.toBe(id2);
    });
  });

  describe("extension config", () => {
    it("registers the correct extension name", () => {
      expect(CORE_EXTENSIONS.TOGGLE_BLOCK).toBe("toggleBlockComponent");
    });
  });
});
