import { describe, it, expect } from "vitest";
import { CORE_EXTENSIONS } from "../src/core/constants/extension";
import { IMermaidAttributeNames, DEFAULT_MERMAID_ATTRIBUTES } from "../src/core/extensions/mermaid/types";
import { generateMermaidBlockId } from "../src/core/extensions/mermaid/utils";

describe("Mermaid Block", () => {
  describe("types", () => {
    it("has correct attribute names", () => {
      expect(IMermaidAttributeNames.ID).toBe("id");
      expect(IMermaidAttributeNames.CODE).toBe("data-code");
      expect(IMermaidAttributeNames.BLOCK_TYPE).toBe("data-block-type");
    });

    it("has correct default attributes", () => {
      expect(DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.ID]).toBeNull();
      expect(DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.CODE]).toContain("graph TD");
      expect(DEFAULT_MERMAID_ATTRIBUTES[IMermaidAttributeNames.BLOCK_TYPE]).toBe("mermaid-component");
    });
  });

  describe("utils", () => {
    it("generates a unique id", () => {
      const id1 = generateMermaidBlockId();
      const id2 = generateMermaidBlockId();
      expect(id1).toBeDefined();
      expect(id1).not.toBe(id2);
    });
  });

  describe("extension config", () => {
    it("registers the correct extension name", () => {
      expect(CORE_EXTENSIONS.MERMAID).toBe("mermaidComponent");
    });
  });
});
