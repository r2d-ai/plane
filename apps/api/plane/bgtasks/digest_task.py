# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.utils import timezone

from plane.db.models import User, UserNotificationPreference
from plane.digests.config import get_digest_config, is_time_due, is_weekday
from plane.digests.constants import PERSONAL_DAILY
from plane.digests.delivery import deliver_personal_daily
from plane.digests.queries import get_personal_actionable_items, get_personal_daily_recipient_ids, has_actionable_items
from plane.digests.snapshots import build_personal_daily_snapshot
from plane.utils.exception_logger import log_exception

logger = logging.getLogger(__name__)


@shared_task
def dispatch_due_digests():
    config = get_digest_config()
    if not config.enabled:
        return

    local_now = timezone.now().astimezone(config.tzinfo)
    logger.info("digest.dispatch.run", extra={"local_time": local_now.isoformat()})

    if (
        config.personal_daily_enabled
        and is_weekday(local_now)
        and is_time_due(config.personal_daily_time, local_now)
    ):
        period_key = local_now.date().isoformat()
        for user_id in get_personal_daily_recipient_ids():
            generate_personal_daily.delay(str(user_id), period_key)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_personal_daily(self, user_id: str, period_key: str):
    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return "skipped_missing_user"

    if not user.email:
        return "skipped_no_email"

    try:
        preference = UserNotificationPreference.objects.get(user_id=user.id)
    except UserNotificationPreference.DoesNotExist:
        return "skipped_no_preference"

    if not preference.personal_daily_digest:
        logger.info(
            "digest.personal.skipped_disabled",
            extra={"recipient_id": str(user.id), "period_key": period_key},
        )
        return "skipped_disabled"

    config = get_digest_config()
    now = timezone.now()
    sections = get_personal_actionable_items(user, config, now=now)

    if not has_actionable_items(sections):
        logger.info(
            "digest.personal.skipped_empty",
            extra={"recipient_id": str(user.id), "period_key": period_key},
        )
        return "skipped_empty"

    try:
        snapshot = build_personal_daily_snapshot(user, sections, period_key, generated_at=now)
        return deliver_personal_daily(user, snapshot, period_key)
    except Exception as exc:
        log_exception(exc)
        raise self.retry(exc=exc)
