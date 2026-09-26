# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from plane.bgtasks.digest_task import generate_leader_morning
from plane.db.models import (
    DigestDelivery,
    Issue,
    IssueAssignee,
    IssueRelation,
    Project,
    ProjectMember,
    State,
    User,
    UserNotificationPreference,
    Workspace,
    WorkspaceMember,
)
from plane.digests.config import DigestConfig
from plane.digests.constants import (
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_SENT,
    LEADER_MORNING,
    LEADER_MORNING_BUCKETS,
    PERSONAL_DAILY,
)

from plane.digests.permissions import get_accessible_project_ids
from plane.digests.queries import (
    get_leader_morning_recipient_ids,
    get_leader_morning_sections,
    get_leader_project_ids,
    has_leader_exceptions,
)
from plane.digests.renderers import (
    LEADER_MORNING_SECTION_LABELS,
    render_leader_morning_email,
)
from plane.digests.snapshots import build_leader_morning_snapshot


# --- fixtures --------------------------------------------------------------


@pytest.fixture
def digest_config():
    return DigestConfig(
        enabled=True,
        timezone="UTC",
        personal_daily_enabled=True,
        personal_daily_time=datetime.strptime("08:00", "%H:%M").time(),
        leader_morning_enabled=True,
        leader_morning_time=datetime.strptime("08:15", "%H:%M").time(),
        leader_weekly_enabled=True,
        leader_weekly_day=4,
        leader_weekly_time=datetime.strptime("16:00", "%H:%M").time(),
        due_soon_days=2,
        stale_days=3,
    )


@pytest.fixture
def leader_workspace(db, create_user):
    workspace = Workspace.objects.create(
        name="Leader Workspace",
        slug="leader-workspace",
        owner=create_user,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=create_user, role=20)
    return workspace


