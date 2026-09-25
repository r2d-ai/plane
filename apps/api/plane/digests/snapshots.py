# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime
from typing import Any

from django.utils import timezone

from plane.db.models import User
from plane.digests.constants import DIGEST_SCHEMA_VERSION, PERSONAL_DAILY, PERSONAL_DAILY_BUCKETS


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
