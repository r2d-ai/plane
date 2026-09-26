## 2025-05-18 - [O(N^2) Tree Building with Nested Array Filtering]
**Learning:** `buildTree` in `@plane/utils` was performing recursive `array.forEach` calls filtering the entire input array for every level of the tree, resulting in O(N^2) time complexity. Refactoring this to a single-pass `Map` lookup reduces time complexity to O(N) while maintaining identical tree output structure and supporting optional parent filtering.
**Action:** When working with tree structures, map nodes by ID in a single pass first before linking parent-child relations to avoid quadratic iteration patterns.
