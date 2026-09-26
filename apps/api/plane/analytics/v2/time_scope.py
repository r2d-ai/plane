# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Time scope resolution for Analytics V2 (spec §9, §38).

Resolves presets and custom ranges in the workspace's timezone. Returns
``(start, end)`` as timezone-aware UTC datetimes using the half-open
``[start, end)`` convention to avoid double-counting across adjacent periods.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_tz
from typing import Optional, Tuple

import pytz


# Preset names — kept stable so persisted query configs survive schema bumps.
PRESET_TODAY = "today"
PRESET_YESTERDAY = "yesterday"
PRESET_THIS_WEEK = "this_week"
PRESET_LAST_WEEK = "last_week"
PRESET_LAST_7_DAYS = "last_7_days"
PRESET_LAST_30_DAYS = "last_30_days"
PRESET_THIS_MONTH = "this_month"
PRESET_LAST_MONTH = "last_month"
PRESET_THIS_QUARTER = "this_quarter"
PRESET_LAST_QUARTER = "last_quarter"
PRESET_LAST_90_DAYS = "last_90_days"
PRESET_THIS_YEAR = "this_year"
PRESET_LAST_YEAR = "last_year"
PRESET_CUSTOM = "custom"
PRESET_NONE = "none"

ALL_PRESETS = frozenset(
    {
        PRESET_TODAY,
        PRESET_YESTERDAY,
        PRESET_THIS_WEEK,
        PRESET_LAST_WEEK,
        PRESET_LAST_7_DAYS,
        PRESET_LAST_30_DAYS,
        PRESET_THIS_MONTH,
        PRESET_LAST_MONTH,
        PRESET_THIS_QUARTER,
        PRESET_LAST_QUARTER,
        PRESET_LAST_90_DAYS,
        PRESET_THIS_YEAR,
        PRESET_LAST_YEAR,
        PRESET_CUSTOM,
        PRESET_NONE,
    }
)

DATE_BASIS_CREATED = "created_at"
DATE_BASIS_COMPLETED = "completed_at"
DATE_BASIS_START = "start_date"
DATE_BASIS_TARGET = "target_date"
DATE_BASIS_LIFECYCLE = "lifecycle_overlap"

ALL_DATE_BASIS = frozenset(
    {
        DATE_BASIS_CREATED,
        DATE_BASIS_COMPLETED,
        DATE_BASIS_START,
        DATE_BASIS_TARGET,
        DATE_BASIS_LIFECYCLE,
    }
)

DATE_GROUP_DAY = "day"
DATE_GROUP_WEEK = "week"
DATE_GROUP_MONTH = "month"
DATE_GROUP_QUARTER = "quarter"
DATE_GROUP_YEAR = "year"

ALL_DATE_GROUPS = frozenset(
    {
        DATE_GROUP_DAY,
        DATE_GROUP_WEEK,
        DATE_GROUP_MONTH,
        DATE_GROUP_QUARTER,
        DATE_GROUP_YEAR,
    }
)


@dataclass(frozen=True)
class ResolvedTimeScope:
    """A preset/custom range resolved into UTC timestamps. ``start`` is inclusive,
    ``end`` is exclusive (``[start, end)``). ``None`` means the caller asked for
    *No time range* — a current-state snapshot — and any time filtering should
    be skipped.
    """

    start: Optional[datetime]
    end: Optional[datetime]
    timezone: str
    preset: str

    @property
    def is_open(self) -> bool:
        return self.start is None and self.end is None


def _local_now(tz_name: str) -> Tuple[datetime, pytz.tzinfo.BaseTzInfo]:
    tz = pytz.timezone(tz_name) if tz_name else pytz.UTC
    return datetime.now(tz=tz), tz


def _to_utc(local_dt: datetime) -> datetime:
    """Convert a tz-aware datetime to UTC. Raises on naive input — callers must
    always pass a tz-aware datetime so daylight-savings bugs are caught loudly."""
    if local_dt.tzinfo is None:
        raise ValueError("ResolvedTimeScope requires timezone-aware datetimes")
    return local_dt.astimezone(pytz.UTC)


