# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime
from typing import Any

from django.utils import timezone

from plane.db.models import User
from plane.digests.constants import (
    DIGEST_SCHEMA_VERSION,
    LEADER_MORNING,
    LEADER_MORNING_BUCKETS,
    PERSONAL_DAILY,
    PERSONAL_DAILY_BUCKETS,
)


def build_personal_daily_snapshot(
    user: User,
    sections: dict[str, list[dict[str, Any]]],
    period_key: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or timezone.now()
    clean_sections = {
        bucket: [
            {key: value for key, value in item.items() if key != "bucket"}
            for item in sections.get(bucket, [])
        ]
        for bucket in PERSONAL_DAILY_BUCKETS
    }

    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "digest_type": PERSONAL_DAILY,
        "generated_at": generated_at.isoformat(),
        "period_key": period_key,
        "recipient": {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
        },
        "counts": {bucket: len(clean_sections.get(bucket, [])) for bucket in PERSONAL_DAILY_BUCKETS},
        "sections": clean_sections,
    }


def build_leader_morning_snapshot(
    user: User,
    sections: dict[str, list[dict[str, Any]]],
    period_key: str,
    projects_scanned_count: int,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a V1 Leader Morning Pulse snapshot.

    Shape decisions baked in here (do not move to template):

    * `assignee` per item is `{id, display_name}` only — no email, no
      avatar URL. Spec §17.5: work-item content is untrusted data;
      surfacing OTHER users' email in the leader's digest is a PII
      surface we don't need.
    * `projects_scanned_count` is a single integer. Spec §4.2 forbids
      "full project inventory"; spec §17.4 forbids dumping everything
      and letting the renderer hide rows. The leader signal we keep is
      "how many projects did this digest actually scan?" — enough for
      the leader to know coverage without leaking names.
    * `schema_version` stays at `DIGEST_SCHEMA_VERSION` (1). RD-449
      decision: no consumer reads the stored snapshot back, so
      back-compat layers would be dead code. The `digest_type` column
      is the discriminator.
    """
    generated_at = generated_at or timezone.now()
    clean_sections = {
        bucket: [
            {key: value for key, value in item.items() if key != "bucket"}
            for item in sections.get(bucket, [])
        ]
        for bucket in LEADER_MORNING_BUCKETS
    }

    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "digest_type": LEADER_MORNING,
        "generated_at": generated_at.isoformat(),
        "period_key": period_key,
        "recipient": {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
        },
        "projects_scanned_count": int(projects_scanned_count),
        "counts": {
            bucket: len(clean_sections.get(bucket, []))
            for bucket in LEADER_MORNING_BUCKETS
        },
        "sections": clean_sections,
    }
