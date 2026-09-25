# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from dataclasses import dataclass
from datetime import datetime, time

from zoneinfo import ZoneInfo


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_time(value: str | None, default: time) -> time:
    if not value:
        return default
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M")
        return time(parsed.hour, parsed.minute)
    except ValueError:
        return default


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class DigestConfig:
    enabled: bool
    timezone: str
    personal_daily_enabled: bool
    personal_daily_time: time
    leader_morning_enabled: bool
    leader_morning_time: time
    leader_weekly_enabled: bool
    leader_weekly_day: int
    leader_weekly_time: time
    due_soon_days: int
    stale_days: int

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def get_digest_config() -> DigestConfig:
    return DigestConfig(
        enabled=_parse_bool(os.environ.get("DIGEST_ENABLED"), default=True),
        timezone=os.environ.get("DIGEST_TIMEZONE", "UTC"),
        personal_daily_enabled=_parse_bool(os.environ.get("DIGEST_PERSONAL_DAILY_ENABLED"), default=True),
        personal_daily_time=_parse_time(os.environ.get("DIGEST_PERSONAL_DAILY_TIME"), time(8, 0)),
        leader_morning_enabled=_parse_bool(os.environ.get("DIGEST_LEADER_MORNING_ENABLED"), default=True),
        leader_morning_time=_parse_time(os.environ.get("DIGEST_LEADER_MORNING_TIME"), time(8, 15)),
        leader_weekly_enabled=_parse_bool(os.environ.get("DIGEST_LEADER_WEEKLY_ENABLED"), default=True),
        leader_weekly_day=_parse_int(os.environ.get("DIGEST_LEADER_WEEKLY_DAY"), 4),
        leader_weekly_time=_parse_time(os.environ.get("DIGEST_LEADER_WEEKLY_TIME"), time(16, 0)),
        due_soon_days=_parse_int(os.environ.get("DIGEST_DUE_SOON_DAYS"), 2),
        stale_days=_parse_int(os.environ.get("DIGEST_STALE_DAYS"), 3),
    )


def is_time_due(scheduled: time, local_now: datetime) -> bool:
    """Return True when `local_now` is inside the 5-minute dispatch window that
    opens at `scheduled` (in `local_now`'s tz).

    Compares absolute elapsed seconds rather than local-minute components so
    the window stays correct for timezones with non-zero-minute offsets such
    as Asia/Kolkata (+5:30) or Asia/Kathmandu (+5:45). Previously this
    compared `hour * 60 + minute` in local time, which silently dropped the
    digest when the scheduler's :00/:05/:10... grid landed in a window the
    local-minute math couldn't represent.
    """
    scheduled_dt = datetime.combine(
        local_now.date(), scheduled, tzinfo=local_now.tzinfo
    )
    delta_seconds = (local_now - scheduled_dt).total_seconds()
    return 0 <= delta_seconds < 300


def is_weekday(local_now: datetime) -> bool:
    return local_now.weekday() < 5
