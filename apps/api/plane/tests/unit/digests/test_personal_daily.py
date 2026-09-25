# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.utils import timezone

from plane.bgtasks.digest_task import generate_personal_daily
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
from plane.digests.config import DigestConfig, get_digest_config, is_time_due
from plane.digests.constants import (
    DELIVERY_STATUS_FAILED,
    DELIVERY_STATUS_PENDING,
    DELIVERY_STATUS_SENT,
    PERSONAL_DAILY,
    PERSONAL_DAILY_BUCKETS,
)
from plane.digests.delivery import claim_delivery, deliver_personal_daily
from plane.digests.permissions import get_accessible_project_ids
from plane.digests.queries import get_personal_actionable_items, has_actionable_items
from plane.digests.snapshots import build_personal_daily_snapshot


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
def digest_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Digest Project",
        identifier="DIG",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def started_state(db, workspace, digest_project):
    return State.objects.create(
        name="In Progress",
        project=digest_project,
        workspace=workspace,
        group="started",
    )


@pytest.fixture
def backlog_state(db, workspace, digest_project):
    return State.objects.create(
        name="Backlog",
        project=digest_project,
        workspace=workspace,
        group="backlog",
        default=True,
    )


def _create_assigned_issue(project, workspace, user, state, name, target_date=None, updated_at=None):
    issue = Issue.objects.create(
        name=name,
        workspace=workspace,
        project=project,
        state=state,
        created_by=user,
        target_date=target_date,
    )
    IssueAssignee.objects.create(issue=issue, assignee=user, project=project, workspace=workspace)
    if updated_at:
        Issue.objects.filter(pk=issue.pk).update(updated_at=updated_at)
        issue.refresh_from_db()
    return issue


