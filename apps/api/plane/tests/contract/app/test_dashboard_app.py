# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Legacy workspace dashboard builder API removal (RD-484 / spec §16.6).

Builder CRUD routes under ``/api/workspaces/<slug>/dashboards/`` are removed.
Clients receive 404 — there is no registered handler. Analytics V2 lives under
``/api/workspaces/<slug>/analytics/v2/`` (see ``test_analytics_v2`` contracts).
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import User, Workspace, WorkspaceMember

pytestmark = [pytest.mark.contract, pytest.mark.django_db]

_LEGACY_BUILDER_PATHS = (
    "/api/workspaces/{slug}/dashboards/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/duplicate/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/layout/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/favorite/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/data/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/drilldown/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/export/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/members/",
    "/api/workspaces/{slug}/dashboards/{dashboard_id}/members/{member_id}/",
)


def _make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email.split("@")[0])
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def workspace_client():
    owner = _make_user("owner@plane.so")
    workspace = Workspace.objects.create(
        name="Acme",
        slug="acme",
        owner=owner,
        created_by=owner,
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20)
    client = APIClient()
    client.force_authenticate(user=owner)
    return {"slug": workspace.slug, "client": client}


@pytest.mark.parametrize("path_template", _LEGACY_BUILDER_PATHS)
def test_legacy_builder_routes_are_not_registered(workspace_client, path_template):
    slug = workspace_client["slug"]
    client = workspace_client["client"]
    dashboard_id = uuid.uuid4()
    widget_id = uuid.uuid4()
    member_id = uuid.uuid4()
    path = path_template.format(
        slug=slug,
        dashboard_id=dashboard_id,
        widget_id=widget_id,
        member_id=member_id,
    )
    response = client.get(path)
    assert response.status_code == 404
