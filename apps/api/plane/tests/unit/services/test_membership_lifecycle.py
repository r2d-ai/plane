# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Unit tests for ``plane.app.services.membership_lifecycle``.

These exercise the row-level state transitions directly, without going
through HTTP. The HTTP-level behavior is covered by:

* ``tests/contract/app/test_workspace_member_revoke_cascade.py``
* ``tests/contract/api/test_project_lead_membership.py``

These unit tests exist so future refactors of the service can be
re-validated cheaply without spinning up the URL routing layer.
"""

import pytest

from plane.app.services.membership_lifecycle import (
    ensure_project_lead_membership,
    revoke_workspace_member,
)
from plane.db.models import (
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)


def _make_user(email: str) -> User:
    local_part = email.split("@")[0]
    user = User.objects.create(email=email, username=local_part, first_name=local_part)
    user.set_password("test-password")
    user.save()
    return user


@pytest.fixture
def workspace(db):
    owner = _make_user("owner@plane.so")
    ws = Workspace.objects.create(name="T", slug="t", owner=owner)
    WorkspaceMember.objects.create(workspace=ws, member=owner, role=20)
    return ws


@pytest.mark.unit
@pytest.mark.django_db
class TestRevokeWorkspaceMember:
    def test_deactivates_workspace_member(self, workspace):
        user = _make_user("u@plane.so")
        ws_member = WorkspaceMember.objects.create(
            workspace=workspace, member=user, role=15, is_active=True
        )

        revoke_workspace_member(ws_member)

        ws_member.refresh_from_db()
        assert ws_member.is_active is False

    def test_cascades_to_project_member(self, workspace):
        user = _make_user("u@plane.so")
        ws_member = WorkspaceMember.objects.create(
            workspace=workspace, member=user, role=15, is_active=True
        )
        proj = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=user
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=user, role=20, is_active=True
        )

        revoke_workspace_member(ws_member)

        pm = ProjectMember.objects.get(project=proj, member=user)
        assert pm.is_active is False

    def test_does_not_touch_other_workspace_members(self, workspace):
        victim = _make_user("victim@plane.so")
        bystander = _make_user("bystander@plane.so")
        victim_ws = WorkspaceMember.objects.create(
            workspace=workspace, member=victim, role=15, is_active=True
        )
        bystander_ws = WorkspaceMember.objects.create(
            workspace=workspace, member=bystander, role=15, is_active=True
        )

        revoke_workspace_member(victim_ws)

        bystander_ws.refresh_from_db()
        assert bystander_ws.is_active is True

    def test_idempotent_on_second_call(self, workspace):
        user = _make_user("u@plane.so")
        ws_member = WorkspaceMember.objects.create(
            workspace=workspace, member=user, role=15, is_active=True
        )

        revoke_workspace_member(ws_member)
        revoke_workspace_member(ws_member)  # second call must not raise

        ws_member.refresh_from_db()
        assert ws_member.is_active is False

    def test_does_not_affect_already_inactive_project_members(self, workspace):
        """Idempotency: rows that were already inactive before the call
        stay inactive -- they aren't re-touched, which would bump
        ``updated_at`` spuriously."""
        user = _make_user("u@plane.so")
        ws_member = WorkspaceMember.objects.create(
            workspace=workspace, member=user, role=15, is_active=True
        )
        proj = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=user
        )
        already_inactive = ProjectMember.objects.create(
            workspace=workspace,
            project=proj,
            member=user,
            role=20,
            is_active=False,
        )
        from django.utils import timezone
        # Force updated_at into the past so we can detect a write.
        past = timezone.now()
        already_inactive.updated_at = past
        already_inactive.save()

        revoke_workspace_member(ws_member)

        already_inactive.refresh_from_db()
        # updated_at preserved: the WHERE is_active=True filter skipped this row.
        assert already_inactive.updated_at.replace(microsecond=0) == past.replace(microsecond=0)


@pytest.mark.unit
@pytest.mark.django_db
class TestEnsureProjectLeadMembership:
    def test_creates_membership_when_absent(self, workspace):
        project = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=workspace.owner
        )
        lead = _make_user("lead@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=lead, role=15)

        ensure_project_lead_membership(project.id, lead.id, workspace.id)

        pm = ProjectMember.objects.get(project=project, member=lead)
        assert pm.is_active is True
        assert pm.role == 20

    def test_reactivates_inactive_membership(self, workspace):
        project = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=workspace.owner
        )
        lead = _make_user("lead@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=lead, role=15)
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=lead, role=15, is_active=False
        )

        ensure_project_lead_membership(project.id, lead.id, workspace.id)

        pm = ProjectMember.objects.get(project=project, member=lead)
        assert pm.is_active is True
        assert pm.role == 20

    def test_promotes_role_without_changing_is_active(self, workspace):
        project = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=workspace.owner
        )
        lead = _make_user("lead@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=lead, role=5)
        ProjectMember.objects.create(
            workspace=workspace, project=project, member=lead, role=5, is_active=True
        )

        ensure_project_lead_membership(project.id, lead.id, workspace.id)

        pm = ProjectMember.objects.get(project=project, member=lead)
        assert pm.is_active is True
        assert pm.role == 20

    def test_noop_when_already_correct(self, workspace):
        """If the lead already has active role=20 membership, the
        service must NOT bump ``updated_at`` -- the WHERE clause filters
        on active row presence and no UPDATE fires.
        """
        from django.utils import timezone
        project = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=workspace.owner
        )
        lead = _make_user("lead@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=lead, role=15)
        pm = ProjectMember.objects.create(
            workspace=workspace, project=project, member=lead, role=20, is_active=True
        )
        original_updated_at = pm.updated_at

        ensure_project_lead_membership(project.id, lead.id, workspace.id)

        pm.refresh_from_db()
        assert pm.updated_at == original_updated_at

    def test_none_lead_id_is_noop(self, workspace):
        """Defensive: a None ``new_lead_id`` (i.e. project_lead cleared)
        must be a silent no-op rather than crash with a NOT NULL error.
        """
        project = Project.objects.create(
            name="P", identifier="P", workspace=workspace, project_lead=workspace.owner
        )
        ensure_project_lead_membership(project.id, None, workspace.id)
        # No rows created.
        assert ProjectMember.objects.filter(project=project).count() == 0