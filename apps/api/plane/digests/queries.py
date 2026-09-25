# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueRelation,
    Project,
    StateGroup,
    User,
    UserNotificationPreference,
)
from plane.digests.config import DigestConfig
from plane.digests.constants import LEADER_MORNING_BUCKETS, PERSONAL_DAILY_BUCKETS, PRIORITY_RANK
from plane.digests.permissions import get_accessible_project_ids

TERMINAL_STATE_GROUPS = {StateGroup.COMPLETED.value, StateGroup.CANCELLED.value}

# Spec §6.6 + §6.7 — Leader Morning Pulse classifier also considers
# `backlog`/`unstarted` for the "due today, not started" exception and
# high-priority unassigned work. These state groups are NOT terminal but
# they are not "in-progress" either, so they don't qualify for the
# `stale` bucket.
NOT_STARTED_STATE_GROUPS = {StateGroup.BACKLOG.value, StateGroup.UNSTARTED.value}
HIGH_PRIORITIES = {"high", "urgent"}


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


def _issue_to_leader_snapshot_entry(
    issue: Issue, assignee_pairs: list[tuple[str, str]]
) -> dict[str, Any]:
    """Leader digest variant of `_issue_to_snapshot_entry`.

    Includes `assignees` (id + display_name only — no email/avatar, see
    scope decision in RD-449 description: leader email surfaces PII about
    OTHER users and we don't need it to act on the digest). The
    `assignee_pairs` list is `(user_id, display_name)`; pre-fetched by the
    caller to avoid N+1 lookups across all issues.
    """
    entry = _issue_to_snapshot_entry(issue)
    entry["assignees"] = [
        {"id": user_id, "display_name": display_name}
        for user_id, display_name in assignee_pairs
    ]
    return entry


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


# --- Leader Morning Pulse --------------------------------------------------


def get_leader_morning_recipient_ids() -> list[UUID]:
    """Distinct active user ids who are project_lead of at least one
    active project AND have leader-morning enabled.

    The list is the *dispatch* candidate set. It does NOT apply the
    accessibility gate (ProjectMember + WorkspaceMember active) — that
    happens inside `get_leader_morning_sections` per recipient, so we
    don't silently skip leaders whose project lead status is intact but
    whose membership row drifted (see RD-449 access-gate decision: log
    the gap rather than skip at dispatch time).
    """
    lead_user_ids = (
        Project.objects.filter(
            project_lead__isnull=False,
            archived_at__isnull=True,
        )
        .exclude(project_lead__is_active=False)
        .exclude(project_lead__email="")
        .values_list("project_lead_id", flat=True)
        .distinct()
    )

    return list(
        UserNotificationPreference.objects.filter(
            user_id__in=lead_user_ids,
            leader_morning_digest=True,
        ).values_list("user_id", flat=True)
    )


def get_leader_project_ids(user_id: UUID | str) -> set[UUID]:
    """Set of project ids where `user_id` is project_lead AND the project
    is currently accessible to the user (ProjectMember + WorkspaceMember
    active). This is the per-recipient gate — same shape as
    `permissions.get_accessible_project_ids` for personal digests.

    RD-449 access-gate decision: gate both conditions. A leader who lost
    active ProjectMember via PATCH `project_lead` change (api/views/project.py
    does not cascade a new ProjectMember for the new lead) MUST NOT
    receive items from that project in the digest. The gap is logged
    inside `get_leader_morning_sections` via a structured counter so the
    missing membership is visible in observability instead of being a
    silent skip.
    """
    accessible = get_accessible_project_ids(user_id)
    if not accessible:
        return set()

    return set(
        Project.objects.filter(
            pk__in=accessible,
            project_lead_id=user_id,
            archived_at__isnull=True,
        ).values_list("pk", flat=True)
    )


def _classify_leader_bucket(
    issue: Issue,
    today: date,
    blocked_ids: set[UUID],
    has_assignees: bool,
    config: DigestConfig,
    now: datetime,
) -> str | None:
    """Pick ONE bucket for a leader-morning exception. First-match-wins
    in the order declared by `LEADER_MORNING_BUCKETS`:
        overdue -> blocked -> unassigned_high_urgent
        -> due_today_not_started -> stale

    Returns None when the issue is not a leader-morning exception (e.g.
    it's a normal in-progress item with no overdue/block/etc signal —
    leader with 100 normal items and 0 exceptions is the spec §9 skip
    case).
    """
    state_group = issue.state.group if issue.state else None
    if state_group in TERMINAL_STATE_GROUPS:
        return None

    target_date = issue.target_date

    if target_date and target_date < today:
        return "overdue"
    if issue.id in blocked_ids:
        return "blocked"
    if (
        issue.priority in HIGH_PRIORITIES
        and not has_assignees
        and state_group not in TERMINAL_STATE_GROUPS
    ):
        return "unassigned_high_urgent"
    if (
        target_date
        and target_date == today
        and state_group in NOT_STARTED_STATE_GROUPS
    ):
        return "due_today_not_started"
    if (
        state_group == StateGroup.STARTED.value
        and issue.updated_at < now - timedelta(days=config.stale_days)
    ):
        return "stale"
    return None


