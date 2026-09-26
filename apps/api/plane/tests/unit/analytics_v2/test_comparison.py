# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for Analytics V2 comparison period resolution (spec §49.1).

Comparison resolution: previous_period (length-equivalent), previous_week,
previous_month, previous_quarter, previous_year, and the ``none`` short-circuit.
"""

from __future__ import annotations

from datetime import datetime

import pytest
import pytz

from plane.analytics.v2.comparison import (
    COMPARISON_NONE,
    COMPARISON_PREVIOUS_MONTH,
    COMPARISON_PREVIOUS_PERIOD,
    COMPARISON_PREVIOUS_QUARTER,
    COMPARISON_PREVIOUS_WEEK,
    COMPARISON_PREVIOUS_YEAR,
    resolve_comparison,
)
from plane.analytics.v2.time_scope import resolve_preset


NOW = datetime(2026, 7, 15, 10, 0, tzinfo=pytz.UTC)


def _current(preset="this_month"):
    return resolve_preset(preset, timezone_name="UTC", now=NOW)


@pytest.mark.unit
class TestComparisonPeriod:
    def test_none_short_circuits(self):
        result = resolve_comparison(_current(), COMPARISON_NONE)
        assert result is None

    def test_previous_period_matches_length(self):
        current = _current("this_month")
        result = resolve_comparison(current, COMPARISON_PREVIOUS_PERIOD)
        assert result is not None
        length = current.end - current.start
        assert result.previous.end - result.previous.start == length
        # The previous window must end exactly where the current begins.
        assert result.previous.end == current.start

    def test_previous_week_aligns_to_iso_week(self):
        current = resolve_preset("this_week", timezone_name="UTC", now=NOW)
        result = resolve_comparison(current, COMPARISON_PREVIOUS_WEEK)
        assert result.previous.end == current.start
        # 7-day window length for weekly preset.
        assert (result.previous.end - result.previous.start).days == 7

    def test_previous_month(self):
        current = resolve_preset("this_month", timezone_name="UTC", now=NOW)
        result = resolve_comparison(current, COMPARISON_PREVIOUS_MONTH)
        assert result.previous.start.month == 6
        assert result.previous.start.year == 2026
        assert result.previous.end.month == 7
        assert result.previous.end.day == 1

    def test_previous_quarter_at_q3(self):
        current = resolve_preset("this_quarter", timezone_name="UTC", now=NOW)
        result = resolve_comparison(current, COMPARISON_PREVIOUS_QUARTER)
        # Q3 starts in July, so previous quarter = April 1 to July 1.
        assert result.previous.start.month == 4
        assert result.previous.start.day == 1
        assert result.previous.end.month == 7
        assert result.previous.end.day == 1

    def test_previous_year(self):
        current = resolve_preset("this_year", timezone_name="UTC", now=NOW)
        result = resolve_comparison(current, COMPARISON_PREVIOUS_YEAR)
        assert result.previous.start.year == 2025
        assert result.previous.end.year == 2026

    def test_open_scope_returns_none(self):
        from plane.analytics.v2.time_scope import resolve_preset as rp

        open_scope = rp("none", timezone_name="UTC", now=NOW)
        assert resolve_comparison(open_scope, COMPARISON_PREVIOUS_PERIOD) is None

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            resolve_comparison(_current(), "previous_decade")