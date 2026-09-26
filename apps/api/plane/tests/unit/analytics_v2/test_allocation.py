# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for Analytics V2 allocation math (spec §49.1, §49.4).

The pure-math helper covers both allocation modes for multi-assignee work
items. The DB-level workload test (§49.4) lives in ``test_workload.py``.
"""

from __future__ import annotations

import pytest

from plane.analytics.v2.allocation import (
    ALLOCATION_FULL_CREDIT,
    ALLOCATION_NONE,
    ALLOCATION_SPLIT_EQUAL,
    VALID_ALLOCATIONS,
    value_for_assignee_count,
)


@pytest.mark.unit
class TestFullCredit:
    def test_single_assignee_gets_full_value(self):
        assert value_for_assignee_count(10.0, 1, ALLOCATION_FULL_CREDIT) == 10.0

    def test_two_assignees_each_get_full_value(self):
        assert value_for_assignee_count(10.0, 2, ALLOCATION_FULL_CREDIT) == 10.0

    def test_three_assignees_each_get_full_value(self):
        assert value_for_assignee_count(12.0, 3, ALLOCATION_FULL_CREDIT) == 12.0


@pytest.mark.unit
class TestSplitEqual:
    def test_single_assignee_gets_full_value(self):
        # No splitting required.
        assert value_for_assignee_count(10.0, 1, ALLOCATION_SPLIT_EQUAL) == 10.0

    def test_two_assignees_each_get_half(self):
        assert value_for_assignee_count(10.0, 2, ALLOCATION_SPLIT_EQUAL) == 5.0

    def test_three_assignees_each_get_third(self):
        result = value_for_assignee_count(12.0, 3, ALLOCATION_SPLIT_EQUAL)
        assert pytest.approx(result, abs=1e-6) == 4.0


@pytest.mark.unit
class TestEdgeCases:
    def test_unassigned_returns_zero(self):
        # Caller is expected to map ``unassigned_work_items`` to ``none``
        # allocation, but if it slips through the math returns 0.
        assert value_for_assignee_count(10.0, 0, ALLOCATION_FULL_CREDIT) == 0.0
        assert value_for_assignee_count(10.0, 0, ALLOCATION_SPLIT_EQUAL) == 0.0

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            value_for_assignee_count(10.0, 2, "bogus")

    def test_valid_allocations_constant(self):
        assert ALLOCATION_FULL_CREDIT in VALID_ALLOCATIONS
        assert ALLOCATION_SPLIT_EQUAL in VALID_ALLOCATIONS
        assert ALLOCATION_NONE in VALID_ALLOCATIONS
        assert len(VALID_ALLOCATIONS) == 3