def _start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _start_of_week(d: date) -> date:
    """Monday-anchored ISO week start."""
    return d - timedelta(days=d.weekday())


def _start_of_month(d: date) -> date:
    return d.replace(day=1)


def _start_of_quarter(d: date) -> date:
    q = (d.month - 1) // 3  # 0..3
    return date(d.year, q * 3 + 1, 1)


def _start_of_year(d: date) -> date:
    return date(d.year, 1, 1)


def _local(dt: date, tz: pytz.tzinfo.BaseTzInfo) -> datetime:
    return tz.localize(datetime.combine(dt, time.min))


def resolve_preset(
    preset: str,
    *,
    timezone_name: str = "UTC",
    custom_start: Optional[date] = None,
    custom_end: Optional[date] = None,
    now: Optional[datetime] = None,
) -> ResolvedTimeScope:
    """Resolve a preset (or ``custom``) into a UTC-bounded scope.

    All local boundaries are computed in ``timezone_name``; only the returned
    values are normalised to UTC for storage and comparison.
    """
    if preset not in ALL_PRESETS:
        raise ValueError(f"Unknown time preset: {preset!r}")

    if preset == PRESET_NONE:
        return ResolvedTimeScope(start=None, end=None, timezone=timezone_name, preset=preset)

    if preset == PRESET_CUSTOM:
        if not custom_start or not custom_end:
            raise ValueError("Custom time range requires both start and end")
        # Coerce string-typed input — clients typically pass ISO dates.
        if isinstance(custom_start, str):
            custom_start = date.fromisoformat(custom_start)
        if isinstance(custom_end, str):
            custom_end = date.fromisoformat(custom_end)
        if custom_end < custom_start:
            raise ValueError("Custom time range end must be >= start")
        tz = pytz.timezone(timezone_name) if timezone_name else pytz.UTC
        start_local = tz.localize(datetime.combine(custom_start, time.min))
        # end is exclusive: bump to start of next day so the caller can use a half-open interval
        end_local = tz.localize(datetime.combine(custom_end + timedelta(days=1), time.min))
        return ResolvedTimeScope(
            start=_to_utc(start_local),
            end=_to_utc(end_local),
            timezone=timezone_name,
            preset=preset,
        )

    tz_name = timezone_name or "UTC"
    tz = pytz.timezone(tz_name)
    if now is None:
        local_now, tz = _local_now(tz_name)
    else:
        # Trust the provided ``now`` only if it is already tz-aware.
        local_now = now.astimezone(tz) if now.tzinfo else tz.localize(now)
    today_local = local_now.date()

    if preset == PRESET_TODAY:
        start_local = tz.localize(datetime.combine(today_local, time.min))
        end_local = tz.localize(datetime.combine(today_local + timedelta(days=1), time.min))
    elif preset == PRESET_YESTERDAY:
        y = today_local - timedelta(days=1)
        start_local = tz.localize(datetime.combine(y, time.min))
        end_local = tz.localize(datetime.combine(today_local, time.min))
    elif preset == PRESET_LAST_7_DAYS:
        start_local = tz.localize(datetime.combine(today_local - timedelta(days=6), time.min))
        end_local = tz.localize(datetime.combine(today_local + timedelta(days=1), time.min))
    elif preset == PRESET_LAST_30_DAYS:
        start_local = tz.localize(datetime.combine(today_local - timedelta(days=29), time.min))
        end_local = tz.localize(datetime.combine(today_local + timedelta(days=1), time.min))
    elif preset == PRESET_LAST_90_DAYS:
        start_local = tz.localize(datetime.combine(today_local - timedelta(days=89), time.min))
        end_local = tz.localize(datetime.combine(today_local + timedelta(days=1), time.min))
    elif preset == PRESET_THIS_WEEK:
        ws = _start_of_week(today_local)
        start_local = tz.localize(datetime.combine(ws, time.min))
        end_local = tz.localize(datetime.combine(ws + timedelta(days=7), time.min))
    elif preset == PRESET_LAST_WEEK:
        ws = _start_of_week(today_local) - timedelta(days=7)
        start_local = tz.localize(datetime.combine(ws, time.min))
        end_local = tz.localize(datetime.combine(ws + timedelta(days=7), time.min))
    elif preset == PRESET_THIS_MONTH:
        ms = _start_of_month(today_local)
        start_local = tz.localize(datetime.combine(ms, time.min))
        # advance one calendar month
        if ms.month == 12:
            next_month = ms.replace(year=ms.year + 1, month=1)
        else:
            next_month = ms.replace(month=ms.month + 1)
        end_local = tz.localize(datetime.combine(next_month, time.min))
    elif preset == PRESET_LAST_MONTH:
        ms = _start_of_month(today_local)
        if ms.month == 1:
            prev_month = ms.replace(year=ms.year - 1, month=12)
        else:
            prev_month = ms.replace(month=ms.month - 1)
        start_local = tz.localize(datetime.combine(prev_month, time.min))
        end_local = tz.localize(datetime.combine(ms, time.min))
    elif preset == PRESET_THIS_QUARTER:
        qs = _start_of_quarter(today_local)
        start_local = tz.localize(datetime.combine(qs, time.min))
        next_q_year = qs.year + (1 if qs.month == 10 else 0)
        next_q_month = 1 if qs.month == 10 else qs.month + 3
        end_local = tz.localize(datetime.combine(date(next_q_year, next_q_month, 1), time.min))
    elif preset == PRESET_LAST_QUARTER:
        qs = _start_of_quarter(today_local)
        if qs.month == 1:
            prev_q_year = qs.year - 1
            prev_q_month = 10
        else:
            prev_q_year = qs.year
            prev_q_month = qs.month - 3
        prev_q = date(prev_q_year, prev_q_month, 1)
        start_local = tz.localize(datetime.combine(prev_q, time.min))
        end_local = tz.localize(datetime.combine(qs, time.min))
    elif preset == PRESET_THIS_YEAR:
        ys = _start_of_year(today_local)
        start_local = tz.localize(datetime.combine(ys, time.min))
        end_local = tz.localize(datetime.combine(date(ys.year + 1, 1, 1), time.min))
    elif preset == PRESET_LAST_YEAR:
        ys = _start_of_year(today_local)
        prev_ys = date(ys.year - 1, 1, 1)
        start_local = tz.localize(datetime.combine(prev_ys, time.min))
        end_local = tz.localize(datetime.combine(ys, time.min))
    else:  # pragma: no cover — ALL_PRESETS guards above
        raise ValueError(f"Unknown time preset: {preset!r}")

    return ResolvedTimeScope(
        start=_to_utc(start_local),
        end=_to_utc(end_local),
        timezone=tz_name,
        preset=preset,
    )


