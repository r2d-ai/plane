# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Comparison period resolution for Analytics V2 (spec §10).

Given a :class:`ResolvedTimeScope` (current period), compute the matching
comparison period for each of:

* ``previous_period``         — calendar-aligned equivalent length
* ``previous_week``           — the ISO week immediately before
* ``previous_month``          — the calendar month immediately before
* ``previous_quarter``        — the calendar quarter immediately before
* ``previous_year``           — the calendar year immediately before
* ``none``                    — disabled
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

import pytz

from .time_scope import ResolvedTimeScope, _to_utc


COMPARISON_NONE = "none"
COMPARISON_PREVIOUS_PERIOD = "previous_period"
COMPARISON_PREVIOUS_WEEK = "previous_week"
COMPARISON_PREVIOUS_MONTH = "previous_month"
COMPARISON_PREVIOUS_QUARTER = "previous_quarter"
COMPARISON_PREVIOUS_YEAR = "previous_year"

ALL_COMPARISONS = frozenset(
    {
        COMPARISON_NONE,
        COMPARISON_PREVIOUS_PERIOD,
        COMPARISON_PREVIOUS_WEEK,
        COMPARISON_PREVIOUS_MONTH,
        COMPARISON_PREVIOUS_QUARTER,
        COMPARISON_PREVIOUS_YEAR,
    }
)


@dataclass(frozen=True)
class ResolvedComparison:
    """The comparison window aligned to the current ``ResolvedTimeScope``.

    ``previous`` uses the same length as ``current`` and is exclusive on the
    right (``[previous.start, previous.end)``). It is in the same timezone as
    the current scope.
    """

    type: str
    previous: ResolvedTimeScope


def _shift_month(d: date, months: int) -> date:
    total = (d.year * 12 + (d.month - 1)) + months
    y, m = divmod(total, 12)
    return date(y, m + 1, 1)


def _quarter_of(d: date) -> int:
    return (d.month - 1) // 3  # 0..3


def resolve_comparison(
    current: ResolvedTimeScope, comparison_type: str
) -> Optional[ResolvedComparison]:
    """Return the comparison scope for ``current``, or ``None`` when comparison is
    disabled (``none``) or ``current`` is an open scope."""

    if comparison_type not in ALL_COMPARISONS:
        raise ValueError(f"Unknown comparison type: {comparison_type!r}")
    if comparison_type == COMPARISON_NONE:
        return None
    if current.is_open:
        return None

    tz = pytz.timezone(current.timezone) if current.timezone else pytz.UTC

    if comparison_type == COMPARISON_PREVIOUS_PERIOD:
        length = current.end - current.start
        # current is UTC; shift back by length, anchor to the original tz midnight
        start_local = (current.start - length).astimezone(tz)
        end_local = current.start.astimezone(tz)
        return ResolvedComparison(
            type=comparison_type,
            previous=ResolvedTimeScope(
                start=_to_utc(start_local),
                end=_to_utc(end_local),
                timezone=current.timezone,
                preset="comparison",
            ),
        )

    if comparison_type == COMPARISON_PREVIOUS_WEEK:
        cur_start_local = current.start.astimezone(tz).date()
        iso_monday = cur_start_local - timedelta(days=cur_start_local.weekday())
        # if the current window starts on a Monday this still moves 7 days
        prev_start = iso_monday - timedelta(days=7)
        prev_end = iso_monday
        start_local = tz.localize(datetime.combine(prev_start, time.min))
        end_local = tz.localize(datetime.combine(prev_end, time.min))
        return ResolvedComparison(
            type=comparison_type,
            previous=ResolvedTimeScope(
                start=_to_utc(start_local),
                end=_to_utc(end_local),
                timezone=current.timezone,
                preset="comparison",
            ),
        )

    if comparison_type == COMPARISON_PREVIOUS_MONTH:
        cur_start_local = current.start.astimezone(tz).date()
        start_local_date = _shift_month(_shift_month(cur_start_local.replace(day=1), 0), -1)
        end_local_date = _shift_month(cur_start_local.replace(day=1), 0)
        start_local = tz.localize(datetime.combine(start_local_date, time.min))
        end_local = tz.localize(datetime.combine(end_local_date, time.min))
        return ResolvedComparison(
            type=comparison_type,
            previous=ResolvedTimeScope(
                start=_to_utc(start_local),
                end=_to_utc(end_local),
                timezone=current.timezone,
                preset="comparison",
            ),
        )

    if comparison_type == COMPARISON_PREVIOUS_QUARTER:
        cur_start_local = current.start.astimezone(tz).date()
        cur_q = _quarter_of(cur_start_local)
        cur_q_start = date(cur_start_local.year, cur_q * 3 + 1, 1)
        prev_q_start = _shift_month(cur_q_start, -3)
        start_local = tz.localize(datetime.combine(prev_q_start, time.min))
        end_local = tz.localize(datetime.combine(cur_q_start, time.min))
        return ResolvedComparison(
            type=comparison_type,
            previous=ResolvedTimeScope(
                start=_to_utc(start_local),
                end=_to_utc(end_local),
                timezone=current.timezone,
                preset="comparison",
            ),
        )

    if comparison_type == COMPARISON_PREVIOUS_YEAR:
        cur_start_local = current.start.astimezone(tz).date()
        cur_y_start = date(cur_start_local.year, 1, 1)
        prev_y_start = date(cur_y_start.year - 1, 1, 1)
        start_local = tz.localize(datetime.combine(prev_y_start, time.min))
        end_local = tz.localize(datetime.combine(cur_y_start, time.min))
        return ResolvedComparison(
            type=comparison_type,
            previous=ResolvedTimeScope(
                start=_to_utc(start_local),
                end=_to_utc(end_local),
                timezone=current.timezone,
                preset="comparison",
            ),
        )

    raise ValueError(f"Unknown comparison type: {comparison_type!r}")