@pytest.mark.unit
@pytest.mark.django_db
class TestPersonalDailyQueries:
    def test_overdue_and_due_today_items_are_classified(self, create_user, workspace, digest_project, started_state, digest_config):
        today = timezone.now().date()
        overdue = _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Overdue issue",
            target_date=today - timedelta(days=2),
        )
        due_today = _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Due today issue",
            target_date=today,
        )
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Future issue",
            target_date=today + timedelta(days=30),
        )

        sections = get_personal_actionable_items(create_user, digest_config)
        overdue_ids = {item["id"] for item in sections["overdue"]}
        due_today_ids = {item["id"] for item in sections["due_today"]}

        assert str(overdue.id) in overdue_ids
        assert str(due_today.id) in due_today_ids
        assert has_actionable_items(sections)

    def test_non_actionable_work_returns_empty_sections(self, create_user, workspace, digest_project, backlog_state, digest_config):
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            backlog_state,
            "Future only",
            target_date=timezone.now().date() + timedelta(days=30),
        )

        sections = get_personal_actionable_items(create_user, digest_config)
        assert not has_actionable_items(sections)

    def test_inaccessible_project_is_excluded(self, create_user, workspace, digest_project, started_state, digest_config, db):
        other_user = User.objects.create(
            email="other-digest@plane.so",
            username="other_digest_user",
            first_name="Other",
            last_name="User",
        )
        private_project = Project.objects.create(
            name="Private Project",
            identifier="PRV",
            workspace=workspace,
            created_by=other_user,
        )
        private_state = State.objects.create(
            name="Private Started",
            project=private_project,
            workspace=workspace,
            group="started",
        )
        _create_assigned_issue(
            private_project,
            workspace,
            create_user,
            private_state,
            "Should not appear",
            target_date=timezone.now().date() - timedelta(days=1),
        )

        sections = get_personal_actionable_items(create_user, digest_config)
        assert not has_actionable_items(sections)

    def test_blocked_item_uses_highest_priority_bucket(self, create_user, workspace, digest_project, started_state, digest_config):
        today = timezone.now().date()
        issue = _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Blocked overdue",
            target_date=today - timedelta(days=1),
        )
        blocker = Issue.objects.create(
            name="Blocker",
            workspace=workspace,
            project=digest_project,
            state=started_state,
            created_by=create_user,
        )
        IssueRelation.objects.create(
            issue=issue,
            related_issue=blocker,
            relation_type="blocked_by",
            project=digest_project,
            workspace=workspace,
        )

        sections = get_personal_actionable_items(create_user, digest_config)
        assert len(sections["overdue"]) == 1
        assert len(sections["blocked"]) == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestDigestDelivery:
    @patch("plane.digests.delivery.send_digest_email")
    def test_duplicate_delivery_is_prevented(self, mock_send, create_user, digest_config):
        sections = {"overdue": [], "due_today": [], "blocked": [], "due_soon": [], "stale": []}
        snapshot = build_personal_daily_snapshot(create_user, sections, "2026-09-25")
        snapshot["counts"]["overdue"] = 1
        snapshot["sections"]["overdue"] = [{"identifier": "DIG-1", "name": "Test"}]

        first = claim_delivery(create_user, PERSONAL_DAILY, "2026-09-25", snapshot)
        second = claim_delivery(create_user, PERSONAL_DAILY, "2026-09-25", snapshot)

        assert first is not None
        assert second is None
        assert DigestDelivery.objects.count() == 1

    @patch("plane.digests.delivery.send_digest_email")
    def test_empty_digest_is_not_delivered(self, mock_send, create_user):
        preference = UserNotificationPreference.objects.get(user=create_user)
        preference.personal_daily_digest = True
        preference.save()

        result = generate_personal_daily(str(create_user.id), timezone.now().date().isoformat())

        assert result == "skipped_empty"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @patch("plane.digests.delivery.send_digest_email")
    def test_opt_out_prevents_delivery(self, mock_send, create_user, workspace, digest_project, started_state):
        preference = UserNotificationPreference.objects.get(user=create_user)
        preference.personal_daily_digest = False
        preference.save()

        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=timezone.now().date() - timedelta(days=1),
        )

        result = generate_personal_daily(str(create_user.id), timezone.now().date().isoformat())

        assert result == "skipped_disabled"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @patch("plane.digests.delivery.send_digest_email")
    def test_one_consolidated_delivery_per_period(self, mock_send, create_user, workspace, digest_project, started_state):
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=timezone.now().date() - timedelta(days=1),
        )
        period_key = timezone.now().date().isoformat()

        first = generate_personal_daily(str(create_user.id), period_key)
        second = generate_personal_daily(str(create_user.id), period_key)

        assert first == "sent"
        assert second == "duplicate"
        assert DigestDelivery.objects.count() == 1
        mock_send.assert_called_once()

    @patch("plane.digests.delivery.send_digest_email")
    def test_retry_after_send_failure_reclaims_failed_row(self, mock_send, create_user, workspace, digest_project, started_state):
        # First attempt: SMTP fails.
        mock_send.side_effect = [
            RuntimeError("smtp timeout"),
            None,
        ]
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Overdue",
            target_date=timezone.now().date() - timedelta(days=1),
        )
        period_key = timezone.now().date().isoformat()

        with pytest.raises(RuntimeError):
            generate_personal_daily(str(create_user.id), period_key)

        row = DigestDelivery.objects.get(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key=period_key,
        )
        assert row.status == DELIVERY_STATUS_FAILED
        assert row.error == "smtp timeout"
        assert row.failed_at is not None
        assert mock_send.call_count == 1

        # Second attempt: row is reclaimed (FAILED → PENDING) and email is
        # actually sent this time. Before the CAS fix this re-delivery was
        # silently swallowed by the unique constraint and the user never
        # received the digest.
        result = generate_personal_daily(str(create_user.id), period_key)
        assert result == "sent"
        row.refresh_from_db()
        assert row.status == DELIVERY_STATUS_SENT
        assert row.error == ""
        assert row.failed_at is None
        assert DigestDelivery.objects.count() == 1
        assert mock_send.call_count == 2

    @patch("plane.digests.delivery.send_digest_email")
    def test_concurrent_reclaim_of_failed_row_only_sends_once(self, mock_send, create_user, digest_config):
        # Two reclaim attempts against the same FAILED row (e.g. a retry and
        # the next dispatch tick). CAS guarantees exactly one winner; the
        # loser must NOT call send_digest_email, otherwise duplicate-send is
        # possible the moment the loser continues past claim_delivery.
        sections = {"overdue": [], "due_today": [], "blocked": [], "due_soon": [], "stale": []}
        snapshot = build_personal_daily_snapshot(create_user, sections, "2026-09-25")
        snapshot["counts"]["overdue"] = 1
        snapshot["sections"]["overdue"] = [{"identifier": "DIG-1", "name": "Test"}]

        DigestDelivery.objects.create(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key="2026-09-25",
            status=DELIVERY_STATUS_FAILED,
            error="previous failure",
            failed_at=timezone.now(),
            scheduled_at=timezone.now(),
            snapshot=snapshot,
        )

        first = deliver_personal_daily(create_user, snapshot, "2026-09-25")
        second = deliver_personal_daily(create_user, snapshot, "2026-09-25")

        assert first == "sent"
        assert second == "duplicate"
        assert DigestDelivery.objects.count() == 1
        mock_send.assert_called_once()

        row = DigestDelivery.objects.get(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key="2026-09-25",
        )
        assert row.status == DELIVERY_STATUS_SENT
        assert row.error == ""
        assert row.failed_at is None

    def test_claim_delivery_on_failed_row_clears_error_and_failed_at(self, create_user):
        # Reclaim transitions the row FAILED → PENDING and wipes the prior
        # error / failed_at so the snapshot reflects a fresh attempt. If a
        # refactor drops the `error=""` / `failed_at=None` from the CAS
        # update, this catches the stale-failure leak.
        snapshot = build_personal_daily_snapshot(
            create_user,
            {"overdue": [], "due_today": [], "blocked": [], "due_soon": [], "stale": []},
            "2026-09-25",
        )
        previous_failure_at = timezone.now() - timedelta(hours=1)
        DigestDelivery.objects.create(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key="2026-09-25",
            status=DELIVERY_STATUS_FAILED,
            error="smtp timeout",
            failed_at=previous_failure_at,
            scheduled_at=previous_failure_at,
            snapshot=snapshot,
        )

        reclaimed = claim_delivery(create_user, PERSONAL_DAILY, "2026-09-25", snapshot)

        assert reclaimed is not None
        assert reclaimed.status == DELIVERY_STATUS_PENDING
        assert reclaimed.error == ""
        assert reclaimed.failed_at is None
        assert reclaimed.scheduled_at > previous_failure_at

    def test_second_claim_on_same_failed_row_returns_none(self, create_user):
        # Direct test of the invariant Alex called out: two `claim_delivery`
        # calls back-to-back against the same FAILED row. The first call
        # wins the CAS and returns the reclaimed row (now PENDING); the
        # second call sees status=PENDING (not FAILED), so the CAS guard
        # `filter(pk, status=FAILED)` matches zero rows and the function
        # returns None.
        #
        # If a refactor drops `status=FAILED` from the CAS filter, the
        # second call's filter still matches (the row exists), `updated`
        # becomes 1, the function returns the row, and downstream code is
        # free to send the same digest twice. This test fails on that
        # regression; the higher-level "send once" assertion alone would
        # not, because it only sees the row after it has already moved to
        # SENT.
        snapshot = build_personal_daily_snapshot(
            create_user,
            {"overdue": [], "due_today": [], "blocked": [], "due_soon": [], "stale": []},
            "2026-09-25",
        )
        DigestDelivery.objects.create(
            recipient=create_user,
            digest_type=PERSONAL_DAILY,
            period_key="2026-09-25",
            status=DELIVERY_STATUS_FAILED,
            error="previous failure",
            failed_at=timezone.now(),
            scheduled_at=timezone.now(),
            snapshot=snapshot,
        )

        first = claim_delivery(create_user, PERSONAL_DAILY, "2026-09-25", snapshot)
        second = claim_delivery(create_user, PERSONAL_DAILY, "2026-09-25", snapshot)

        assert first is not None
        assert first.status == DELIVERY_STATUS_PENDING
        assert second is None
        assert DigestDelivery.objects.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestRevocationGate:
    """Defense-in-depth against the PATCH-revoke bypass described in the
    security review.

    `PATCH /api/workspaces/{slug}/members/{member_id}/` with
    `{"is_active": false}` deactivates only `WorkspaceMember`; unlike
    `destroy` / `leave`, it does NOT cascade to `ProjectMember`. Without
    a workspace-level check the digest would still pick up issues from
    projects the user has been removed from at the workspace boundary.
    These tests guard `digests/permissions.get_accessible_project_ids`
    plus the downstream `get_personal_actionable_items` /
    `generate_personal_daily` paths that consume it.
    """

    @patch("plane.digests.delivery.send_digest_email")
    def test_revoked_workspace_excludes_actionable_items_and_delivery(
        self, mock_send, create_user, workspace, digest_project, started_state, digest_config
    ):
        # Project membership is still active; only the workspace boundary
        # has been revoked. Before the fix, `get_personal_actionable_items`
        # returned the issue and `generate_personal_daily` would deliver
        # an email containing it.
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Revoked workspace issue",
            target_date=timezone.now().date() - timedelta(days=1),
        )
        period_key = timezone.now().date().isoformat()

        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(is_active=False)

        # Permission gate now returns empty.
        assert get_accessible_project_ids(create_user.id) == set()

        sections = get_personal_actionable_items(create_user, digest_config)
        assert not has_actionable_items(sections)
        for bucket in PERSONAL_DAILY_BUCKETS:
            assert sections[bucket] == []

        # End-to-end: dispatcher task does not send and does not create a
        # delivery row.
        result = generate_personal_daily(str(create_user.id), period_key)
        assert result == "skipped_empty"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

    @patch("plane.digests.delivery.send_digest_email")
    def test_revoked_workspace_only_filters_that_workspace(
        self, mock_send, create_user, workspace, digest_project, started_state, digest_config
    ):
        # Multi-workspace setup: workspace (W1) plus a second workspace
        # (W2) each with their own project, issue, and ProjectMember.
        # Revoking W1 must NOT take W2 down with it.
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "W1 overdue",
            target_date=timezone.now().date() - timedelta(days=1),
        )

        workspace_2 = Workspace.objects.create(
            name="Second Workspace",
            slug="second-workspace",
            owner=create_user,
        )
        WorkspaceMember.objects.create(workspace=workspace_2, member=create_user, role=20)
        project_2 = Project.objects.create(
            name="W2 Project",
            identifier="W2",
            workspace=workspace_2,
            created_by=create_user,
        )
        ProjectMember.objects.create(project=project_2, member=create_user, role=20, is_active=True)
        started_state_2 = State.objects.create(
            name="In Progress",
            project=project_2,
            workspace=workspace_2,
            group="started",
        )
        _create_assigned_issue(
            project_2,
            workspace_2,
            create_user,
            started_state_2,
            "W2 overdue",
            target_date=timezone.now().date() - timedelta(days=1),
        )

        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(is_active=False)

        accessible = get_accessible_project_ids(create_user.id)
        assert digest_project.id not in accessible
        assert project_2.id in accessible

        sections = get_personal_actionable_items(create_user, digest_config)
        assert has_actionable_items(sections)
        workspace_names = {
            entry["workspace"]["name"]
            for bucket in PERSONAL_DAILY_BUCKETS
            for entry in sections[bucket]
        }
        assert "Test Workspace" not in workspace_names
        assert "Second Workspace" in workspace_names

        # And the digest actually delivers, scoped to the surviving workspace.
        result = generate_personal_daily(
            str(create_user.id), timezone.now().date().isoformat()
        )
        assert result == "sent"
        mock_send.assert_called_once()
        assert DigestDelivery.objects.count() == 1

    @patch("plane.digests.delivery.send_digest_email")
    def test_reactivated_workspace_member_restores_digest(
        self, mock_send, create_user, workspace, digest_project, started_state, digest_config
    ):
        # State check: the gate follows `WorkspaceMember.is_active` on every
        # call (it is not "stuck off" once revoked). Revoke → no delivery;
        # re-activate → delivery resumes. This guards against the gate
        # getting accidentally memoized or stuck on a one-shot "deleted"
        # flag.
        _create_assigned_issue(
            digest_project,
            workspace,
            create_user,
            started_state,
            "Re-activatable issue",
            target_date=timezone.now().date() - timedelta(days=1),
        )
        period_key = timezone.now().date().isoformat()
        member = WorkspaceMember.objects.get(workspace=workspace, member=create_user)

        member.is_active = False
        member.save()
        assert get_accessible_project_ids(create_user.id) == set()
        sections = get_personal_actionable_items(create_user, digest_config)
        assert not has_actionable_items(sections)
        assert generate_personal_daily(str(create_user.id), period_key) == "skipped_empty"
        mock_send.assert_not_called()
        assert DigestDelivery.objects.count() == 0

        member.is_active = True
        member.save()
        assert digest_project.id in get_accessible_project_ids(create_user.id)
        sections = get_personal_actionable_items(create_user, digest_config)
        assert has_actionable_items(sections)
        assert generate_personal_daily(str(create_user.id), period_key) == "sent"
        mock_send.assert_called_once()
        assert DigestDelivery.objects.count() == 1