def get_leader_morning_sections(
    user: User,
    config: DigestConfig,
    now: datetime | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Build the leader-morning section map and the count of projects
    scanned.

    Returns: (sections_by_bucket, projects_scanned_count)

    `projects_scanned_count` is the count of projects that passed BOTH
    gates (project_lead AND accessible). Per RD-449 decision, the
    snapshot stores ONLY this integer — no list of project names — so the
    digest never carries a "full project inventory" that the spec
    explicitly forbids.

    Leader-with-no-active-membership cases are emitted as
    `digest.leader_morning.skipped_no_membership` structured log lines so
    ops can spot gaps without users being silently starved.
    """
    now = now or timezone.now()
    local_now = now.astimezone(config.tzinfo)
    today = local_now.date()

    leader_project_ids = get_leader_project_ids(user.id)

    # Log the access-gate gap: user leads projects in raw Project rows
    # but no project survives the (ProjectMember + WorkspaceMember)
    # filter. We log the COUNT (no project ids) to stay inside the
    # "do not log full snapshot at INFO" rule from spec §21.
    if not leader_project_ids:
        raw_lead_count = Project.objects.filter(
            project_lead_id=user.id,
            archived_at__isnull=True,
        ).count()
        if raw_lead_count > 0:
            import logging

            logging.getLogger("plane.digests.queries").info(
                "digest.leader_morning.skipped_no_membership",
                extra={
                    "recipient_id": str(user.id),
                    "lead_project_count": raw_lead_count,
                },
            )
        return {bucket: [] for bucket in LEADER_MORNING_BUCKETS}, 0

    issues = (
        Issue.objects.filter(
            project_id__in=leader_project_ids,
            deleted_at__isnull=True,
            archived_at__isnull=True,
            is_draft=False,
        )
        .exclude(state__group__in=TERMINAL_STATE_GROUPS)
        .select_related(
            "state",
            "project",
            "project__workspace",
        )
    )

    issue_list = list(issues)
    issue_ids = [issue.id for issue in issue_list]
    blocked_ids = _blocked_issue_ids(issue_ids)

    # Bulk-load assignees per issue. Personal daily doesn't render
    # assignee, but leader digest does (spec §7). Fetching in one query
    # avoids the N+1 the spec §16.1 forbids.
    assignee_rows = (
        IssueAssignee.objects.filter(
            issue_id__in=issue_ids,
            deleted_at__isnull=True,
        )
        .select_related("assignee")
        .values_list("issue_id", "assignee_id", "assignee__display_name")
    )
    assignees_by_issue: dict[UUID, list[tuple[str, str]]] = {}
    for issue_id, user_id, display_name in assignee_rows:
        assignees_by_issue.setdefault(issue_id, []).append(
            (str(user_id), display_name or "")
        )

    classified: dict[UUID, dict[str, Any]] = {}
    for issue in issue_list:
        bucket = _classify_leader_bucket(
            issue,
            today,
            blocked_ids,
            bool(assignees_by_issue.get(issue.id)),
            config,
            now,
        )
        if not bucket:
            continue
        classified[issue.id] = {
            **_issue_to_leader_snapshot_entry(
                issue, assignees_by_issue.get(issue.id, [])
            ),
            "bucket": bucket,
        }

    sections: dict[str, list[dict[str, Any]]] = {
        bucket: [] for bucket in LEADER_MORNING_BUCKETS
    }
    for item in classified.values():
        sections[item["bucket"]].append(item)

    for bucket in LEADER_MORNING_BUCKETS:
        sections[bucket].sort(key=_issue_sort_key)

    return sections, len(leader_project_ids)


def has_leader_exceptions(sections: dict[str, list[dict[str, Any]]]) -> bool:
    """Spec §9 — leader with 100 normal items and 0 exceptions receives
    no email. We treat any non-empty bucket as an exception signal.
    """
    return any(sections.get(bucket) for bucket in LEADER_MORNING_BUCKETS)
