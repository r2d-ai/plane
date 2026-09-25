# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from typing import Any

from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import IntegrityError, transaction
from django.utils import timezone

from plane.db.models import DigestDelivery, User
from plane.digests.constants import (
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_PENDING,
    DELIVERY_STATUS_SENT,
    DELIVERY_STATUS_SENDING,
    LEADER_MORNING,
    LEADER_MORNING_BUCKETS,
)
from plane.digests.renderers import (
    LEADER_MORNING_SECTION_LABELS,
    render_leader_morning_email,
    render_personal_daily_email,
)
from plane.license.utils.instance_value import get_email_configuration
from plane.utils.exception_logger import log_exception

logger = logging.getLogger(__name__)


def claim_delivery(recipient: User, digest_type: str, period_key: str, snapshot: dict[str, Any]) -> DigestDelivery | None:
    try:
        with transaction.atomic():
            delivery = DigestDelivery.objects.create(
                recipient=recipient,
                digest_type=digest_type,
                period_key=period_key,
                status=DELIVERY_STATUS_PENDING,
                snapshot=snapshot,
                scheduled_at=timezone.now(),
            )
            return delivery
    except IntegrityError:
        existing = (
            DigestDelivery.objects.filter(
                recipient=recipient,
                digest_type=digest_type,
                period_key=period_key,
            )
            .only("id", "status", "snapshot")
            .first()
        )
        if existing is None:
            logger.info(
                "digest.delivery.duplicate_prevented",
                extra={
                    "recipient_id": str(recipient.id),
                    "digest_type": digest_type,
                    "period_key": period_key,
                },
            )
            return None

        updated = DigestDelivery.objects.filter(
            pk=existing.pk, status=DELIVERY_STATUS_FAILED
        ).update(
            status=DELIVERY_STATUS_PENDING,
            error="",
            failed_at=None,
            snapshot=snapshot,
            scheduled_at=timezone.now(),
        )
        if updated != 1:
            logger.info(
                "digest.delivery.duplicate_prevented",
                extra={
                    "recipient_id": str(recipient.id),
                    "digest_type": digest_type,
                    "period_key": period_key,
                    "existing_status": existing.status,
                },
            )
            return None

        logger.info(
            "digest.delivery.reclaimed",
            extra={
                "recipient_id": str(recipient.id),
                "digest_type": digest_type,
                "period_key": period_key,
            },
        )
        return DigestDelivery.objects.get(pk=existing.pk)


def send_digest_email(recipient: User, subject: str, html_content: str, text_content: str) -> None:
    (
        EMAIL_HOST,
        EMAIL_HOST_USER,
        EMAIL_HOST_PASSWORD,
        EMAIL_PORT,
        EMAIL_USE_TLS,
        EMAIL_USE_SSL,
        EMAIL_FROM,
    ) = get_email_configuration()

    connection = get_connection(
        host=EMAIL_HOST,
        port=int(EMAIL_PORT),
        username=EMAIL_HOST_USER,
        password=EMAIL_HOST_PASSWORD,
        use_tls=EMAIL_USE_TLS == "1",
        use_ssl=EMAIL_USE_SSL == "1",
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=EMAIL_FROM,
        to=[recipient.email],
        connection=connection,
    )
    message.attach_alternative(html_content, "text/html")
    message.send()


def deliver_personal_daily(recipient: User, snapshot: dict[str, Any], period_key: str) -> str:
    delivery = claim_delivery(recipient, snapshot["digest_type"], period_key, snapshot)
    if delivery is None:
        return "duplicate"

    try:
        delivery.status = DELIVERY_STATUS_SENDING
        delivery.save(update_fields=["status", "updated_at"])

        subject, html_content, text_content = render_personal_daily_email(snapshot)
        send_digest_email(recipient, subject, html_content, text_content)

        delivery.status = DELIVERY_STATUS_SENT
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "sent_at", "updated_at"])
        logger.info(
            "digest.personal.sent",
            extra={
                "recipient_id": str(recipient.id),
                "period_key": period_key,
            },
        )
        return "sent"
    except Exception as exc:
        log_exception(exc)
        delivery.status = DELIVERY_STATUS_FAILED
        delivery.failed_at = timezone.now()
        delivery.error = str(exc)[:1000]
        delivery.save(update_fields=["status", "failed_at", "error", "updated_at"])
        logger.info(
            "digest.personal.failed",
            extra={
                "recipient_id": str(recipient.id),
                "period_key": period_key,
            },
        )
        raise


def deliver_leader_morning(recipient: User, snapshot: dict[str, Any], period_key: str) -> str:
    """Deliver the Leader Morning Pulse digest.

    Reuses `claim_delivery` (CAS on the unique constraint, FAILED → PENDING
    reclaim) and `send_digest_email` from Phase 1 — only the renderer
    changes. The bucket + label pair is passed explicitly to the renderer
    so a future caller cannot accidentally feed a personal-daily snapshot
    here and KeyError on the missing leader-only labels.
    """
    delivery = claim_delivery(recipient, LEADER_MORNING, period_key, snapshot)
    if delivery is None:
        return "duplicate"

    try:
        delivery.status = DELIVERY_STATUS_SENDING
        delivery.save(update_fields=["status", "updated_at"])

        subject, html_content, text_content = render_leader_morning_email(
            snapshot,
            LEADER_MORNING_BUCKETS,
            LEADER_MORNING_SECTION_LABELS,
        )
        send_digest_email(recipient, subject, html_content, text_content)

        delivery.status = DELIVERY_STATUS_SENT
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "sent_at", "updated_at"])
        logger.info(
            "digest.leader_morning.sent",
            extra={
                "recipient_id": str(recipient.id),
                "period_key": period_key,
            },
        )
        return "sent"
    except Exception as exc:
        log_exception(exc)
        delivery.status = DELIVERY_STATUS_FAILED
        delivery.failed_at = timezone.now()
        delivery.error = str(exc)[:1000]
        delivery.save(update_fields=["status", "failed_at", "error", "updated_at"])
        logger.info(
            "digest.leader_morning.failed",
            extra={
                "recipient_id": str(recipient.id),
                "period_key": period_key,
            },
        )
        raise
