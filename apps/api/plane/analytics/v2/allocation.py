# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Multi-assignee allocation (spec §15).

For multi-assignee work items the value must be attributed to each assignee.
Two modes are supported:

* :data:`ALLOCATION_FULL_CREDIT` — every assignee receives the full value
  (10 points -> 10 to A and 10 to B). Useful for "is anyone from team X
  touching this issue" membership analytics.
* :data:`ALLOCATION_SPLIT_EQUAL` — the value is divided evenly across
  active assignees (10 points / 2 -> 5 to A and 5 to B). The chosen
  workload metric for split-equal reporting.

Allocation is a query-time concept — it never modifies stored data. The
implementation lives in :mod:`plane.analytics.v2.query` because it has to
run inside a single ORM aggregation; this module holds the small pure-math
helper used by tests and the engine.
"""

from __future__ import annotations


ALLOCATION_FULL_CREDIT = "full_credit"
ALLOCATION_SPLIT_EQUAL = "split_equal"
ALLOCATION_NONE = "none"

VALID_ALLOCATIONS = frozenset({ALLOCATION_FULL_CREDIT, ALLOCATION_SPLIT_EQUAL, ALLOCATION_NONE})


def value_for_assignee_count(raw_value: float, assignee_count: int, mode: str) -> float:
    """Return the per-assignee contribution under the given allocation mode.

    ``raw_value`` is the metric value for a single issue (e.g. 10 estimate
    points, or 1 for a work-item count). ``assignee_count`` is the number of
    *active* (non-deleted) assignee rows for the issue at evaluation time.
    """
    if assignee_count <= 0:
        # Unassigned: with full_credit the issue still has no assignee, so 0.
        # split_equal cannot be applied; caller is expected to fall back to
        # ``none`` for unassigned metrics (see metrics.ALLOCATION_NONE).
        return 0.0
    if assignee_count == 1 or mode == ALLOCATION_FULL_CREDIT:
        return float(raw_value)
    if mode == ALLOCATION_SPLIT_EQUAL:
        return float(raw_value) / float(assignee_count)
    raise ValueError(f"Unknown allocation mode: {mode!r}")