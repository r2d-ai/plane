# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

PERSONAL_DAILY = "personal_daily"
LEADER_MORNING = "leader_morning"
LEADER_WEEKLY = "leader_weekly"

DIGEST_SCHEMA_VERSION = 1

PERSONAL_DAILY_BUCKETS = ("overdue", "due_today", "blocked", "due_soon", "stale")

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
