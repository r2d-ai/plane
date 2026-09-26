# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression: dashboard serializer must not leak inaccessible project ids (§28.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory

from plane.app.serializers.dashboard import DashboardSerializer
from plane.db.models import (
    Dashboard,
    DashboardProject,
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