def apply_time_basis(queryset, basis: str, scope: ResolvedTimeScope):
    """Apply a date basis filter to a queryset. ``scope.is_open`` skips
    filtering (used for ``none``/snapshot metrics)."""

    if basis not in ALL_DATE_BASIS:
        raise ValueError(f"Unknown date basis: {basis!r}")
    if scope.is_open:
        return queryset

    start, end = scope.start, scope.end
    if basis == DATE_BASIS_CREATED:
        return queryset.filter(created_at__gte=start, created_at__lt=end)
    if basis == DATE_BASIS_COMPLETED:
        return queryset.filter(completed_at__gte=start, completed_at__lt=end)
    if basis == DATE_BASIS_START:
        return queryset.filter(start_date__gte=start.date(), start_date__lt=end.date())
    if basis == DATE_BASIS_TARGET:
        return queryset.filter(target_date__gte=start.date(), target_date__lt=end.date())
    if basis == DATE_BASIS_LIFECYCLE:
        # created_at <= range.end AND (completed_at IS NULL OR completed_at >= range.start)
        return queryset.filter(created_at__lt=end).filter(
            models_q_or_null("completed_at", start)
        )
    raise ValueError(f"Unknown date basis: {basis!r}")


def models_q_or_null(field: str, start):
    """Internal helper: ``field IS NULL OR field >= start``. Exposed for the
    lifecycle_overlap basis only."""
    from django.db.models import Q

    return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gte": start})