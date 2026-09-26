# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dashboard CRUD API contract tests (spec §49.2)."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from plane.analytics.v2.query import MAX_BATCH_QUERIES
from plane.db.models import (
    Dashboard,
    DashboardFavorite,
    DashboardMemberAccess,
    DashboardProject,
    DashboardWidget,
    Issue,
    Project,
    ProjectMember,
    ProjectNetwork,
    State,
    User,
    Workspace,
    WorkspaceMember,
)

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def enable_workspace_dashboards(settings):
    settings.WORKSPACE_DASHBOARDS = True


def _dashboards_url(slug):
    return f"/api/workspaces/{slug}/dashboards/"


def _dashboard_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/"


def _duplicate_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/duplicate/"


def _widgets_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/"


def _widget_url(slug, dashboard_id, widget_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/"


def _data_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/data/"


def _favorite_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/favorite/"


def _export_url(slug, dashboard_id, widget_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/export/"


def _drilldown_url(slug, dashboard_id, widget_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/widgets/{widget_id}/drilldown/"


def _members_url(slug, dashboard_id):
    return f"/api/workspaces/{slug}/dashboards/{dashboard_id}/members/"


def _make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email.split("@")[0])
    user.set_password("pw")
    user.save()
    return user


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _state(project: Project) -> State:
    return State.objects.create(project=project, name="Backlog", color="#000", group="started")


@pytest.fixture
def acme():
    owner = _make_user("owner@plane.so")
    workspace = Workspace.objects.create(name="ACME", slug="acme-dash", owner=owner, timezone="UTC")
    proj_a = Project.objects.create(
        workspace=workspace,
        name="Public",
        identifier="PUB",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    proj_b = Project.objects.create(
        workspace=workspace,
        name="Secret",
        identifier="SEC",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    st = {p.id: _state(p) for p in (proj_a, proj_b)}

    x = _make_user("x@plane.so")
    y = _make_user("y@plane.so")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=x, role=15, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=y, role=15, is_active=True)
    ProjectMember.objects.create(project=proj_a, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_b, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_a, member=y, role=20, is_active=True)

    for proj in (proj_a, proj_b):
        for i in range(2):
            Issue.objects.create(
                project=proj,
                workspace=workspace,
                name=f"{proj.identifier}-{i}",
                state=st[proj.id],
                priority="medium",
                created_by=x,
            )

    return {
        "workspace": workspace,
        "owner": owner,
        "proj_a": proj_a,
        "proj_b": proj_b,
        "x": x,
        "y": y,
    }


class TestDashboardFeatureFlag:
    def test_flag_off_returns_404(self, acme, settings):
        settings.WORKSPACE_DASHBOARDS = False
        client = _client_for(acme["owner"])
        response = client.get(_dashboards_url(acme["workspace"].slug))
        assert response.status_code == 404


class TestDashboardCrud:
    def test_create_list_get_patch_delete(self, acme):
        client = _client_for(acme["owner"])
        slug = acme["workspace"].slug

        created = client.post(
            _dashboards_url(slug),
            {
                "name": "Sprint health",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id), str(acme["proj_b"].id)],
            },
            format="json",
        )
        assert created.status_code == 201
        dashboard_id = created.data["id"]

        listed = client.get(_dashboards_url(slug))
        assert listed.status_code == 200
        assert any(row["id"] == dashboard_id for row in listed.data)

        detail = client.get(_dashboard_url(slug, dashboard_id))
        assert detail.status_code == 200
        assert detail.data["name"] == "Sprint health"

        patched = client.patch(
            _dashboard_url(slug, dashboard_id),
            {"name": "Renamed"},
            format="json",
        )
        assert patched.status_code == 200
        assert patched.data["name"] == "Renamed"

        deleted = client.delete(_dashboard_url(slug, dashboard_id))
        assert deleted.status_code == 204
        assert not Dashboard.objects.filter(id=dashboard_id, deleted_at__isnull=True).exists()

    def test_private_dashboard_hidden_from_other_member(self, acme):
        owner_client = _client_for(acme["owner"])
        other_client = _client_for(acme["y"])
        slug = acme["workspace"].slug

        created = owner_client.post(
            _dashboards_url(slug),
            {"name": "Private board", "visibility": Dashboard.VISIBILITY_PRIVATE},
            format="json",
        )
        dashboard_id = created.data["id"]

        assert other_client.get(_dashboard_url(slug, dashboard_id)).status_code == 404

    def test_workspace_visible_dashboard_readable(self, acme):
        owner_client = _client_for(acme["owner"])
        other_client = _client_for(acme["y"])
        slug = acme["workspace"].slug

        created = owner_client.post(
            _dashboards_url(slug),
            {"name": "Team board", "visibility": Dashboard.VISIBILITY_WORKSPACE},
            format="json",
        )
        assert other_client.get(_dashboard_url(slug, created.data["id"])).status_code == 200


class TestDashboardWidgetsAndData:
    def _dashboard_with_widget(self, acme, client, filters=None):
        slug = acme["workspace"].slug
        dash = client.post(
            _dashboards_url(slug),
            {
                "name": "Data board",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id), str(acme["proj_b"].id)],
                "filters": filters or {},
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        dashboard_id = dash.data["id"]
        widget = client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "Counts",
                "widget_type": "number",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        return slug, dashboard_id, widget.data["id"]

    def test_widget_crud(self, acme):
        client = _client_for(acme["x"])
        slug, dashboard_id, widget_id = self._dashboard_with_widget(acme, client)

        patched = client.patch(
            _widget_url(slug, dashboard_id, widget_id),
            {"title": "Updated"},
            format="json",
        )
        assert patched.status_code == 200
        assert patched.data["title"] == "Updated"

        deleted = client.delete(_widget_url(slug, dashboard_id, widget_id))
        assert deleted.status_code == 204

    def test_batch_data_partial_failure(self, acme):
        client = _client_for(acme["x"])
        slug = acme["workspace"].slug
        dash = client.post(
            _dashboards_url(slug),
            {
                "name": "Batch",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id)],
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        dashboard_id = dash.data["id"]
        client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "OK",
                "widget_type": "number",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "Bad",
                "widget_type": "number",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "not_a_metric"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )

        response = client.post(_data_url(slug, dashboard_id), {}, format="json")
        assert response.status_code == 200
        widgets = response.data["widgets"]
        statuses = {entry["status"] for entry in widgets.values()}
        assert "ok" in statuses
        assert "error" in statuses

    def test_acl_intersection_per_viewer(self, acme):
        x_client = _client_for(acme["x"])
        y_client = _client_for(acme["y"])
        slug, dashboard_id, _widget_id = self._dashboard_with_widget(acme, x_client)

        x_data = x_client.post(_data_url(slug, dashboard_id), {}, format="json")
        y_data = y_client.post(_data_url(slug, dashboard_id), {}, format="json")

        x_total = next(
            w["data"]["totals"]["work_item_count"]
            for w in x_data.data["widgets"].values()
            if w["status"] == "ok"
        )
        y_total = next(
            w["data"]["totals"]["work_item_count"]
            for w in y_data.data["widgets"].values()
            if w["status"] == "ok"
        )
        assert x_total == 4.0
        assert y_total == 2.0
        assert str(acme["proj_b"].id) not in str(y_data.data)

    def test_filter_intersection_narrows_widget(self, acme):
        client = _client_for(acme["x"])
        slug, dashboard_id, widget_id = self._dashboard_with_widget(
            acme,
            client,
            filters={"project_id": [str(acme["proj_a"].id)]},
        )
        response = client.post(_data_url(slug, dashboard_id), {}, format="json")
        widget_payload = response.data["widgets"][str(widget_id)]
        assert widget_payload["status"] == "ok"
        assert widget_payload["data"]["totals"]["work_item_count"] == 2.0


