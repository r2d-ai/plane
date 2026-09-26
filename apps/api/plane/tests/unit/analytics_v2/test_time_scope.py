# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for Analytics V2 time-scope resolution (spec §49.1).

Covers: time preset resolution, quarter boundaries, month boundaries,
year boundaries, DST/non-DST timezone behaviour, and the half-open
``[start, end)`` convention.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
import pytz

from plane.analytics.v2.time_scope import (
    ALL_PRESETS,
    PRESET_CUSTOM,
    PRESET_LAST_30_DAYS,
    PRESET_LAST_90_DAYS,
    PRESET_LAST_MONTH,
    PRESET_LAST_QUARTER,
    PRESET_LAST_WEEK,
    PRESET_LAST_YEAR,
    PRESET_NONE,
    PRESET_THIS_MONTH,
    PRESET_THIS_QUARTER,
    PRESET_THIS_WEEK,
    PRESET_THIS_YEAR,
    PRESET_TODAY,
    PRESET_YESTERDAY,
    resolve_preset,
)


# Anchored ``now`` values used by the tests. We pin ``now`` so the assertions
# stay deterministic across timezones.
NOW_UTC = datetime(2026, 7, 15, 10, 0, tzinfo=pytz.UTC)


def _now(tz_name: str):
    tz = pytz.timezone(tz_name)
    return NOW_UTC.astimezone(tz)


def _aware_local(tz_name: str, year: int, month: int, day: int, h: int = 0):
    tz = pytz.timezone(tz_name)
    return tz.localize(datetime(year, month, day, h))


@pytest.mark.unit
class TestPresetRegistry:
    def test_all_presets_have_resolvers(self):
        for preset in ALL_PRESETS:
            if preset == PRESET_CUSTOM:
                # Requires explicit custom_start/custom_end — covered below.
                continue
            scope = resolve_preset(preset, timezone_name="UTC", now=NOW_UTC)
            assert scope.preset == preset


@pytest.mark.unit
class TestCalendarPresetsUTC:
    def test_today_is_one_day_window(self):
        scope = resolve_preset(PRESET_TODAY, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 7, 15)
        assert scope.end == _aware_local("UTC", 2026, 7, 16)
        assert scope.is_open is False

    def test_yesterday_is_one_day_window(self):
        scope = resolve_preset(PRESET_YESTERDAY, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 7, 14)
        assert scope.end == _aware_local("UTC", 2026, 7, 15)

    def test_this_week_starts_monday(self):
        scope = resolve_preset(PRESET_THIS_WEEK, timezone_name="UTC", now=NOW_UTC)
        # 2026-07-15 is a Wednesday; week starts Monday 2026-07-13.
        assert scope.start == _aware_local("UTC", 2026, 7, 13)
        assert scope.end == _aware_local("UTC", 2026, 7, 20)

    def test_last_week_is_the_previous_monday_to_monday(self):
        scope = resolve_preset(PRESET_LAST_WEEK, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 7, 6)
        assert scope.end == _aware_local("UTC", 2026, 7, 13)

    def test_this_month(self):
        scope = resolve_preset(PRESET_THIS_MONTH, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 7, 1)
        assert scope.end == _aware_local("UTC", 2026, 8, 1)

    def test_last_month(self):
        scope = resolve_preset(PRESET_LAST_MONTH, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 6, 1)
        assert scope.end == _aware_local("UTC", 2026, 7, 1)


@pytest.mark.unit
class TestQuarterBoundaries:
    """Quarter is an intentional CE extension (§9.3) — we test three cases:
    Q1, Q2 and Q4 starts.
    """

    @pytest.mark.parametrize(
        ("now_local", "expected_start", "expected_end"),
        [
            # Q1 (Jan-Mar)
            (datetime(2026, 1, 15, 12, tzinfo=pytz.UTC), date(2026, 1, 1), date(2026, 4, 1)),
            # Q2 (Apr-Jun)
            (datetime(2026, 4, 15, 12, tzinfo=pytz.UTC), date(2026, 4, 1), date(2026, 7, 1)),
            # Q4 (Oct-Dec)
            (datetime(2026, 11, 15, 12, tzinfo=pytz.UTC), date(2026, 10, 1), date(2027, 1, 1)),
        ],
    )
    def test_this_quarter_calendar_boundaries(self, now_local, expected_start, expected_end):
        scope = resolve_preset(PRESET_THIS_QUARTER, timezone_name="UTC", now=now_local)
        tz = pytz.timezone("UTC")
        assert scope.start.date() == expected_start
        assert scope.end.date() == expected_end
        assert scope.start.tzinfo == tz
        assert scope.end.tzinfo == tz

    @pytest.mark.parametrize(
        ("now_local", "expected_start", "expected_end"),
        [
            (datetime(2026, 1, 15, 12, tzinfo=pytz.UTC), date(2025, 10, 1), date(2026, 1, 1)),
            (datetime(2026, 4, 15, 12, tzinfo=pytz.UTC), date(2026, 1, 1), date(2026, 4, 1)),
            (datetime(2026, 11, 15, 12, tzinfo=pytz.UTC), date(2026, 7, 1), date(2026, 10, 1)),
        ],
    )
    def test_last_quarter_calendar_boundaries(self, now_local, expected_start, expected_end):
        scope = resolve_preset(PRESET_LAST_QUARTER, timezone_name="UTC", now=now_local)
        assert scope.start.date() == expected_start
        assert scope.end.date() == expected_end


