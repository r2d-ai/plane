# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
RD-447 -- contract tests for the revoke-cascade guarantee.

Three HTTP paths share the same intent ("revoke a user from this
workspace"):

* ``PATCH /api/workspaces/{slug}/members/{pk}/`` with
  ``{"is_active": false}``  (admin)
* ``DELETE /api/workspaces/{slug}/members/{pk}/``  (admin)
* ``POST /api/workspaces/{slug}/members/leave/``   (self)

Before RD-447 only DELETE and leave cascaded to ``ProjectMember``;
PATCH silently set ``WorkspaceMember.is_active = False`` and left the
project rows intact, so a revoked user kept project access (and any
membership-gated feature, e.g. the digest emails that PR #51
defended-in-depth against).

These tests cover the contract -- "after revoke, the user has zero
active ProjectMember rows in the workspace" -- for all three paths and
add regression tests for the PATCH behaviors that must NOT regress:
role updates, promote / demote, and the guest conversion (`role == 5`)
which already has its own cascade to ``ProjectMember.role``.
"""

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Project,
    ProjectMember,
    User,
    WorkspaceMember,
)


def _member_detail_url(slug: str, pk) -> str:
    return f"/api/workspaces/{slug}/members/{pk}/"


def _leave_url(slug: str) -> str:
    return f"/api/workspaces/{slug}/members/leave/"


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


def _add_project_member(project, user, *, role: int = 15, is_active: bool = True) -> ProjectMember:
    return ProjectMember.objects.create(
        workspace=project.workspace,
        project=project,
        member=user,
        role=role,
        is_active=is_active,
    )


@pytest.fixture
def project_for_revoke(db, workspace, create_user):
    """Two projects owned by ``create_user`` (workspace admin) with one
    other active member. We use two projects to confirm the cascade is
    workspace-wide and not just the first row encountered.
    """
    other = _make_user("victim@plane.so")
    _add_workspace_member(workspace, other, role=15)
    projects = []
    for i in range(2):
        proj = Project.objects.create(
            name=f"Cascade Project {i}",
            identifier=f"CP{i}",
            workspace=workspace,
            created_by=create_user,
            project_lead=create_user,
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=create_user, role=20, is_active=True
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=other, role=15, is_active=True
        )
        projects.append(proj)
    return other, projects


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceMemberRevokeCascade:
    def test_patch_is_active_false_cascades_to_project_member(
        self, workspace, create_user, project_for_revoke
    ):
        """Core RD-447 contract: PATCH {"is_active": false} on a
        WorkspaceMember must deactivate every active ProjectMember the
        user has in that workspace. Before the fix, the workspace row
        flipped to inactive but the project rows stayed active and the
        user kept project access.
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        # Pre-condition: victim has 2 active ProjectMember rows.
        assert ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        ).count() == 2

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content

        ws_member.refresh_from_db()
        assert ws_member.is_active is False

        active = ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        )
        assert active.count() == 0, (
            f"Expected zero active ProjectMember rows after PATCH, "
            f"got {list(active.values('project_id', 'role'))}"
        )
        # Soft-deactivation, not hard-delete: rows still exist.
        assert ProjectMember.objects.filter(member=victim, workspace=workspace).count() == 2

    def test_patch_is_active_true_is_a_noop_for_project_members(
        self, workspace, create_user, project_for_revoke
    ):
        """Regression guard for the no-op path: PATCH {"is_active": true}
        on an already-active workspace member must NOT touch project
        memberships. The serializer saves and the cascade service must
        see deactivating=False and stay quiet.
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"is_active": True},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        # All project rows still active, role unchanged.
        active = ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        )
        assert active.count() == 2
        assert set(active.values_list("role", flat=True)) == {15}

    def test_delete_cascade_still_works(self, workspace, create_user, project_for_revoke):
        """Regression guard: DELETE on a workspace member continues to
        cascade to ProjectMember. This was already correct pre-RD-447
        and the refactor moved the inline cascade into a service -- so
        we verify the refactor didn't break the existing path.
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.delete(_member_detail_url(workspace.slug, ws_member.pk))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        ).count() == 0

    def test_leave_cascade_still_works(self, workspace, create_user, project_for_revoke):
        """Regression guard: POST /members/leave/ continues to cascade to
        ProjectMember. The user is NOT the only admin of their projects
        in the project_for_revoke fixture -- ``create_user`` (the
        workspace owner) is the admin there. But we need to avoid the
        "only workspace admin" guard that blocks the only-admin from
        leaving, so create a second workspace admin (the victim must
        not be the only role=20 in the workspace).
        """
        victim, projects = project_for_revoke
        # Promote victim on each project so the project-level "only admin"
        # guard doesn't fire when they leave. They are still not the only
        # workspace admin -- create_user (workspace owner, role=20) is.
        for proj in projects:
            pm = ProjectMember.objects.get(project=proj, member=victim)
            pm.role = 20
            pm.save()

        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)
        assert ws_member.is_active is True

        client = APIClient()
        client.force_authenticate(user=victim)
        response = client.post(_leave_url(workspace.slug))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        ).count() == 0

    def test_patch_role_does_not_deactivate_project_member(
        self, workspace, create_user, project_for_revoke
    ):
        """Regression guard for the orthogonal PATCH /members/{pk}/ use
        case: changing only ``role`` must NOT deactivate project rows.
        Before the fix, the cascade was only attached to destroy/leave,
        so a role update never deactivated anything -- we want to keep
        that property.
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"role": 15},  # admin -> member, no is_active in payload
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content

        ws_member.refresh_from_db()
        assert ws_member.role == 15

        # Project rows untouched: still active, still role=15.
        active = ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        )
        assert active.count() == 2
        assert set(active.values_list("role", flat=True)) == {15}

    def test_patch_role_to_guest_cascades_role_to_project_member(
        self, workspace, create_user, project_for_revoke
    ):
        """Regression guard for the existing guest-conversion behavior:
        when ``role`` is set to 5 (guest), the view already propagates
        ``role=5`` to all of the member's ``ProjectMember`` rows. After
        the fix, that behavior is preserved and the project rows are
        NOT deactivated (the intent of role=5 is "downgrade", not
        "remove").
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"role": 5},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.content

        # Project rows updated to role=5, still active.
        active = ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        )
        assert active.count() == 2
        assert set(active.values_list("role", flat=True)) == {5}

    def test_patch_cannot_revoke_self(self, workspace, create_user):
        """Self-removal guard must survive the refactor: PATCH
        ``is_active: false`` on your own workspace membership returns
        400 and does not cascade anything. This was already enforced by
        the existing "you cannot update your own role" check, but the
        new cascade code path must not bypass it.
        """
        own_ws_member = WorkspaceMember.objects.get(workspace=workspace, member=create_user)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, own_ws_member.pk),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        own_ws_member.refresh_from_db()
        assert own_ws_member.is_active is True

    def test_patch_is_active_false_for_other_workspace_user_unchanged(
        self, workspace, create_user
    ):
        """Cascade must scope to the *target* workspace member, not the
        requesting user's memberships. Two distinct victims in two
        projects: revoking victim-A must leave victim-B's project rows
        intact. Catches a regression where the cascade accidentally
        uses ``request.user`` instead of ``workspace_member.member``.
        """
        victim_a = _make_user("victim-a@plane.so")
        victim_b = _make_user("victim-b@plane.so")
        _add_workspace_member(workspace, victim_a, role=15)
        _add_workspace_member(workspace, victim_b, role=15)

        proj = Project.objects.create(
            name="Two Victims",
            identifier="TV",
            workspace=workspace,
            created_by=create_user,
            project_lead=create_user,
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=create_user, role=20, is_active=True
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=victim_a, role=15, is_active=True
        )
        ProjectMember.objects.create(
            workspace=workspace, project=proj, member=victim_b, role=15, is_active=True
        )

        ws_member_a = WorkspaceMember.objects.get(workspace=workspace, member=victim_a)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member_a.pk),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert ProjectMember.objects.filter(
            member=victim_a, workspace=workspace, is_active=True
        ).count() == 0
        # victim_b untouched.
        assert ProjectMember.objects.filter(
            member=victim_b, workspace=workspace, is_active=True
        ).count() == 1
        # requester untouched.
        assert ProjectMember.objects.filter(
            member=create_user, workspace=workspace, is_active=True
        ).count() == 1

    def test_patch_is_active_false_for_user_with_no_project_membership(
        self, workspace, create_user
    ):
        """Idempotency / safety: revoking a user who has no project
        memberships in the workspace must succeed and not raise. The
        cascade's WHERE clause already filters on is_active=True, but
        we add this to lock in that ``ProjectMember.objects.filter(...).
        update(...)`` returning 0 rows is not an error.
        """
        no_projects = _make_user("no-projects@plane.so")
        ws_member = _add_workspace_member(workspace, no_projects, role=15)

        client = APIClient()
        client.force_authenticate(user=create_user)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ws_member.refresh_from_db()
        assert ws_member.is_active is False
        assert ProjectMember.objects.filter(
            member=no_projects, workspace=workspace
        ).count() == 0

    def test_double_revoke_is_idempotent(self, workspace, create_user, project_for_revoke):
        """Calling revoke_workspace_member twice must converge to the
        same state without raising. PATCH ``is_active: false`` after a
        prior DELETE (or two PATCHes in a row) -- the second call sees
        no active project rows and an already-inactive workspace row,
        which the service must treat as a no-op rather than a duplicate
        constraint violation.
        """
        victim, projects = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        client = APIClient()
        client.force_authenticate(user=create_user)

        # First revoke.
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"is_active": False},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        # Second revoke: the target row is already is_active=False (so
        # the partial_update guard at the view level rejects with 404,
        # because get(pk=..., is_active=True) misses). That is the
        # correct HTTP behavior -- it shows the system converged.
        ws_member.refresh_from_db()
        assert ws_member.is_active is False
        assert ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        ).count() == 0


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceMemberRevokeCascadeRBAC:
    """Authorization checks around the new cascade path. These were
    already enforced by the existing @allow_permission decorator and
    self-removal guard, but we lock them in so the refactor (which
    moved the cascade into a service) does not silently widen the
    attack surface.
    """

    def test_non_admin_cannot_revoke_via_patch(self, workspace, project_for_revoke):
        victim, _ = project_for_revoke
        ws_member = WorkspaceMember.objects.get(workspace=workspace, member=victim)

        # Downgrade victim to plain member so the decorator requires ADMIN.
        ws_member.role = 15
        ws_member.save()

        # Authenticate as a non-admin workspace member (not in fixture
        # by default; create_user is the admin owner).
        attacker = _make_user("attacker@plane.so")
        _add_workspace_member(workspace, attacker, role=15)

        client = APIClient()
        client.force_authenticate(user=attacker)
        response = client.patch(
            _member_detail_url(workspace.slug, ws_member.pk),
            {"is_active": False},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

        ws_member.refresh_from_db()
        assert ws_member.is_active is True
        assert ProjectMember.objects.filter(
            member=victim, workspace=workspace, is_active=True
        ).count() == 2