class TestDashboardFavoriteDuplicateSharing:
    def test_favorite_and_duplicate(self, acme):
        client = _client_for(acme["owner"])
        slug = acme["workspace"].slug
        created = client.post(
            _dashboards_url(slug),
            {
                "name": "Original",
                "visibility": Dashboard.VISIBILITY_PRIVATE,
                "project_ids": [str(acme["proj_a"].id)],
            },
            format="json",
        )
        dashboard_id = created.data["id"]
        client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "W1",
                "widget_type": "number",
                "query_config": {"schema_version": 1, "version": 1, "metrics": [{"key": "work_item_count"}]},
            },
            format="json",
        )

        assert client.post(_favorite_url(slug, dashboard_id)).status_code == 204
        detail = client.get(_dashboard_url(slug, dashboard_id))
        assert detail.data["is_favorited"] is True

        dup = client.post(_duplicate_url(slug, dashboard_id))
        assert dup.status_code == 201
        assert str(dup.data["owner"]) == str(acme["owner"].id)
        assert dup.data["visibility"] == Dashboard.VISIBILITY_PRIVATE
        assert DashboardWidget.objects.filter(dashboard_id=dup.data["id"]).count() == 1
        assert not DashboardMemberAccess.objects.filter(dashboard_id=dup.data["id"]).exists()

    def test_sharing_row_grants_view(self, acme):
        owner_client = _client_for(acme["owner"])
        guest_client = _client_for(acme["y"])
        slug = acme["workspace"].slug
        created = owner_client.post(
            _dashboards_url(slug),
            {"name": "Shared", "visibility": Dashboard.VISIBILITY_PRIVATE},
            format="json",
        )
        dashboard_id = created.data["id"]
        assert guest_client.get(_dashboard_url(slug, dashboard_id)).status_code == 404

        owner_client.post(
            _members_url(slug, dashboard_id),
            {"member": str(acme["y"].id), "access": DashboardMemberAccess.ACCESS_VIEW},
            format="json",
        )
        assert guest_client.get(_dashboard_url(slug, dashboard_id)).status_code == 200


