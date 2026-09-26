import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { buildTree } from "../array.ts";

describe("buildTree", () => {
  it("returns an empty array when input is empty or null", () => {
    assert.deepEqual(buildTree([] as any), []);
    assert.deepEqual(buildTree(null as any), []);
  });

  it("builds a flat tree for items with no parents (null or undefined parent)", () => {
    const labels: any[] = [
      { id: "1", name: "Label 1", parent: null },
      { id: "2", name: "Label 2", parent: undefined },
    ];

    const result = buildTree(labels);

    assert.equal(result.length, 2);
    assert.equal(result[0].id, "1");
    assert.deepEqual(result[0].children, []);
    assert.equal(result[1].id, "2");
    assert.deepEqual(result[1].children, []);
  });

  it("correctly nests child items under their parent", () => {
    const labels: any[] = [
      { id: "1", name: "Parent Label", parent: null },
      { id: "2", name: "Child Label 1", parent: "1" },
      { id: "3", name: "Child Label 2", parent: "1" },
      { id: "4", name: "Grandchild Label", parent: "2" },
    ];

    const result = buildTree(labels);

    assert.equal(result.length, 1);
    assert.equal(result[0].id, "1");
    assert.equal(result[0].children.length, 2);

    assert.equal(result[0].children[0].id, "2");
    assert.equal(result[0].children[0].children.length, 1);
    assert.equal(result[0].children[0].children[0].id, "4");

    assert.equal(result[0].children[1].id, "3");
    assert.equal(result[0].children[1].children.length, 0);
  });

  it("handles filtering by a custom parent ID", () => {
    const labels: any[] = [
      { id: "1", name: "Parent Label", parent: null },
      { id: "2", name: "Child Label 1", parent: "1" },
      { id: "3", name: "Child Label 2", parent: "1" },
    ];

    const result = buildTree(labels, "1");

    assert.equal(result.length, 2);
    assert.equal(result[0].id, "2");
    assert.equal(result[1].id, "3");
  });
});
