# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
RD-447 (project_lead half) -- contract tests for the
``PATCH /api/v1/workspaces/{slug}/projects/{pk}/`` path with
``project_lead=X``.

Pre-fix behavior: setting ``project_lead`` updated the FK column but
did NOT create a ``ProjectMember`` row for the new lead. The new lead
had ``project.project_lead == self`` but every membership gate
(Leader Morning Pulse digest, project archive, ...) saw them as not a
member and stripped their access.

Post-fix behavior: PATCH that transitions ``project_lead`` to a new
user guarantees that user has an active ``ProjectMember`` row at
role=20 inside the same transaction. The reverse direction (current
lead becomes a non-lead) does NOT remove their membership -- their
project access is preserved, only their "lead" status changes.
"""

from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Project, ProjectMember, User, WorkspaceMember


def _project_url(workspace_slug: str, project_id) -> str:
    return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/"


def _make_user(email: str) -> User:
    local_part = email.split("@")[0]
    user = User.objects.create(email=email, username=local_part, first_name=local_part)
    user.set_password("test-password")
    user.save()
    return user


def _add_workspace_member(workspace, user, *, role: int = 15) -> WorkspaceMember:
    return WorkspaceMember.objects.create(
        workspace=workspace, member=user, role=role, is_active=True
    )


def _make_project(workspace, *, name: str, identifier: str, lead: User, created_by: User) -> Project:
    proj = Project.objects.create(
        name=name,
        identifier=identifier,
        workspace=workspace,
        created_by=created_by,
        project_lead=lead,
    )
    # The POST /projects/ endpoint creates these -- mirrors that here so
    # the fixture matches what the API would have created on its own.
    ProjectMember.objects.create(
        workspace=workspace, project=proj, member=lead, role=20, is_active=True
    )
    return proj


@pytest.fixture
def outsider_user(db):
    """User that is NOT a member of any workspace under test.

    Mirrors the fixture in test_projects.py -- duplicated here so this
    test file stays self-contained (the api/ contract test directory
    has no conftest.py that would re-export it).
    """
    unique_id = uuid4().hex[:8]
    user = User.objects.create(
        email=f"outsider-{unique_id}@plane.so",
        username=f"outsider_{unique_id}",
    )
    user.set_password("test-password")
    user.save()
    return user


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectLeadMembershipOnPatch:
    def test_patch_project_lead_creates_membership(self, api_key_client, workspace, create_user):
        """Core RD-447 contract: PATCH project_lead to a user that has
        NO ProjectMember row for the project creates one at role=20.
        Without the fix, the lead had ``project_lead == self`` but no
        ``ProjectMember`` and every membership gate stripped them.
        """
        # Creator (workspace admin) is the initial lead.
        project = _make_project(
            workspace,
            name="Lead Switch",
            identifier="LS",
            lead=create_user,
            created_by=create_user,
        )
        new_lead = _make_user("new-lead@plane.so")
        _add_workspace_member(workspace, new_lead, role=15)
        # Sanity: new_lead has NO ProjectMember row yet.
        assert not ProjectMember.objects.filter(project=project, member=new_lead).exists()

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(new_lead.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content

        project.refresh_from_db()
        assert project.project_lead_id == new_lead.id

        pm = ProjectMember.objects.get(project=project, member=new_lead)
        assert pm.is_active is True
        assert pm.role == 20, "Lead must be a project admin (role=20)."

    def test_patch_project_lead_reactivates_inactive_membership(
        self, api_key_client, workspace, create_user
    ):
        """Re-promoting a previously-revoked member reactivates their
        ProjectMember at role=20. This covers the case where a member
        had their project membership deactivated (RD-447 cascade) and
        is later re-promoted to lead -- the row exists but is_active=False.
        """
        project = _make_project(
            workspace,
            name="Reactivate Lead",
            identifier="RL",
            lead=create_user,
            created_by=create_user,
        )
        previously_revoked = _make_user("revoked@plane.so")
        _add_workspace_member(workspace, previously_revoked, role=15)
        # Add an inactive ProjectMember (simulates the RD-447 cascade).
        ProjectMember.objects.create(
            workspace=workspace,
            project=project,
            member=previously_revoked,
            role=15,
            is_active=False,
        )

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(previously_revoked.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        pm = ProjectMember.objects.get(project=project, member=previously_revoked)
        assert pm.is_active is True
        assert pm.role == 20

    def test_patch_project_lead_promotes_guest_to_admin(
        self, api_key_client, workspace, create_user
    ):
        """Promoting a current guest (role=5) to lead bumps their
        ProjectMember to role=20. Catches a regression where the
        service only checks ``is_active`` and forgets the role bump.
        """
        project = _make_project(
            workspace,
            name="Guest Promotion",
            identifier="GP",
            lead=create_user,
            created_by=create_user,
        )
        former_guest = _make_user("guest@plane.so")
        _add_workspace_member(workspace, former_guest, role=5)
        ProjectMember.objects.create(
            workspace=workspace,
            project=project,
            member=former_guest,
            role=5,  # GUEST
            is_active=True,
        )

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(former_guest.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        pm = ProjectMember.objects.get(project=project, member=former_guest)
        assert pm.role == 20

    def test_patch_project_lead_no_op_does_not_bump_updated_at(
        self, api_key_client, workspace, create_user
    ):
        """Submitting the same project_lead value twice must NOT touch
        the existing ProjectMember row's updated_at. The view detects
        ``new_lead_id == previous_lead_id`` and skips the service call,
        so the cascade service is not triggered on a no-op PATCH.
        """
        project = _make_project(
            workspace,
            name="No-op Patch",
            identifier="NP",
            lead=create_user,
            created_by=create_user,
        )
        # create_user is the lead AND a ProjectMember(role=20). The
        # membership row already exists from _make_project().
        pm = ProjectMember.objects.get(project=project, member=create_user)
        original_updated_at = pm.updated_at

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(create_user.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        pm.refresh_from_db()
        assert pm.updated_at == original_updated_at, (
            "No-op PATCH on project_lead must not mutate the existing "
            "ProjectMember row."
        )

    def test_patch_unrelated_fields_does_not_touch_membership(
        self, api_key_client, workspace, create_user
    ):
        """Regression guard: PATCH with only non-lead fields (name,
        description, cycle_view, etc.) must NOT call the
        ensure_project_lead_membership service. The view detects
        ``project_lead`` was not in the payload and skips the branch.
        """
        project = _make_project(
            workspace,
            name="Unrelated Update",
            identifier="UU",
            lead=create_user,
            created_by=create_user,
        )
        bystander = _make_user("bystander@plane.so")
        _add_workspace_member(workspace, bystander, role=15)
        ProjectMember.objects.create(
            workspace=workspace,
            project=project,
            member=bystander,
            role=15,
            is_active=False,
        )
        original_updated_at = ProjectMember.objects.get(
            project=project, member=bystander
        ).updated_at

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"name": "Renamed Project", "description": "Updated description"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        project.refresh_from_db()
        assert project.name == "Renamed Project"

        bystander_pm = ProjectMember.objects.get(project=project, member=bystander)
        # updated_at unchanged -> the service was not called for bystander.
        assert bystander_pm.updated_at == original_updated_at
        # And bystander's existing inactive row stayed inactive.
        assert bystander_pm.is_active is False

    def test_patch_project_lead_preserves_other_members(
        self, api_key_client, workspace, create_user
    ):
        """Switching the lead must NOT deactivate / delete other
        ProjectMember rows. Catches a regression where the service
        accidentally touches more than the new lead.
        """
        project = _make_project(
            workspace,
            name="Multi Member",
            identifier="MM",
            lead=create_user,
            created_by=create_user,
        )
        # Add 3 other active members.
        other_members = []
        for i in range(3):
            u = _make_user(f"other-{i}@plane.so")
            _add_workspace_member(workspace, u, role=15)
            ProjectMember.objects.create(
                workspace=workspace, project=project, member=u, role=15, is_active=True
            )
            other_members.append(u)

        new_lead = _make_user("fresh-lead@plane.so")
        _add_workspace_member(workspace, new_lead, role=15)

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(new_lead.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content

        # All three other members still active.
        for u in other_members:
            pm = ProjectMember.objects.get(project=project, member=u)
            assert pm.is_active is True
            assert pm.role == 15, f"Other member role must be unchanged, got {pm.role}"
        # create_user, the previous lead, still active (we do NOT remove
        # the previous lead's membership on a lead switch -- only their
        # "lead" status changes).
        prev_lead_pm = ProjectMember.objects.get(project=project, member=create_user)
        assert prev_lead_pm.is_active is True
        assert prev_lead_pm.role == 20
        # New lead now has active membership at role=20.
        new_lead_pm = ProjectMember.objects.get(project=project, member=new_lead)
        assert new_lead_pm.is_active is True
        assert new_lead_pm.role == 20

    def test_patch_project_lead_to_outsider_is_rejected(
        self, api_key_client, workspace, create_user, outsider_user
    ):
        """Setting project_lead to a user that is NOT a workspace
        member must still be rejected by ProjectCreateSerializer.validate
        -- the membership_lifecycle service is only invoked AFTER the
        serializer validates. So no half-baked lead gets persisted.
        """
        project = _make_project(
            workspace,
            name="Outsider Lead",
            identifier="OL",
            lead=create_user,
            created_by=create_user,
        )

        response = api_key_client.patch(
            _project_url(workspace.slug, project.id),
            {"project_lead": str(outsider_user.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "project_lead" in response.data

        project.refresh_from_db()
        assert project.project_lead_id == create_user.id
        # Outsider must not have a ProjectMember row.
        assert not ProjectMember.objects.filter(
            project=project, member=outsider_user
        ).exists()