@pytest.mark.unit
class TestYearBoundaries:
    def test_this_year(self):
        scope = resolve_preset(PRESET_THIS_YEAR, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2026, 1, 1)
        assert scope.end == _aware_local("UTC", 2027, 1, 1)

    def test_last_year(self):
        scope = resolve_preset(PRESET_LAST_YEAR, timezone_name="UTC", now=NOW_UTC)
        assert scope.start == _aware_local("UTC", 2025, 1, 1)
        assert scope.end == _aware_local("UTC", 2026, 1, 1)


@pytest.mark.unit
class TestRollingWindows:
    def test_last_30_days_includes_today_and_29_prior(self):
        scope = resolve_preset(PRESET_LAST_30_DAYS, timezone_name="UTC", now=NOW_UTC)
        assert scope.start.date() == date(2026, 6, 16)
        assert scope.end.date() == date(2026, 7, 16)

    def test_last_90_days(self):
        scope = resolve_preset(PRESET_LAST_90_DAYS, timezone_name="UTC", now=NOW_UTC)
        # 2026-07-15 minus 89 days = 2026-04-17; end is the start of the day after ``now``.
        assert scope.start.date() == date(2026, 4, 17)
        assert scope.end.date() == date(2026, 7, 16)


@pytest.mark.unit
class TestCustomRange:
    def test_custom_uses_half_open_interval(self):
        scope = resolve_preset(
            PRESET_CUSTOM,
            timezone_name="UTC",
            custom_start=date(2026, 7, 1),
            custom_end=date(2026, 7, 31),
            now=NOW_UTC,
        )
        # End is exclusive — bumped to start of August 1.
        assert scope.start.date() == date(2026, 7, 1)
        assert scope.end.date() == date(2026, 8, 1)

    def test_custom_rejects_inverted_range(self):
        with pytest.raises(ValueError):
            resolve_preset(
                PRESET_CUSTOM,
                timezone_name="UTC",
                custom_start=date(2026, 7, 31),
                custom_end=date(2026, 7, 1),
                now=NOW_UTC,
            )

    def test_custom_requires_both_dates(self):
        with pytest.raises(ValueError):
            resolve_preset(
                PRESET_CUSTOM,
                timezone_name="UTC",
                custom_start=date(2026, 7, 1),
                custom_end=None,
                now=NOW_UTC,
            )


@pytest.mark.unit
class TestNonePreset:
    def test_none_returns_open_scope(self):
        scope = resolve_preset(PRESET_NONE, timezone_name="UTC", now=NOW_UTC)
        assert scope.is_open is True
        assert scope.start is None and scope.end is None


@pytest.mark.unit
class TestTimezoneRespected:
    """The same UTC moment produces different local calendar boundaries."""

    def test_today_in_asia_different_calendar_day(self):
        # 2026-07-15 10:00 UTC = 2026-07-15 17:00 in Asia/Ho_Chi_Minh
        scope = resolve_preset(PRESET_TODAY, timezone_name="Asia/Ho_Chi_Minh", now=NOW_UTC)
        tz = pytz.timezone("Asia/Ho_Chi_Minh")
        assert scope.start == tz.localize(datetime(2026, 7, 15, 0, 0))
        assert scope.end == tz.localize(datetime(2026, 7, 16, 0, 0))

    def test_utc_endpoints_are_normalised_to_utc(self):
        # 2026-07-15 02:00 UTC = 2026-07-15 11:00 in Australia/Sydney (non-DST)
        scope = resolve_preset(PRESET_TODAY, timezone_name="Australia/Sydney", now=NOW_UTC)
        assert scope.start.tzinfo.zone == "UTC"
        assert scope.end.tzinfo.zone == "UTC"