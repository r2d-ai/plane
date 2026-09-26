# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""P0 dashboard data model tests (RD-452).

Pins the behaviour the analytics query layer (RD-451) and the dashboards
API layer (RD-453) will rely on:

* private vs workspace visibility (`Dashboard.visibility`);
* member access rows (`DashboardMemberAccess` view/edit);
* favorite uniqueness with soft-delete re-favorite semantics
  (`DashboardFavorite`);
* cascade behaviour when a dashboard or member is hard-deleted.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.db.models import (
    Dashboard,
    DashboardFavorite,
    DashboardMemberAccess,
    DashboardProject,
    DashboardWidget,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)


def _make_user(email: str) -> User:
    user = User(email=email, username=email, first_name=email, last_name="x")
    user.set_password("test-password")
    user.save()
    return user


def _make_workspace(slug: str, owner: User) -> Workspace:
    return Workspace.objects.create(name=slug, slug=slug, owner=owner)


def _make_project(workspace: Workspace, creator: User, identifier: str = "TP") -> Project:
    project = Project.objects.create(
        name=f"Project {identifier}",
        identifier=identifier,
        workspace=workspace,
        created_by=creator,
    )
    ProjectMember.objects.create(project=project, member=creator, role=20, is_active=True)
    return project


def _make_dashboard(workspace: Workspace, owner: User, **overrides) -> Dashboard:
    defaults = {
        "name": "Test dashboard",
        "description": "Test",
        "workspace": workspace,
        "owner": owner,
        "visibility": Dashboard.VISIBILITY_PRIVATE,
    }
    defaults.update(overrides)
    return Dashboard.objects.create(**defaults)


