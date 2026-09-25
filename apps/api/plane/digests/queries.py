# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueRelation, StateGroup, User, UserNotificationPreference
from plane.digests.config import DigestConfig
from plane.digests.constants import PERSONAL_DAILY_BUCKETS, PRIORITY_RANK
from plane.digests.permissions import get_accessible_project_ids

TERMINAL_STATE_GROUPS = {StateGroup.COMPLETED.value, StateGroup.CANCELLED.value}


def get_personal_daily_recipient_ids() -> list[UUID]:
    eligible_assignees = (
        IssueAssignee.objects.filter(
            deleted_at__isnull=True,
            assignee__is_active=True,
        )
        .exclude(assignee__email="")
        .filter(
            issue__deleted_at__isnull=True,
            issue__archived_at__isnull=True,
            issue__is_draft=False,
        )
        .exclude(issue__state__group__in=TERMINAL_STATE_GROUPS)
        .values_list("assignee_id", flat=True)
        .distinct()
    )

    return list(
        UserNotificationPreference.objects.filter(
            user_id__in=eligible_assignees,
            personal_daily_digest=True,
        ).values_list("user_id", flat=True)
    )


def _blocked_issue_ids(issue_ids: list[UUID]) -> set[UUID]:
    if not issue_ids:
        return set()

    blocked_relations = IssueRelation.objects.filter(
        issue_id__in=issue_ids,
        relation_type="blocked_by",
        deleted_at__isnull=True,
        related_issue__deleted_at__isnull=True,
    ).exclude(related_issue__state__group__in=TERMINAL_STATE_GROUPS)

    return set(blocked_relations.values_list("issue_id", flat=True))


def _classify_bucket(issue: Issue, today: date, blocked_ids: set[UUID], config: DigestConfig, now: datetime) -> str | None:
    state_group = issue.state.group if issue.state else None
    if state_group in TERMINAL_STATE_GROUPS:
        return None

    target_date = issue.target_date
    if target_date and target_date < today:
        return "overdue"
    if target_date and target_date == today:
        return "due_today"
    if issue.id in blocked_ids:
        return "blocked"
    if target_date and today < target_date <= today + timedelta(days=config.due_soon_days):
        return "due_soon"
    if state_group == StateGroup.STARTED.value and issue.updated_at < now - timedelta(days=config.stale_days):
        return "stale"
    return None


def _issue_sort_key(item: dict[str, Any]) -> tuple:
    return (
        PRIORITY_RANK.get(item.get("priority") or "none", 4),
        item.get("target_date") or date.max,
        item.get("project", {}).get("identifier") or "",
        item.get("sequence_id") or 0,
    )


def _build_issue_url(issue: Issue) -> str:
    base_url = settings.APP_BASE_URL or settings.WEB_URL or ""
    base_url = base_url.rstrip("/")
    return (
        f"{base_url}/{issue.project.workspace.slug}/projects/{issue.project_id}/issues/{issue.id}"
    )


def _issue_to_snapshot_entry(issue: Issue) -> dict[str, Any]:
    return {
        "id": str(issue.id),
        "identifier": f"{issue.project.identifier}-{issue.sequence_id}",
        "name": issue.name,
        "sequence_id": issue.sequence_id,
        "workspace": {
            "id": str(issue.workspace_id),
            "name": issue.project.workspace.name,
            "slug": issue.project.workspace.slug,
        },
        "project": {
            "id": str(issue.project_id),
            "name": issue.project.name,
            "identifier": issue.project.identifier,
        },
        "state": {
            "name": issue.state.name if issue.state else "",
            "group": issue.state.group if issue.state else "",
        },
        "priority": issue.priority,
        "target_date": issue.target_date.isoformat() if issue.target_date else None,
        "assignees": [],
        "url": _build_issue_url(issue),
    }


def get_personal_actionable_items(user: User, config: DigestConfig, now: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
    now = now or timezone.now()
    local_now = now.astimezone(config.tzinfo)
    today = local_now.date()
    accessible_project_ids = get_accessible_project_ids(user.id)

    if not accessible_project_ids:
        return {bucket: [] for bucket in PERSONAL_DAILY_BUCKETS}

    assignments = (
        IssueAssignee.objects.filter(
            assignee_id=user.id,
            deleted_at__isnull=True,
            issue__project_id__in=accessible_project_ids,
            issue__deleted_at__isnull=True,
            issue__archived_at__isnull=True,
            issue__is_draft=False,
        )
        .exclude(issue__state__group__in=TERMINAL_STATE_GROUPS)
        .select_related(
            "issue",
            "issue__state",
            "issue__project",
            "issue__project__workspace",
        )
    )

    issues = [assignment.issue for assignment in assignments]
    issue_ids = [issue.id for issue in issues]
    blocked_ids = _blocked_issue_ids(issue_ids)

    classified: dict[str, dict[str, Any]] = {}
    for issue in issues:
        bucket = _classify_bucket(issue, today, blocked_ids, config, now)
        if not bucket:
            continue
        classified[str(issue.id)] = {**_issue_to_snapshot_entry(issue), "bucket": bucket}

    sections = {bucket: [] for bucket in PERSONAL_DAILY_BUCKETS}
    for item in classified.values():
        sections[item["bucket"]].append(item)

    for bucket in PERSONAL_DAILY_BUCKETS:
        sections[bucket].sort(key=_issue_sort_key)

    return sections


def has_actionable_items(sections: dict[str, list[dict[str, Any]]]) -> bool:
    return any(sections.get(bucket) for bucket in PERSONAL_DAILY_BUCKETS)
