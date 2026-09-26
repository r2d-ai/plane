# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for Analytics V2 normalisation math (spec §49.1).

Verifies §17 group_total / series_total / grand_total arithmetic and the
display-mode formatting helper.
"""

from __future__ import annotations

import pytest

from plane.analytics.v2.normalization import (
    DISPLAY_PERCENTAGE,
    DISPLAY_VALUE,
    DISPLAY_VALUE_AND_PCT,
    NORMALIZATION_GRAND_TOTAL,
    NORMALIZATION_GROUP_TOTAL,
    NORMALIZATION_NONE,
    NORMALIZATION_SERIES_TOTAL,
    format_display,
    normalize,
)


@pytest.mark.unit
class TestNormalizeNone:
    def test_none_mode_returns_raw_values_without_percentages(self):
        rows = [("A", "x", 10.0), ("B", "y", 20.0)]
        out = normalize(rows, mode=NORMALIZATION_NONE)
        assert [c.value for c in out] == [10.0, 20.0]
        assert all(c.percentage is None for c in out)


@pytest.mark.unit
class TestNormalizeGroupTotal:
    """§17.1: cell / SUM(all cells in the same row group)."""

    def test_each_row_sums_to_one_hundred_percent(self):
        rows = [
            ("A", "x", 10.0),
            ("A", "y", 30.0),
            ("B", "x", 5.0),
            ("B", "y", 15.0),
        ]
        out = normalize(rows, mode=NORMALIZATION_GROUP_TOTAL)
        by_group: dict[str, float] = {}
        for c in out:
            by_group[c.group] = by_group.get(c.group, 0.0) + (c.percentage or 0.0)
        for g, total in by_group.items():
            assert pytest.approx(total, abs=1e-6) == 1.0, f"group {g} did not sum to 100%"

    def test_specific_cell_value(self):
        rows = [("A", "x", 10.0), ("A", "y", 30.0)]
        out = normalize(rows, mode=NORMALIZATION_GROUP_TOTAL)
        # 10 / (10+30) = 0.25
        assert out[0].percentage == pytest.approx(0.25, abs=1e-6)


@pytest.mark.unit
class TestNormalizeSeriesTotal:
    """§17.2: cell / SUM(all cells in the same series column)."""

    def test_each_column_sums_to_one_hundred_percent(self):
        rows = [
            ("A", "x", 10.0),
            ("B", "x", 30.0),
            ("A", "y", 5.0),
            ("B", "y", 15.0),
        ]
        out = normalize(rows, mode=NORMALIZATION_SERIES_TOTAL)
        by_series: dict[str, float] = {}
        for c in out:
            by_series[c.series] = by_series.get(c.series, 0.0) + (c.percentage or 0.0)
        for s, total in by_series.items():
            assert pytest.approx(total, abs=1e-6) == 1.0, f"series {s} did not sum to 100%"


@pytest.mark.unit
class TestNormalizeGrandTotal:
    """§17.3: cell / total selected metric."""

    def test_all_percentages_sum_to_one(self):
        rows = [("A", "x", 10.0), ("A", "y", 30.0), ("B", "x", 60.0)]
        out = normalize(rows, mode=NORMALIZATION_GRAND_TOTAL)
        total = sum((c.percentage or 0.0) for c in out)
        assert pytest.approx(total, abs=1e-6) == 1.0

    def test_zero_total_returns_none_percentages(self):
        rows = [("A", "x", 0.0), ("B", "y", 0.0)]
        out = normalize(rows, mode=NORMALIZATION_GRAND_TOTAL)
        assert all(c.percentage is None for c in out)


@pytest.mark.unit
class TestFormatDisplay:
    """§17.4 display modes."""

    def test_value_mode(self):
        from plane.analytics.v2.normalization import Cell

        cell = Cell("A", "x", 18.0, 0.429)
        assert format_display(cell, DISPLAY_VALUE) == "18"
        assert format_display(cell, DISPLAY_VALUE, unit=" pts") == "18 pts"

    def test_percentage_mode(self):
        from plane.analytics.v2.normalization import Cell

        cell = Cell("A", "x", 18.0, 0.429)
        assert format_display(cell, DISPLAY_PERCENTAGE) == "42.9%"

    def test_value_and_pct_mode(self):
        from plane.analytics.v2.normalization import Cell

        cell = Cell("A", "x", 18.0, 0.429)
        assert format_display(cell, DISPLAY_VALUE_AND_PCT) == "18 · 42.9%"


@pytest.mark.unit
def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        normalize([], mode="garbage")
    with pytest.raises(ValueError):
        format_display(None, "bogus")