@pytest.mark.django_db(transaction=True)
class TestDashboardVisibility:
    """Spec §27.1 + §28: dashboard visibility rules at the model layer."""

    def test_private_dashboard_owner_can_view_and_edit(self, create_user):
        workspace = _make_workspace("ws-priv", create_user)
        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_PRIVATE,
        )

        assert dashboard.is_private() is True
        assert dashboard.is_workspace_visible() is False
        assert dashboard.can_view(create_user) is True
        assert dashboard.can_edit(create_user) is True
        assert dashboard.can_manage(create_user) is True

    def test_private_dashboard_other_user_cannot_view_by_default(self, create_user):
        workspace = _make_workspace("ws-priv2", create_user)
        other = _make_user("other@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)

        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_PRIVATE,
        )

        assert dashboard.can_view(other) is False
        assert dashboard.can_edit(other) is False
        assert dashboard.can_manage(other) is False

    def test_private_dashboard_explicit_view_grant(self, create_user):
        workspace = _make_workspace("ws-priv3", create_user)
        viewer = _make_user("viewer@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15)

        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_PRIVATE,
        )
        DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member=viewer,
            access=DashboardMemberAccess.ACCESS_VIEW,
        )

        assert dashboard.can_view(viewer) is True
        # A view grant does not confer edit rights.
        assert dashboard.can_edit(viewer) is False

    def test_private_dashboard_explicit_edit_grant(self, create_user):
        workspace = _make_workspace("ws-priv4", create_user)
        editor = _make_user("editor@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=editor, role=15)

        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_PRIVATE,
        )
        DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member=editor,
            access=DashboardMemberAccess.ACCESS_EDIT,
        )

        assert dashboard.can_view(editor) is True
        assert dashboard.can_edit(editor) is True

    def test_workspace_visible_dashboard_readable_by_member(self, create_user):
        workspace = _make_workspace("ws-wv", create_user)
        member = _make_user("member@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)

        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_WORKSPACE,
        )

        assert dashboard.is_workspace_visible() is True
        assert dashboard.is_private() is False
        # Workspace-visible dashboards are readable by any active workspace member.
        assert dashboard.can_view(member) is True
        # Edit requires explicit grant or workspace admin/owner.
        assert dashboard.can_edit(member) is False
        # Manage (delete / change visibility / manage sharing / publish) is
        # owner-only per spec §28.2.
        assert dashboard.can_manage(member) is False

    def test_workspace_admin_can_edit_workspace_visible_dashboard(self, create_user):
        workspace = _make_workspace("ws-wv2", create_user)
        admin = _make_user("admin@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=admin, role=20)

        dashboard = _make_dashboard(
            workspace,
            create_user,
            visibility=Dashboard.VISIBILITY_WORKSPACE,
        )

        assert dashboard.can_view(admin) is True
        assert dashboard.can_edit(admin, workspace_role=20) is True
        # ... but admin still cannot manage (delete / publish / change
        # visibility / manage sharing) — owner-only.
        assert dashboard.can_manage(admin) is False


@pytest.mark.django_db(transaction=True)
class TestDashboardProjectJoin:
    """Spec §27.2: project scope via join table (not JSON)."""

    def test_dashboard_project_join_unique_when_active(self, create_user):
        workspace = _make_workspace("ws-proj", create_user)
        project_a = _make_project(workspace, create_user, "PA")
        project_b = _make_project(workspace, create_user, "PB")

        dashboard = _make_dashboard(workspace, create_user)

        DashboardProject.objects.create(dashboard=dashboard, project=project_a)
        DashboardProject.objects.create(dashboard=dashboard, project=project_b)

        assert DashboardProject.objects.filter(dashboard=dashboard).count() == 2

        # Re-adding the same pair while the original is active must fail.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DashboardProject.objects.create(dashboard=dashboard, project=project_a)

    def test_dashboard_project_allows_re_add_after_soft_delete(self, create_user):
        """Soft-deleted join rows release the active unique constraint so the
        user can re-pick a project after an undo / re-save cycle.
        """
        workspace = _make_workspace("ws-proj2", create_user)
        project = _make_project(workspace, create_user, "PC")

        dashboard = _make_dashboard(workspace, create_user)

        link = DashboardProject.objects.create(dashboard=dashboard, project=project)
        # Soft-delete the existing row.
        link.delete(soft=True)

        # Re-adding the same pair should now succeed.
        DashboardProject.objects.create(dashboard=dashboard, project=project)

        active = DashboardProject.objects.filter(
            dashboard=dashboard, project=project, deleted_at__isnull=True
        )
        assert active.count() == 1

    def test_dashboard_cascade_removes_project_join_rows(self, create_user):
        workspace = _make_workspace("ws-proj3", create_user)
        project = _make_project(workspace, create_user, "PD")
        dashboard = _make_dashboard(workspace, create_user)

        DashboardProject.objects.create(dashboard=dashboard, project=project)
        assert DashboardProject.objects.filter(dashboard=dashboard).count() == 1

        # Hard delete should cascade to the join row.
        dashboard.delete(soft=False)
        assert DashboardProject.objects.filter(dashboard_id=dashboard.id).count() == 0


@pytest.mark.django_db(transaction=True)
class TestDashboardMemberAccess:
    """Spec §27.4: per-dashboard × per-member access rows."""

    def test_member_access_uniqueness(self, create_user):
        workspace = _make_workspace("ws-acc", create_user)
        member = _make_user("acc@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)

        dashboard = _make_dashboard(workspace, create_user)

        DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member=member,
            access=DashboardMemberAccess.ACCESS_VIEW,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DashboardMemberAccess.objects.create(
                    dashboard=dashboard,
                    member=member,
                    access=DashboardMemberAccess.ACCESS_EDIT,
                )

    def test_member_access_cascades_on_member_hard_delete(self, create_user):
        workspace = _make_workspace("ws-acc2", create_user)
        member = _make_user("acc2@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)

        dashboard = _make_dashboard(workspace, create_user)
        DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member=member,
            access=DashboardMemberAccess.ACCESS_VIEW,
        )

        member_id = member.id
        member.delete()

        assert (
            DashboardMemberAccess.objects.filter(member_id=member_id).count() == 0
        )

    def test_member_access_cascades_on_dashboard_hard_delete(self, create_user):
        workspace = _make_workspace("ws-acc3", create_user)
        member = _make_user("acc3@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)

        dashboard = _make_dashboard(workspace, create_user)
        DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member=member,
            access=DashboardMemberAccess.ACCESS_VIEW,
        )

        dashboard_id = dashboard.id
        dashboard.delete(soft=False)

        assert (
            DashboardMemberAccess.objects.filter(dashboard_id=dashboard_id).count()
            == 0
        )


@pytest.mark.django_db(transaction=True)
class TestDashboardFavorite:
    """Spec §27.5: per-user favorite uniqueness with soft-delete semantics."""

    def test_favorite_uniqueness(self, create_user):
        workspace = _make_workspace("ws-fav", create_user)
        dashboard = _make_dashboard(workspace, create_user)

        DashboardFavorite.objects.create(dashboard=dashboard, member=create_user)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DashboardFavorite.objects.create(
                    dashboard=dashboard, member=create_user
                )

    def test_favorite_can_be_recreated_after_soft_delete(self, create_user):
        """Spec §31: a user can re-favorite after unfavoriting; the unique
        constraint must be a partial one that ignores soft-deleted rows.
        """
        workspace = _make_workspace("ws-fav2", create_user)
        dashboard = _make_dashboard(workspace, create_user)

        fav = DashboardFavorite.objects.create(
            dashboard=dashboard, member=create_user
        )
        fav.delete(soft=True)

        # Re-favorite should now succeed.
        DashboardFavorite.objects.create(dashboard=dashboard, member=create_user)

        active = DashboardFavorite.objects.filter(
            dashboard=dashboard, member=create_user, deleted_at__isnull=True
        )
        assert active.count() == 1

    def test_favorite_cascades_on_dashboard_hard_delete(self, create_user):
        workspace = _make_workspace("ws-fav3", create_user)
        dashboard = _make_dashboard(workspace, create_user)
        DashboardFavorite.objects.create(dashboard=dashboard, member=create_user)

        dashboard_id = dashboard.id
        dashboard.delete(soft=False)
        assert (
            DashboardFavorite.objects.filter(dashboard_id=dashboard_id).count() == 0
        )

    def test_favorite_lookup_by_user(self, create_user):
        """§40.3: favorite lookup by user. The `(member, deleted_at)` index
        should back the favorites-panel hydration query."""
        workspace = _make_workspace("ws-fav4", create_user)
        other = _make_user("fav4@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)

        d1 = _make_dashboard(workspace, create_user, name="d1")
        d2 = _make_dashboard(workspace, create_user, name="d2")

        DashboardFavorite.objects.create(dashboard=d1, member=create_user)
        DashboardFavorite.objects.create(dashboard=d2, member=create_user)
        DashboardFavorite.objects.create(dashboard=d1, member=other)

        assert (
            DashboardFavorite.objects.filter(
                member=create_user, deleted_at__isnull=True
            ).count()
            == 2
        )
        assert (
            DashboardFavorite.objects.filter(member=other, deleted_at__isnull=True).count()
            == 1
        )


@pytest.mark.django_db(transaction=True)
class TestDashboardWidget:
    """Spec §27.3: widget configuration storage."""

    def test_widget_query_config_requires_schema_version(self, create_user):
        """Spec §27.3: query_config MUST include a schema version. The model
        layer does not validate it (that belongs to the analytics engine);
        we document the contract by ensuring a missing key surfaces clearly.
        """
        workspace = _make_workspace("ws-w", create_user)
        dashboard = _make_dashboard(workspace, create_user)

        widget = DashboardWidget.objects.create(
            dashboard=dashboard,
            title="No schema version",
            widget_type="bar",
            query_config={"foo": "bar"},
        )
        assert "schema_version" not in widget.query_config

        # Round-trip a valid query_config through save+refresh.
        widget.query_config = {"schema_version": 1, "metric": "count"}
        widget.save()
        widget.refresh_from_db()
        assert widget.query_config["schema_version"] == 1

    def test_widget_cascades_on_dashboard_hard_delete(self, create_user):
        workspace = _make_workspace("ws-w2", create_user)
        dashboard = _make_dashboard(workspace, create_user)
        DashboardWidget.objects.create(
            dashboard=dashboard,
            title="w",
            widget_type="bar",
            query_config={"schema_version": 1},
        )

        dashboard_id = dashboard.id
        dashboard.delete(soft=False)
        assert (
            DashboardWidget.objects.filter(dashboard_id=dashboard_id).count() == 0
        )

    def test_widget_soft_delete_hides_from_default_manager(self, create_user):
        workspace = _make_workspace("ws-w3", create_user)
        dashboard = _make_dashboard(workspace, create_user)
        widget = DashboardWidget.objects.create(
            dashboard=dashboard,
            title="w",
            widget_type="bar",
            query_config={"schema_version": 1},
        )

        widget.delete(soft=True)
        # Soft-delete uses the standard `objects` manager so default
        # `objects.filter(...)` queries skip tombstones.
        assert (
            DashboardWidget.objects.filter(id=widget.id).count() == 0
        )
        assert (
            DashboardWidget.all_objects.filter(id=widget.id).count() == 1
        )