@pytest.fixture
def leader_project(db, leader_workspace, create_user):
    project = Project.objects.create(
        name="Leader Project",
        identifier="LDR",
        workspace=leader_workspace,
        created_by=create_user,
        project_lead=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def started_state(db, leader_workspace, leader_project):
    return State.objects.create(
        name="In Progress",
        project=leader_project,
        workspace=leader_workspace,
        group="started",
    )


@pytest.fixture
def backlog_state(db, leader_workspace, leader_project):
    return State.objects.create(
        name="Backlog",
        project=leader_project,
        workspace=leader_workspace,
        group="backlog",
        default=True,
    )


@pytest.fixture
def unstarted_state(db, leader_workspace, leader_project):
    return State.objects.create(
        name="Todo",
        project=leader_project,
        workspace=leader_workspace,
        group="unstarted",
    )


def _create_issue(project, workspace, creator, state, name, *, target_date=None, priority="none", updated_at=None):
    issue = Issue.objects.create(
        name=name,
        workspace=workspace,
        project=project,
        state=state,
        created_by=creator,
        target_date=target_date,
        priority=priority,
    )
    if updated_at:
        Issue.objects.filter(pk=issue.pk).update(updated_at=updated_at)
        issue.refresh_from_db()
    return issue


def _assign(issue, project, workspace, user):
    IssueAssignee.objects.create(
        issue=issue,
        assignee=user,
        project=project,
        workspace=workspace,
    )


def _enable_leader_preference(user):
    pref, _ = UserNotificationPreference.objects.get_or_create(user=user)
    pref.leader_morning_digest = True
    pref.personal_daily_digest = True
    pref.save()
    return pref


# --- recipient discovery ---------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderMorningRecipientDiscovery:
    def test_leads_active_projects_are_picked_up(self, create_user, leader_project):
        _enable_leader_preference(create_user)
        ids = get_leader_morning_recipient_ids()
        assert create_user.id in ids

    def test_inactive_lead_user_is_excluded(self, create_user, leader_project, db):
        _enable_leader_preference(create_user)
        User.objects.filter(pk=create_user.pk).update(is_active=False)
        ids = get_leader_morning_recipient_ids()
        assert create_user.id not in ids

    def test_user_without_email_is_excluded(self, leader_workspace, leader_project, db):
        user = User.objects.create(
            email="",
            username="no_email_leader",
            first_name="No",
            last_name="Email",
        )
        Project.objects.filter(pk=leader_project.pk).update(project_lead=user)
        ProjectMember.objects.create(project=leader_project, member=user, role=20, is_active=True)
        _enable_leader_preference(user)

        ids = get_leader_morning_recipient_ids()
        assert user.id not in ids

    def test_pref_disabled_excludes_from_recipient_list(self, create_user, leader_project):
        pref, _ = UserNotificationPreference.objects.get_or_create(user=create_user)
        pref.leader_morning_digest = False
        pref.save()

        ids = get_leader_morning_recipient_ids()
        assert create_user.id not in ids


# --- per-recipient gate ---------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderProjectGate:
    def test_lead_and_accessible_returns_project(self, create_user, leader_project):
        assert leader_project.id in get_leader_project_ids(create_user.id)

    def test_not_lead_returns_empty(self, create_user, leader_workspace, leader_project, db):
        other = User.objects.create(
            email="other-leader-gate@plane.so",
            username="other_leader_gate",
            first_name="Other",
            last_name="Leader",
        )
        ProjectMember.objects.create(project=leader_project, member=other, role=20, is_active=True)
        assert get_leader_project_ids(other.id) == set()

    def test_lead_without_active_project_membership_returns_empty(
        self, create_user, leader_workspace, leader_project, db
    ):
        # `project_lead_id` says the user leads, but the ProjectMember
        # row was never created (or was deactivated). Gate must exclude
        # this project so no items leak.
        ProjectMember.objects.filter(project=leader_project, member=create_user).update(is_active=False)
        assert get_leader_project_ids(create_user.id) == set()

    def test_revoked_workspace_excludes_lead_project(self, create_user, leader_workspace, leader_project):
        WorkspaceMember.objects.filter(workspace=leader_workspace, member=create_user).update(is_active=False)
        assert get_leader_project_ids(create_user.id) == set()
        assert get_accessible_project_ids(create_user.id) == set()


# --- bucket classification -------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderMorningBuckets:
    def test_overdue_item_lands_in_overdue_bucket(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue item",
            target_date=today - timedelta(days=2),
        )
        _assign(issue, leader_project, leader_workspace, create_user)

        sections, scanned = get_leader_morning_sections(create_user, digest_config)
        assert scanned == 1
        assert len(sections["overdue"]) == 1
        assert sections["overdue"][0]["id"] == str(issue.id)

    def test_blocked_uses_highest_priority_bucket_over_overdue(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        # overdue + blocked must render as overdue (first-match-wins).
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Blocked overdue",
            target_date=today - timedelta(days=2),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        blocker = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Active blocker",
        )
        IssueRelation.objects.create(
            issue=issue,
            related_issue=blocker,
            relation_type="blocked_by",
            project=leader_project,
            workspace=leader_workspace,
        )

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert len(sections["overdue"]) == 1
        assert len(sections["blocked"]) == 0

    def test_blocked_with_completed_blocker_is_not_blocked(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        # The blocker is completed → spec §6.4 says the item is no longer
        # "blocked by" anything. Other classifier rules then take over.
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Was blocked",
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        completed_state = State.objects.create(
            name="Done",
            project=leader_project,
            workspace=leader_workspace,
            group="completed",
        )
        blocker = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            completed_state,
            "Already done blocker",
        )
        IssueRelation.objects.create(
            issue=issue,
            related_issue=blocker,
            relation_type="blocked_by",
            project=leader_project,
            workspace=leader_workspace,
        )

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert len(sections["blocked"]) == 0
        # And `overdue`/`due_today`/etc. only catch it if it matches those
        # rules. With no target_date and a "started" state, it's stale
        # only if updated_at is old enough — so we just assert no exception
        # bucket caught it via the "blocked" rule.
        assert all(
            not any(item["id"] == str(issue.id) for item in sections[bucket])
            for bucket in ("blocked",)
        )

    def test_unassigned_high_urgent_lands_in_unassigned_bucket(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "High prio unassigned",
            priority="high",
        )
        # No `_assign` — leave it unassigned.

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert len(sections["unassigned_high_urgent"]) == 1
        assert sections["unassigned_high_urgent"][0]["id"] == str(issue.id)

    def test_assigned_high_priority_does_not_match_unassigned(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        # Has the priority, but is assigned → not a leader exception.
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Assigned high",
            priority="urgent",
        )
        _assign(issue, leader_project, leader_workspace, create_user)

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert sections["unassigned_high_urgent"] == []
        # And no other bucket matches either (no target_date, not stale
        # yet), so the user is the spec §9 "100 normal items" case.
        assert not has_leader_exceptions(sections)

    def test_low_priority_unassigned_is_not_a_leader_exception(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Low prio unassigned",
            priority="low",
        )

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert sections["unassigned_high_urgent"] == []

    def test_due_today_not_started_lands_in_its_bucket(
        self, create_user, leader_project, leader_workspace, backlog_state, digest_config
    ):
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            backlog_state,
            "Due today, backlog",
            target_date=today,
        )
        _assign(issue, leader_project, leader_workspace, create_user)

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert len(sections["due_today_not_started"]) == 1
        assert sections["due_today_not_started"][0]["id"] == str(issue.id)

    def test_due_today_started_is_not_in_not_started_bucket(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        # target_date == today AND state group == started. The
        # `due_today_not_started` rule excludes started items (they're
        # already in flight); this is a "normal in-progress today" item
        # and not a leader exception.
        today = timezone.now().date()
        _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Due today, started",
            target_date=today,
        )

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert sections["due_today_not_started"] == []

    def test_stale_item_lands_in_stale_bucket(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Stale",
            updated_at=timezone.now() - timedelta(days=10),
        )
        _assign(issue, leader_project, leader_workspace, create_user)

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert len(sections["stale"]) == 1
        assert sections["stale"][0]["id"] == str(issue.id)

    def test_terminal_state_is_excluded(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        done_state = State.objects.create(
            name="Done",
            project=leader_project,
            workspace=leader_workspace,
            group="completed",
        )
        today = timezone.now().date()
        _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            done_state,
            "Already done",
            target_date=today - timedelta(days=1),
            priority="urgent",
        )

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert not has_leader_exceptions(sections)

    def test_normal_in_progress_items_are_not_leader_exceptions(
        self, create_user, leader_project, leader_workspace, started_state, digest_config
    ):
        # Spec §9 "100 normal active work items, 0 exceptions → no email".
        for n in range(5):
            issue = _create_issue(
                leader_project,
                leader_workspace,
                create_user,
                started_state,
                f"Normal item {n}",
                updated_at=timezone.now(),
            )
            _assign(issue, leader_project, leader_workspace, create_user)

        sections, _ = get_leader_morning_sections(create_user, digest_config)
        assert not has_leader_exceptions(sections)
        for bucket in LEADER_MORNING_BUCKETS:
            assert sections[bucket] == []


