# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timedelta
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
)
from plane.digests.config import DigestConfig, get_digest_config
from plane.digests.constants import PERSONAL_DAILY
from plane.digests.delivery import claim_delivery, deliver_personal_daily
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