class TestDashboardExportAndDrilldown:
    def test_export_csv_matches_acl(self, acme):
        client = _client_for(acme["y"])
        slug = acme["workspace"].slug
        dash = client.post(
            _dashboards_url(slug),
            {
                "name": "Export",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id), str(acme["proj_b"].id)],
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        dashboard_id = dash.data["id"]
        widget = client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "CSV",
                "widget_type": "table",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        export = client.get(_export_url(slug, dashboard_id, widget.data["id"]))
        assert export.status_code == 200
        assert "text/csv" in export["Content-Type"]
        body = export.content.decode()
        assert str(acme["proj_b"].id) not in body

    def test_drilldown_parity_with_aggregate(self, acme):
        client = _client_for(acme["x"])
        slug = acme["workspace"].slug
        dash = client.post(
            _dashboards_url(slug),
            {
                "name": "Drill",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id)],
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        dashboard_id = dash.data["id"]
        widget = client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "D",
                "widget_type": "bar",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        widget_id = widget.data["id"]

        data = client.post(_data_url(slug, dashboard_id), {}, format="json")
        aggregate_total = data.data["widgets"][str(widget_id)]["data"]["totals"]["work_item_count"]

        drill = client.post(
            _drilldown_url(slug, dashboard_id, widget_id),
            {
                "selection": {"project": [str(acme["proj_a"].id)]},
                "page_size": 50,
            },
            format="json",
        )
        assert drill.status_code == 200
        assert drill.data["contributions"]["work_item_count"] == aggregate_total


def _assert_no_project_leak(payload, hidden: Project):
    blob = str(payload)
    assert str(hidden.id) not in blob
    assert hidden.name not in blob
    assert hidden.identifier not in blob


