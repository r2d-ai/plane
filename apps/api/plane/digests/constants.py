# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

PERSONAL_DAILY = "personal_daily"
LEADER_MORNING = "leader_morning"
LEADER_WEEKLY = "leader_weekly"

DIGEST_SCHEMA_VERSION = 1

# Keep `schema_version` at 1 across V1 digests. The digest snapshot stored on
# `DigestDelivery` is currently an audit/history row only — there is no code
# path that reads a stored snapshot back to re-render or migrate. Phase 1 of
# `deliver_personal_daily` renders inline at send time, and Phase 2
# `deliver_leader_morning` does the same. `digest_type` is the discriminator
# (it's the third column of the unique constraint), so an old
# `personal_daily` snapshot cannot be confused with a new `leader_morning`
# one. Bumping `schema_version` here without a consumer would just be
# ceremony.

PERSONAL_DAILY_BUCKETS = ("overdue", "due_today", "blocked", "due_soon", "stale")

# Leader Morning Pulse buckets — distinct from PERSONAL_DAILY_BUCKETS because
# the leader view is "what needs intervention this morning" and includes
# two leader-only exceptions:
#   * unassigned_high_urgent — a work item the leader must staff
#   * due_today_not_started  — the leader is the one who unblocks this
# There is no `due_soon` for the morning pulse: spec §4.2 limits morning
# pulse to today's exceptions only, not upcoming ones.
LEADER_MORNING_BUCKETS = (
    "overdue",
    "blocked",
    "unassigned_high_urgent",
    "due_today_not_started",
    "stale",
)

PRIORITY_RANK = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "none": 4,
}

DELIVERY_STATUS_PENDING = "pending"
DELIVERY_STATUS_SENDING = "sending"
DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_FAILED = "failed"

MAX_ITEMS_PER_SECTION = 10
