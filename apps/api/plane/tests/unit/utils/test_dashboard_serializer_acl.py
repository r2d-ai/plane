# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression: dashboard serializer must not leak inaccessible project ids (§28.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory

from plane.app.serializers.dashboard import DashboardSerializer, DashboardWidgetSerializer
from plane.db.models import (
    Dashboard,
    DashboardProject,
    DashboardWidget,
    Project,
    ProjectMember,
    ProjectNetwork,
    User,
    Workspace,
    WorkspaceMember,
)


pytestmark = pytest.mark.unit


def _user(email: str) -> User:
    user = User.objects.create(email=email, username=email.split("@")[0])
    user.set_password("pw")
    user.save()
    return user


@pytest.mark.django_db
def test_serializer_projects_filtered_for_viewer(db):
    owner = _user("owner-serializer-acl@plane.so")
    viewer = _user("viewer-serializer-acl@plane.so")
    workspace = Workspace.objects.create(
        name="ACL", slug=f"acl-{uuid4().hex[:6]}", owner=owner, timezone="UTC"
    )
    public = Project.objects.create(
        workspace=workspace,
        name="A",
        identifier="ACLPA",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    secret = Project.objects.create(
        workspace=workspace,
        name="B-secret",
        identifier="ACLPS",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15, is_active=True)
    ProjectMember.objects.create(project=public, member=viewer, role=20, is_active=True)

    dashboard = Dashboard.objects.create(
        workspace=workspace,
        owner=owner,
        name="Leak test",
        visibility=Dashboard.VISIBILITY_WORKSPACE,
        filters={"project_id": [str(public.id), str(secret.id)]},
        pql=f"project_id = '{secret.id}'",
    )
    DashboardProject.objects.create(dashboard=dashboard, project_id=public.id)
    DashboardProject.objects.create(dashboard=dashboard, project_id=secret.id)

    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = viewer

    data = DashboardSerializer(dashboard, context={"request": request}).data
    assert str(secret.id) not in str(data)
    assert str(public.id) in data["projects"]
    assert str(secret.id) not in data["projects"]
    assert data["pql"] is None
    assert str(secret.id) not in str(data["filters"])


@pytest.mark.django_db
def test_serializer_nested_query_config_redacts_inaccessible_projects(db):
    owner = _user("owner-nested-acl@plane.so")
    viewer = _user("viewer-nested-acl@plane.so")
    workspace = Workspace.objects.create(
        name="Nested ACL", slug=f"nested-acl-{uuid4().hex[:6]}", owner=owner, timezone="UTC"
    )
    public = Project.objects.create(
        workspace=workspace,
        name="A",
        identifier="NACLPA",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    secret = Project.objects.create(
        workspace=workspace,
        name="B-secret",
        identifier="NACLPS",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15, is_active=True)
    ProjectMember.objects.create(project=public, member=viewer, role=20, is_active=True)

    dashboard = Dashboard.objects.create(
        workspace=workspace,
        owner=owner,
        name="Nested leak test",
        visibility=Dashboard.VISIBILITY_WORKSPACE,
    )
    DashboardProject.objects.create(dashboard=dashboard, project_id=public.id)
    DashboardProject.objects.create(dashboard=dashboard, project_id=secret.id)
    DashboardWidget.objects.create(
        dashboard=dashboard,
        title="Nested widget",
        widget_type="number",
        query_config={
            "schema_version": 1,
            "query": {
                "metrics": [{"key": "work_item_count"}],
                "project_ids": [str(public.id), str(secret.id)],
                "filters": {"project_id": [str(public.id), str(secret.id)]},
                "pql": f"project_id = '{secret.id}'",
                "time": {"preset": "none"},
            },
        },
    )

    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = viewer

    data = DashboardSerializer(dashboard, context={"request": request}).data
    widget = data["widgets"][0]
    nested = widget["query_config"]["query"]
    assert str(secret.id) not in str(widget["query_config"])
    assert str(secret.id) not in nested.get("project_ids", [])
    assert str(secret.id) not in str(nested.get("filters", {}))
    assert nested.get("pql") is None


@pytest.mark.django_db
def test_widget_serializer_redacts_query_config_with_request_context(db):
    owner = _user("owner-widget-serializer@plane.so")
    viewer = _user("viewer-widget-serializer@plane.so")
    workspace = Workspace.objects.create(
        name="Widget ACL",
        slug=f"widget-acl-{uuid4().hex[:6]}",
        owner=owner,
        timezone="UTC",
    )
    public = Project.objects.create(
        workspace=workspace,
        name="A",
        identifier="WACLPA",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    secret = Project.objects.create(
        workspace=workspace,
        name="B-secret",
        identifier="WACLPS",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15, is_active=True)
    ProjectMember.objects.create(project=public, member=viewer, role=20, is_active=True)

    dashboard = Dashboard.objects.create(
        workspace=workspace,
        owner=owner,
        name="Widget serializer ACL",
        visibility=Dashboard.VISIBILITY_WORKSPACE,
    )
    DashboardProject.objects.create(dashboard=dashboard, project_id=public.id)
    DashboardProject.objects.create(dashboard=dashboard, project_id=secret.id)
    widget = DashboardWidget.objects.create(
        dashboard=dashboard,
        title="Leak widget",
        widget_type="number",
        query_config={
            "schema_version": 1,
            "version": 1,
            "metrics": [{"key": "work_item_count"}],
            "filters": {"project_id": [str(public.id), str(secret.id)]},
            "pql": f"project_id = '{secret.id}'",
            "time": {"preset": "none"},
        },
    )

    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = viewer

    data = DashboardWidgetSerializer(widget, context={"request": request}).data
    assert str(secret.id) not in str(data["query_config"])
    assert data["query_config"].get("pql") is None