@pytest.fixture
def acl_abc():
    """§49.3: public A; private B (X only); private C (Y only)."""
    owner = _make_user("owner-493@plane.so")
    workspace = Workspace.objects.create(
        name="ACL-493", slug="acl-493", owner=owner, timezone="UTC"
    )
    proj_a = Project.objects.create(
        workspace=workspace,
        name="Project-A",
        identifier="PRA",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    proj_b = Project.objects.create(
        workspace=workspace,
        name="Project-B-secret",
        identifier="PRB",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    proj_c = Project.objects.create(
        workspace=workspace,
        name="Project-C-secret",
        identifier="PRC",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    states = {p.id: _state(p) for p in (proj_a, proj_b, proj_c)}

    x = _make_user("x-493@plane.so")
    y = _make_user("y-493@plane.so")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=x, role=15, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=y, role=15, is_active=True)
    ProjectMember.objects.create(project=proj_a, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_b, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_a, member=y, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_c, member=y, role=20, is_active=True)

    for project in (proj_a, proj_b, proj_c):
        Issue.objects.create(
            project=project,
            workspace=workspace,
            name=f"Issue-{project.identifier}",
            state=states[project.id],
            priority="medium",
            created_by=x,
        )

    return {
        "workspace": workspace,
        "owner": owner,
        "proj_a": proj_a,
        "proj_b": proj_b,
        "proj_c": proj_c,
        "x": x,
        "y": y,
    }


class TestDashboardACLRegression493:
    """Single end-to-end scenario across metadata + data surfaces (spec §49.3)."""

    def _create_shared_dashboard(self, acl_abc, owner_client):
        slug = acl_abc["workspace"].slug
        created = owner_client.post(
            _dashboards_url(slug),
            {
                "name": "ACL regression",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [
                    str(acl_abc["proj_a"].id),
                    str(acl_abc["proj_b"].id),
                    str(acl_abc["proj_c"].id),
                ],
                "filters": {
                    "project_id": [
                        str(acl_abc["proj_a"].id),
                        str(acl_abc["proj_b"].id),
                        str(acl_abc["proj_c"].id),
                    ]
                },
                "pql": f"project_id = '{acl_abc['proj_c'].id}'",
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        assert created.status_code == 201
        dashboard_id = created.data["id"]
        widget = owner_client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "By project",
                "widget_type": "table",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "filters": {
                        "project_id": [
                            str(acl_abc["proj_a"].id),
                            str(acl_abc["proj_b"].id),
                            str(acl_abc["proj_c"].id),
                        ]
                    },
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        assert widget.status_code == 201
        return slug, dashboard_id, widget.data["id"]

    def test_cross_surface_acl_regression(self, acl_abc):
        owner_client = _client_for(acl_abc["owner"])
        x_client = _client_for(acl_abc["x"])
        y_client = _client_for(acl_abc["y"])
        slug, dashboard_id, widget_id = self._create_shared_dashboard(acl_abc, owner_client)

        for client, hidden, expected_total in (
            (x_client, acl_abc["proj_c"], 2.0),
            (y_client, acl_abc["proj_b"], 2.0),
        ):
            listed = client.get(_dashboards_url(slug))
            assert listed.status_code == 200
            row = next(item for item in listed.data if item["id"] == dashboard_id)
            _assert_no_project_leak(row, hidden)
            assert str(hidden.id) not in row["projects"]

            detail = client.get(_dashboard_url(slug, dashboard_id))
            assert detail.status_code == 200
            _assert_no_project_leak(detail.data, hidden)
            assert str(hidden.id) not in str(detail.data["widgets"])

            batch = client.post(_data_url(slug, dashboard_id), {}, format="json")
            assert batch.status_code == 200
            _assert_no_project_leak(batch.data, hidden)
            widget_payload = batch.data["widgets"][str(widget_id)]
            assert widget_payload["status"] == "ok"
            assert widget_payload["data"]["totals"]["work_item_count"] == expected_total
            groups = {str(row.get("group")) for row in widget_payload["data"]["data"]}
            assert str(hidden.id) not in groups

            drill = client.post(
                _drilldown_url(slug, dashboard_id, widget_id),
                {"selection": {"project": [str(acl_abc["proj_a"].id)]}, "page_size": 50},
                format="json",
            )
            assert drill.status_code == 200
            _assert_no_project_leak(drill.data, hidden)

            export = client.get(_export_url(slug, dashboard_id, widget_id))
            assert export.status_code == 200
            _assert_no_project_leak(export.content.decode(), hidden)

        bad = owner_client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "Bad",
                "widget_type": "number",
                "query_config": {
                    "schema_version": 1,
                    "version": 1,
                    "metrics": [{"key": "not_a_real_metric"}],
                    "time": {"preset": "none"},
                },
            },
            format="json",
        )
        assert bad.status_code == 201
        over = x_client.post(_data_url(slug, dashboard_id), {}, format="json")
        assert over.status_code == 200
        err_blob = str(over.data)
        assert str(acl_abc["proj_c"].id) not in err_blob
        assert "not_a_real_metric" not in err_blob

    def test_nested_query_config_acl_list_and_detail(self, acl_abc):
        """Nested query_config.query must not leak hidden project UUIDs (RD-457 / §28.3)."""
        owner_client = _client_for(acl_abc["owner"])
        y_client = _client_for(acl_abc["y"])
        hidden = acl_abc["proj_b"]
        slug = acl_abc["workspace"].slug

        created = owner_client.post(
            _dashboards_url(slug),
            {
                "name": "Nested ACL",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [
                    str(acl_abc["proj_a"].id),
                    str(acl_abc["proj_b"].id),
                    str(acl_abc["proj_c"].id),
                ],
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        assert created.status_code == 201
        dashboard_id = created.data["id"]
        widget = owner_client.post(
            _widgets_url(slug, dashboard_id),
            {
                "title": "Nested query body",
                "widget_type": "number",
                "query_config": {
                    "schema_version": 1,
                    "query": {
                        "version": 1,
                        "metrics": [{"key": "work_item_count"}],
                        "project_ids": [
                            str(acl_abc["proj_a"].id),
                            str(acl_abc["proj_b"].id),
                            str(acl_abc["proj_c"].id),
                        ],
                        "filters": {
                            "project_id": [
                                str(acl_abc["proj_a"].id),
                                str(acl_abc["proj_b"].id),
                                str(acl_abc["proj_c"].id),
                            ]
                        },
                        "pql": f"project_id = '{hidden.id}'",
                        "time": {"preset": "none"},
                    },
                },
            },
            format="json",
        )
        assert widget.status_code == 201

        listed = y_client.get(_dashboards_url(slug))
        assert listed.status_code == 200
        row = next(item for item in listed.data if item["id"] == dashboard_id)
        _assert_no_project_leak(row, hidden)
        list_widget = row["widgets"][0]
        nested = list_widget["query_config"]["query"]
        assert str(hidden.id) not in str(list_widget["query_config"])
        assert str(hidden.id) not in nested.get("project_ids", [])
        assert str(hidden.id) not in str(nested.get("filters", {}))
        assert nested.get("pql") is None

        detail = y_client.get(_dashboard_url(slug, dashboard_id))
        assert detail.status_code == 200
        _assert_no_project_leak(detail.data, hidden)
        detail_widget = detail.data["widgets"][0]
        nested_detail = detail_widget["query_config"]["query"]
        assert str(hidden.id) not in str(detail_widget["query_config"])
        assert str(hidden.id) not in nested_detail.get("project_ids", [])
        assert str(hidden.id) not in str(nested_detail.get("filters", {}))
        assert nested_detail.get("pql") is None


class TestDashboardDataWidgetCap:
    def test_oversized_widget_batch_rejected(self, acme):
        client = _client_for(acme["owner"])
        slug = acme["workspace"].slug
        dash = client.post(
            _dashboards_url(slug),
            {
                "name": "Cap board",
                "visibility": Dashboard.VISIBILITY_WORKSPACE,
                "project_ids": [str(acme["proj_a"].id)],
                "default_time_scope": {"preset": "none"},
            },
            format="json",
        )
        dashboard_id = dash.data["id"]
        for index in range(MAX_BATCH_QUERIES + 1):
            client.post(
                _widgets_url(slug, dashboard_id),
                {
                    "title": f"W{index}",
                    "widget_type": "number",
                    "query_config": {
                        "schema_version": 1,
                        "version": 1,
                        "metrics": [{"key": "work_item_count"}],
                        "time": {"preset": "none"},
                    },
                },
                format="json",
            )

        response = client.post(_data_url(slug, dashboard_id), {}, format="json")
        assert response.status_code == 400
        assert response.data["code"] == "INVALID_QUERY"
        assert str(MAX_BATCH_QUERIES + 1) not in str(response.data)