@pytest.mark.unit
class TestIsTimeDue:
    """Unit tests for the dispatch-window predicate.

    Behaviour under non-zero-minute offsets (IST +5:30, NPT +5:45) used to
    silently drop the digest because the comparison used `hour*60+minute`
    in local time and could miss the beat's :00/:05/:10... grid.
    """

    def test_window_open(self):
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 8, 1, tzinfo=ist)
        assert is_time_due(time(8, 0), local_now) is True

    def test_window_close(self):
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 8, 5, tzinfo=ist)
        assert is_time_due(time(8, 0), local_now) is False

    def test_window_before_scheduled(self):
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 7, 59, tzinfo=ist)
        assert is_time_due(time(8, 0), local_now) is False

    def test_window_within_five_minutes_after_scheduled(self):
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 8, 4, 30, tzinfo=ist)
        assert is_time_due(time(8, 0), local_now) is True

    def test_window_matches_when_ist_offset_is_30_minutes(self):
        # Scheduled 08:00 IST; dispatcher firing 1 minute into the window.
        # The previous hour-based predicate still matched this case but
        # the assertion guards against a regression.
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 8, 1, tzinfo=ist)
        assert is_time_due(time(8, 0), local_now) is True

    def test_window_matches_when_npt_offset_is_45_minutes(self):
        # Asia/Kathmandu is UTC+5:45. The beat never visits minutes like
        # :46 / :47 in local time, so a naive `hour*60+minute` comparison
        # could never trigger the 08:00 schedule here. The replacement
        # uses absolute elapsed seconds, which works for any IANA tz.
        npt = ZoneInfo("Asia/Kathmandu")
        local_now = datetime(2026, 9, 25, 8, 1, tzinfo=npt)
        assert is_time_due(time(8, 0), local_now) is True

    def test_window_off_grid_minute_in_ist(self):
        # A scheduled minute that never lines up with the beat's
        # :00/:05/.../:55 grid in IST +5:30 (e.g. 08:08 IST). The
        # dispatcher fires at the next grid stop after 08:08, which is
        # 08:10 IST (= 02:40 UTC). The predicate must still return True
        # at 08:10 because the window is [08:08, 08:13).
        ist = ZoneInfo("Asia/Kolkata")
        local_now = datetime(2026, 9, 25, 8, 10, tzinfo=ist)
        assert is_time_due(time(8, 8), local_now) is True


@pytest.mark.unit
@pytest.mark.django_db
class TestDigestPreferences:
    def test_existing_users_default_digest_preferences_to_true(self, create_user):
        preference = UserNotificationPreference.objects.get(user=create_user)
        assert preference.personal_daily_digest is True
        assert preference.leader_morning_digest is True
        assert preference.leader_weekly_digest is True

    def test_notification_preference_patch_does_not_reset_digest_fields(self, session_client, create_user):
        preference = UserNotificationPreference.objects.get(user=create_user)
        preference.personal_daily_digest = False
        preference.save()

        response = session_client.patch(
            "/api/users/me/notification-preferences/",
            {"property_change": False},
            format="json",
        )

        assert response.status_code == 200
        preference.refresh_from_db()
        assert preference.property_change is False
        assert preference.personal_daily_digest is False
