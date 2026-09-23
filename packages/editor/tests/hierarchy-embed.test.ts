import { describe, it, expect } from "vitest";
import { CORE_EXTENSIONS } from "../src/core/constants/extension";
import {
  IHierarchyEmbedAttributeNames,
  DEFAULT_HIERARCHY_EMBED_ATTRIBUTES,
} from "../src/core/extensions/hierarchy-embed/types";
import { generateHierarchyEmbedId } from "../src/core/extensions/hierarchy-embed/utils";

describe("Hierarchy Embed", () => {
  describe("types", () => {
    it("has correct attribute names", () => {
      expect(IHierarchyEmbedAttributeNames.ID).toBe("id");
      expect(IHierarchyEmbedAttributeNames.PAGE_ID).toBe("data-page-id");
      expect(IHierarchyEmbedAttributeNames.WORKSPACE_SLUG).toBe("data-workspace-slug");
      expect(IHierarchyEmbedAttributeNames.PROJECT_ID).toBe("data-project-id");
      expect(IHierarchyEmbedAttributeNames.DEPTH).toBe("data-depth");
      expect(IHierarchyEmbedAttributeNames.VIEW_MODE).toBe("data-view-mode");
      expect(IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR).toBe("data-group-by-creator");
      expect(IHierarchyEmbedAttributeNames.BLOCK_TYPE).toBe("data-block-type");
    });

    it("has correct default attributes", () => {
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.ID]).toBeNull();
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.PAGE_ID]).toBeUndefined();
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.DEPTH]).toBe(2);
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.VIEW_MODE]).toBe("children");
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.GROUP_BY_CREATOR]).toBe(false);
      expect(DEFAULT_HIERARCHY_EMBED_ATTRIBUTES[IHierarchyEmbedAttributeNames.BLOCK_TYPE]).toBe(
        "hierarchy-embed-component"
      );
    });
  });

  describe("utils", () => {
    it("generates a unique id", () => {
      const id1 = generateHierarchyEmbedId();
      const id2 = generateHierarchyEmbedId();
      expect(id1).toBeDefined();
      expect(id1).not.toBe(id2);
    });
  });

  describe("extension config", () => {
    it("registers the correct extension name", () => {
      expect(CORE_EXTENSIONS.HIERARCHY_EMBED).toBe("hierarchyEmbedComponent");
    });
  });
});