# --- multi-workspace / cross-project scoping -------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderCrossWorkspace:
    def test_exceptions_across_three_projects_consolidate(
        self, create_user, leader_workspace, leader_project, started_state, digest_config
    ):
        # Three projects led by the same user → one consolidated email
        # with items from all three. Spec §26.2 acceptance.
        project_b = Project.objects.create(
            name="Project B",
            identifier="PRB",
            workspace=leader_workspace,
            created_by=create_user,
            project_lead=create_user,
        )
        ProjectMember.objects.create(project=project_b, member=create_user, role=20, is_active=True)
        started_b = State.objects.create(
            name="In Progress",
            project=project_b,
            workspace=leader_workspace,
            group="started",
        )
        project_c = Project.objects.create(
            name="Project C",
            identifier="PRC",
            workspace=leader_workspace,
            created_by=create_user,
            project_lead=create_user,
        )
        ProjectMember.objects.create(project=project_c, member=create_user, role=20, is_active=True)
        started_c = State.objects.create(
            name="In Progress",
            project=project_c,
            workspace=leader_workspace,
            group="started",
        )

        today = timezone.now().date()
        for project, state in (
            (leader_project, started_state),
            (project_b, started_b),
            (project_c, started_c),
        ):
            issue = _create_issue(
                project,
                leader_workspace,
                create_user,
                state,
                f"{project.name} overdue",
                target_date=today - timedelta(days=1),
            )
            _assign(issue, project, leader_workspace, create_user)

        sections, scanned = get_leader_morning_sections(create_user, digest_config)
        assert scanned == 3
        assert len(sections["overdue"]) == 3

    def test_revoked_workspace_filters_only_that_workspace(
        self, create_user, leader_workspace, leader_project, started_state, digest_config
    ):
        today = timezone.now().date()
        issue_w1 = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "W1 overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue_w1, leader_project, leader_workspace, create_user)

        # Second workspace + project.
        workspace_2 = Workspace.objects.create(
            name="Workspace 2",
            slug="workspace-2",
            owner=create_user,
        )
        WorkspaceMember.objects.create(workspace=workspace_2, member=create_user, role=20)
        project_2 = Project.objects.create(
            name="W2 Project",
            identifier="W2",
            workspace=workspace_2,
            created_by=create_user,
            project_lead=create_user,
        )
        ProjectMember.objects.create(project=project_2, member=create_user, role=20, is_active=True)
        started_2 = State.objects.create(
            name="In Progress",
            project=project_2,
            workspace=workspace_2,
            group="started",
        )
        issue_w2 = _create_issue(
            project_2,
            workspace_2,
            create_user,
            started_2,
            "W2 overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue_w2, project_2, workspace_2, create_user)

        # Revoke W1 only.
        WorkspaceMember.objects.filter(workspace=leader_workspace, member=create_user).update(is_active=False)

        sections, scanned = get_leader_morning_sections(create_user, digest_config)
        # Scanned is the count of projects that passed BOTH gates; W1's
        # project dropped out, W2's project remained.
        assert scanned == 1
        overdue_ids = {item["id"] for item in sections["overdue"]}
        assert str(issue_w2.id) in overdue_ids
        assert str(issue_w1.id) not in overdue_ids


# --- snapshot contract ----------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderMorningSnapshot:
    def test_snapshot_has_required_shape(self, create_user, digest_config):
        sections = {bucket: [] for bucket in LEADER_MORNING_BUCKETS}
        sections["overdue"] = [
            {
                "id": str(uuid4()),
                "identifier": "LDR-1",
                "name": "Test",
                "sequence_id": 1,
                "workspace": {"id": "ws", "name": "WS", "slug": "ws"},
                "project": {"id": "p", "name": "P", "identifier": "LDR"},
                "state": {"name": "In Progress", "group": "started"},
                "priority": "high",
                "target_date": "2026-09-25",
                "assignees": [{"id": "u-1", "display_name": "An Nguyen"}],
                "url": "https://plane.example/x",
                "bucket": "overdue",
            }
        ]
        snapshot = build_leader_morning_snapshot(
            create_user,
            sections,
            "2026-09-26",
            projects_scanned_count=3,
            generated_at=datetime(2026, 9, 26, 8, 15, tzinfo=datetime_timezone.utc),
        )

        assert snapshot["schema_version"] == 1
        assert snapshot["digest_type"] == LEADER_MORNING
        assert snapshot["period_key"] == "2026-09-26"  # bare, no `leader_morning:` prefix
        assert snapshot["projects_scanned_count"] == 3
        assert snapshot["counts"]["overdue"] == 1
        assert snapshot["counts"]["unassigned_high_urgent"] == 0

        # `assignee` is scalar-only: id + display_name, no email/avatar.
        assignee = snapshot["sections"]["overdue"][0]["assignees"][0]
        assert set(assignee.keys()) == {"id", "display_name"}

        # Bucket field is scrubbed before persistence — kept on the live
        # classification map, dropped from the stored snapshot.
        assert "bucket" not in snapshot["sections"]["overdue"][0]

        # Recipient still gets id/display_name/email — that's the
        # recipient themselves, not someone else.
        assert snapshot["recipient"]["id"] == str(create_user.id)

    def test_snapshot_drops_section_when_empty(self, create_user, digest_config):
        sections = {bucket: [] for bucket in LEADER_MORNING_BUCKETS}
        snapshot = build_leader_morning_snapshot(
            create_user, sections, "2026-09-26", projects_scanned_count=0
        )
        for bucket in LEADER_MORNING_BUCKETS:
            assert snapshot["counts"][bucket] == 0
            assert snapshot["sections"][bucket] == []


# --- renderer -------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestLeaderMorningRenderer:
    def _snapshot_with_overdue(self, create_user, count=1):
        return {
            "schema_version": 1,
            "digest_type": LEADER_MORNING,
            "generated_at": "2026-09-26T08:15:00+00:00",
            "period_key": "2026-09-26",
            "recipient": {"id": str(create_user.id), "display_name": "An", "email": create_user.email},
            "projects_scanned_count": 2,
            "counts": {
                "overdue": count,
                "blocked": 0,
                "unassigned_high_urgent": 0,
                "due_today_not_started": 0,
                "stale": 0,
            },
            "sections": {
                "overdue": [
                    {
                        "id": "issue-1",
                        "identifier": "LDR-1",
                        "name": "Test overdue",
                        "workspace": {"id": "ws", "name": "WS Name", "slug": "ws-slug"},
                        "project": {"id": "p", "name": "Project", "identifier": "LDR"},
                        "state": {"name": "In Progress", "group": "started"},
                        "priority": "high",
                        "target_date": "2026-09-24",
                        "assignees": [{"id": "u-2", "display_name": "An Nguyen"}],
                        "url": "https://plane.example/x",
                    }
                ]
                * count,
                "blocked": [],
                "unassigned_high_urgent": [],
                "due_today_not_started": [],
                "stale": [],
            },
        }

    def test_subject_includes_exception_count(self, create_user):
        snapshot = self._snapshot_with_overdue(create_user, count=4)
        subject, html, text = render_leader_morning_email(
            snapshot, LEADER_MORNING_BUCKETS, LEADER_MORNING_SECTION_LABELS
        )
        assert "4" in subject
        assert "Morning Pulse" in subject

    def test_renderer_uses_passed_labels(self, create_user):
        snapshot = self._snapshot_with_overdue(create_user, count=1)
        custom_labels = dict(LEADER_MORNING_SECTION_LABELS)
        custom_labels["overdue"] = "CUSTOM-OVERDUE"
        subject, html, _ = render_leader_morning_email(
            snapshot, LEADER_MORNING_BUCKETS, custom_labels
        )
        assert "CUSTOM-OVERDUE" in html

    def test_renderer_keyerrors_on_mismatched_label_keys(self, create_user):
        # If the caller passes the personal-daily labels, the leader-only
        # buckets (`unassigned_high_urgent`, `due_today_not_started`)
        # KeyError as soon as a bucket with items is reached. The guard
        # is data-dependent — an item MUST exist in one of the leader-only
        # buckets to trigger the KeyError. This is the contract the
        # (buckets, labels) parameterization enforces for the
        # "realistically-misused" direction (calling leader renderer with
        # a personal snapshot whose `unassigned_high_urgent` /
        # `due_today_not_started` happened to be non-empty).
        snapshot = self._snapshot_with_overdue(create_user, count=1)
        snapshot["sections"]["unassigned_high_urgent"] = [
            {
                "id": "issue-2",
                "identifier": "LDR-2",
                "name": "Unassigned high",
                "workspace": {"id": "ws", "name": "WS Name", "slug": "ws-slug"},
                "project": {"id": "p", "name": "Project", "identifier": "LDR"},
                "state": {"name": "In Progress", "group": "started"},
                "priority": "high",
                "target_date": "",
                "assignees": [],
                "url": "https://plane.example/x",
            }
        ]
        snapshot["counts"]["unassigned_high_urgent"] = 1
        personal_labels = {
            "overdue": "Overdue",
            "due_today": "Due today",
            "blocked": "Blocked",
            "due_soon": "Due soon",
            "stale": "Stale",
        }
        with pytest.raises(KeyError):
            render_leader_morning_email(snapshot, LEADER_MORNING_BUCKETS, personal_labels)

    def test_html_escapes_user_controlled_title(self, create_user):
        # Work-item title contains HTML; it must render as text, not as a
        # tag. This guards the renderer-side `escape` that Django's
        # template auto-escapes for, plus the snapshot contract that
        # `name` is a scalar.
        snapshot = self._snapshot_with_overdue(create_user, count=1)
        snapshot["sections"]["overdue"][0]["name"] = '<script>alert("x")</script>'
        _, html, _ = render_leader_morning_email(
            snapshot, LEADER_MORNING_BUCKETS, LEADER_MORNING_SECTION_LABELS
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# --- end-to-end dispatcher task -------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
class TestGenerateLeaderMorning:
    @patch("plane.digests.delivery.send_digest_email")
    def test_no_exceptions_skips_email(self, mock_send, create_user, leader_project, leader_workspace, started_state):
        _enable_leader_preference(create_user)
        # Normal item, no exception.
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Normal",
            updated_at=timezone.now(),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "skipped_empty"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @patch("plane.digests.delivery.send_digest_email")
    def test_exception_triggers_one_email(
        self, mock_send, create_user, leader_project, leader_workspace, started_state
    ):
        _enable_leader_preference(create_user)
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "sent"
        assert DigestDelivery.objects.count() == 1
        row = DigestDelivery.objects.first()
        assert row.digest_type == LEADER_MORNING
        assert row.period_key == period_key
        assert row.recipient_id == create_user.id

    @patch("plane.digests.delivery.send_digest_email")
    def test_pref_disabled_skips_email(self, mock_send, create_user, leader_project, leader_workspace, started_state):
        pref, _ = UserNotificationPreference.objects.get_or_create(user=create_user)
        pref.leader_morning_digest = False
        pref.save()
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "skipped_disabled"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @patch("plane.digests.delivery.send_digest_email")
    def test_no_email_skips_when_user_has_none(self, mock_send, create_user, leader_project):
        User.objects.filter(pk=create_user.pk).update(email="")
        _enable_leader_preference(create_user)
        period_key = timezone.now().date().isoformat()

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "skipped_no_email"
        mock_send.assert_not_called()

    @patch("plane.digests.delivery.send_digest_email")
    def test_lead_without_membership_logs_and_skips(
        self, mock_send, create_user, leader_workspace, leader_project, started_state
    ):
        # Raw Project.project_lead points at the user but the ProjectMember
        # row was deactivated. Gate rejects, structured log fires,
        # task returns skipped_empty. The user is NOT delivered items
        # from this project.
        _enable_leader_preference(create_user)
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Mystery overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        ProjectMember.objects.filter(project=leader_project, member=create_user).update(is_active=False)
        period_key = timezone.now().date().isoformat()

        with self._assert_logs("digest.leader_morning.skipped_no_membership"):
            result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "skipped_empty"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @staticmethod
    def _assert_logs(log_record_name):
        """Helper for asserting a particular log line was emitted at
        INFO level. Implemented as a context manager so each test stays
        one expression. We don't cap the count because the dispatcher
        itself emits digest.dispatch.run too.

        We MUST set the logger level to INFO on the target logger in
        `__enter__`. Why: under `DJANGO_SETTINGS_MODULE=plane.settings.
        production`, the `plane.digests.queries` namespace was missing
        from `LOGGING["loggers"]` until RD-449 fix 1; root default is
        WARNING, so without an explicit `setLevel(INFO)` here the INFO
        record is dropped at the logger level — not just at the
        (already-INFO) handler. That's exactly the bug that hid
        `digest.leader_morning.skipped_no_membership` in production.
        Don't simplify this back to "just addHandler".
        """
        import logging

        class _Capture(logging.Handler):
            def __init__(self):
                super().__init__(level=logging.INFO)
                self.records = []

            def emit(self, record):
                self.records.append(record)

        capture = _Capture()

        class _Ctx:
            def __enter__(self_inner):
                logger = logging.getLogger("plane.digests.queries")
                self_inner._previous_level = logger.level
                logger.setLevel(logging.INFO)
                logger.addHandler(capture)
                return capture

            def __exit__(self_inner, exc_type, exc, tb):
                logger = logging.getLogger("plane.digests.queries")
                logger.removeHandler(capture)
                logger.setLevel(self_inner._previous_level)
                names = [r.__dict__.get("name") or r.name for r in capture.records]
                msg = f"expected log record '{log_record_name}', got: {names}"
                ok = any(
                    log_record_name in str(r.msg)
                    or log_record_name in str(getattr(r, "message", ""))
                    for r in capture.records
                )
                if not ok:
                    raise AssertionError(msg)
                return False

        return _Ctx()

    @patch("plane.digests.delivery.send_digest_email")
    def test_duplicate_period_returns_duplicate(
        self, mock_send, create_user, leader_project, leader_workspace, started_state
    ):
        _enable_leader_preference(create_user)
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        first = generate_leader_morning(str(create_user.id), period_key)
        second = generate_leader_morning(str(create_user.id), period_key)
        assert first == "sent"
        assert second == "duplicate"
        assert DigestDelivery.objects.count() == 1
        mock_send.assert_called_once()

    @patch("plane.digests.delivery.send_digest_email")
    def test_retry_after_failure_reclaims(
        self, mock_send, create_user, leader_project, leader_workspace, started_state
    ):
        # Same CAS invariant Phase 1 has: a second attempt after SMTP
        # failure must reclaim the FAILED row, not silently swallow.
        mock_send.side_effect = [RuntimeError("smtp timeout"), None]
        _enable_leader_preference(create_user)
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        with pytest.raises(RuntimeError):
            generate_leader_morning(str(create_user.id), period_key)
        row = DigestDelivery.objects.get(
            recipient=create_user,
            digest_type=LEADER_MORNING,
            period_key=period_key,
        )
        assert row.status == DELIVERY_STATUS_FAILED
        assert row.error == "smtp timeout"

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "sent"
        row.refresh_from_db()
        assert row.status == DELIVERY_STATUS_SENT
        assert DigestDelivery.objects.count() == 1

    @patch("plane.digests.delivery.send_digest_email")
    def test_personal_and_leader_use_independent_period_keys(
        self,
        mock_send,
        create_user,
        leader_project,
        leader_workspace,
        started_state,
        digest_config,
    ):
        # Different `digest_type` discriminator → unique constraint does
        # not collide. Same period_key is fine across digest types.
        _enable_leader_preference(create_user)
        today = timezone.now().date()
        issue = _create_issue(
            leader_project,
            leader_workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=today - timedelta(days=1),
        )
        _assign(issue, leader_project, leader_workspace, create_user)
        period_key = timezone.now().date().isoformat()

        # Pre-create a personal_daily row for the same user/period_key
        # — leader morning must still create its own row.
        DigestDelivery.objects.create(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key=period_key,
            status=DELIVERY_STATUS_SENT,
            sent_at=timezone.now(),
            scheduled_at=timezone.now(),
            snapshot={"digest_type": PERSONAL_DAILY, "counts": {}},
        )

        result = generate_leader_morning(str(create_user.id), period_key)
        assert result == "sent"
        assert DigestDelivery.objects.filter(digest_type=LEADER_MORNING).count() == 1
        assert DigestDelivery.objects.filter(digest_type=PERSONAL_DAILY).count() == 1
