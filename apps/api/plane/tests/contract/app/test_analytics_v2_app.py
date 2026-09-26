# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Analytics V2 API contract tests (spec §49.2, §49.3).

Covers:

* /api/workspaces/{slug}/analytics/v2/query/  — execute a query
* /api/workspaces/{slug}/analytics/v2/stats/  — totals only
* /api/workspaces/{slug}/analytics/v2/charts/ — chart shape
* /api/workspaces/{slug}/analytics/v2/drilldown/ — drill-down
* /api/workspaces/{slug}/analytics/v2/batch/  — batched widget data
* §40.1 caps enforcement
* §49.3 ACL cross-project scenario
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
import pytz
from freezegun import freeze_time
from rest_framework.test import APIClient

from plane.analytics.v2.query import MAX_BATCH_QUERIES
from plane.tests.fixtures.v3_dashboard_batch import (
    V3_DASHBOARD_CARD_COUNT,
    V3_MAX_DRILLDOWN_REFETCHES_UNDER_CAP,
    build_v3_card_query,
    build_v3_dashboard_batch_payload,
    v3_batch_response_contract_keys,
    warm_app_urlconf_for_freezegun,
)
from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueLabel,
    Label,
    Project,
    ProjectMember,
    ProjectNetwork,
    State,
    User,
    Workspace,
    WorkspaceMember,
)


pytestmark = pytest.mark.contract


# ----- URL helpers --------------------------------------------------------


def _query_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/query/"


def _stats_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/stats/"


def _charts_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/charts/"


def _drilldown_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/drilldown/"


def _batch_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/batch/"


# ----- Test fixtures ------------------------------------------------------


def _make_user(email: str) -> User:
    return User.objects.create(email=email, username=email.split("@")[0])


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_state(project: Project, group: str) -> State:
    return State.objects.create(project=project, name="Backlog", color="#000000", group=group)


@pytest.fixture
def acme():
    owner = _make_user("owner@plane.so")
    owner.set_password("pw")
    owner.save()
    workspace = Workspace.objects.create(name="ACME", slug="acme", owner=owner, timezone="UTC")

    proj_public = Project.objects.create(
        workspace=workspace,
        name="Public",
        identifier="PUB",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    proj_secret = Project.objects.create(
        workspace=workspace,
        name="Secret",
        identifier="SEC",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.SECRET.value,
    )
    states = {p.id: _make_state(p, "started") for p in (proj_public, proj_secret)}

    x = _make_user("x@plane.so")
    y = _make_user("y@plane.so")
    x.set_password("pw"); x.save()
    y.set_password("pw"); y.save()

    WorkspaceMember.objects.create(workspace=workspace, member=x, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=y, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_public, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_secret, member=x, role=20, is_active=True)
    ProjectMember.objects.create(project=proj_public, member=y, role=20, is_active=True)
    # Y only has access to the public project.

    # Two issues in each project so the totals are non-zero.
    for proj in (proj_public, proj_secret):
        for i in range(2):
            Issue.objects.create(
                project=proj,
                workspace=workspace,
                name=f"{proj.identifier}-{i}",
                state=states[proj.id],
                priority="medium",
                created_by=x,
            )

    return {
        "workspace": workspace,
        "proj_public": proj_public,
        "proj_secret": proj_secret,
        "x": x,
        "y": y,
    }


# ----- /query -------------------------------------------------------------


@pytest.mark.django_db
class TestV2QueryEndpoint:
    def test_query_returns_acl_filtered_totals(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _query_url(acme["workspace"].slug),
            {
                "version": 1,
                "source": "work_items",
                "metrics": [{"key": "work_item_count"}],
                "dimensions": [{"key": "project"}],
                "time": {"preset": "none"},
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        body = response.data
        # X sees both projects; 2 issues per project → 4 work items.
        assert body["totals"]["work_item_count"] == 4.0
        groups = {str(row["group"]) for row in body["data"]}
        assert str(acme["proj_public"].id) in groups
        assert str(acme["proj_secret"].id) in groups

    def test_y_only_sees_public_project(self, acme):
        client = _client_for(acme["y"])
        response = client.post(
            _query_url(acme["workspace"].slug),
            {
                "version": 1,
                "source": "work_items",
                "metrics": [{"key": "work_item_count"}],
                "dimensions": [{"key": "project"}],
                "time": {"preset": "none"},
            },
            format="json",
        )
        assert response.status_code == 200
        body = response.data
        assert body["totals"]["work_item_count"] == 2.0
        groups = {str(row["group"]) for row in body["data"]}
        assert str(acme["proj_public"].id) in groups
        # The secret project must not appear anywhere in the response payload.
        serialised = str(body)
        assert str(acme["proj_secret"].id) not in serialised
        assert acme["proj_secret"].name not in serialised

    def test_invalid_query_returns_400(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _query_url(acme["workspace"].slug),
            {"version": 1, "metrics": [{"key": "bogus"}]},
            format="json",
        )
        assert response.status_code == 400

    def test_caps_enforced_with_400(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _query_url(acme["workspace"].slug),
            {
                "version": 1,
                "metrics": [{"key": "work_item_count"}],
                "dimensions": [],
                "limit": 10000,  # exceeds MAX_ROWS=100
            },
            format="json",
        )
        assert response.status_code == 400


# ----- /stats -------------------------------------------------------------


@pytest.mark.django_db
class TestV2StatsEndpoint:
    def test_stats_returns_totals_only(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _stats_url(acme["workspace"].slug),
            {
                "version": 1,
                "metrics": [{"key": "work_item_count"}],
                "dimensions": [{"key": "project"}],
                "time": {"preset": "none"},
            },
            format="json",
        )
        assert response.status_code == 200
        assert "totals" in response.data
        assert "data" not in response.data


# ----- /charts ------------------------------------------------------------


@pytest.mark.django_db
class TestV2ChartsEndpoint:
    def test_charts_returns_labels_and_series(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _charts_url(acme["workspace"].slug),
            {
                "version": 1,
                "metrics": [{"key": "work_item_count"}],
                "dimensions": [{"key": "project"}],
                "time": {"preset": "none"},
            },
            format="json",
        )
        assert response.status_code == 200
        body = response.data
        assert "labels" in body
        assert "series" in body
        assert body["series"][0]["metric"] == "work_item_count"


# ----- /drilldown ---------------------------------------------------------


@pytest.mark.django_db
class TestV2DrilldownEndpoint:
    def test_drilldown_returns_matching_work_items(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _drilldown_url(acme["workspace"].slug),
            {
                "query": {
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "time": {"preset": "none"},
                },
                "selection": {"project": [str(acme["proj_public"].id)]},
                "page_size": 10,
            },
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["total"] == 2
        assert len(response.data["rows"]) == 2
        assert {row["project_id"] for row in response.data["rows"]} == {str(acme["proj_public"].id)}

    def test_drilldown_includes_contributions(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _drilldown_url(acme["workspace"].slug),
            {
                "query": {
                    "version": 1,
                    "metrics": [{"key": "work_item_count"}],
                    "dimensions": [{"key": "project"}],
                    "time": {"preset": "none"},
                },
                "selection": {"project": [str(acme["proj_public"].id)]},
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["contributions"]["work_item_count"] == 2.0


# ----- /batch -------------------------------------------------------------


@pytest.mark.django_db
class TestV2BatchEndpoint:
    def test_batch_returns_per_widget_partial_failure(self, acme):
        client = _client_for(acme["x"])
        response = client.post(
            _batch_url(acme["workspace"].slug),
            {
                "queries": [
                    {
                        "key": "widget-ok",
                        "version": 1,
                        "metrics": [{"key": "work_item_count"}],
                        "dimensions": [{"key": "project"}],
                        "time": {"preset": "none"},
                    },
                    {
                        "key": "widget-broken",
                        "version": 1,
                        "metrics": [{"key": "unknown_metric"}],
                        "time": {"preset": "none"},
                    },
                ]
            },
            format="json",
        )
        assert response.status_code == 200
        by_key = {entry["key"]: entry for entry in response.data["results"]}
        assert by_key["widget-ok"]["status"] == "ok"
        assert by_key["widget-broken"]["status"] == "error"

    def test_v3_batch_twelve_cards_with_global_scope_round_trip(self, acme):
        """C.9 — v3 dashboard sends 12 §7 cards with merged global scope filters."""
        client = _client_for(acme["x"])
        payload = build_v3_dashboard_batch_payload(
            project_ids=[str(acme["proj_public"].id)],
        )
        assert len(payload["queries"]) == V3_DASHBOARD_CARD_COUNT
        frozen = datetime(2026, 9, 15, 12, 0, tzinfo=pytz.UTC)
        warm_app_urlconf_for_freezegun()
        with freeze_time(frozen):
            response = client.post(
                _batch_url(acme["workspace"].slug),
                payload,
                format="json",
            )
        assert response.status_code == 200, response.data
        assert response.data["workspace_slug"] == acme["workspace"].slug
        results = response.data["results"]
        assert len(results) == V3_DASHBOARD_CARD_COUNT
        by_key = {entry["key"]: entry for entry in results}
        for card_id in "ABCDEFGHIJKL":
            key = f"card-{card_id}"
            assert key in by_key, key
            assert by_key[key]["status"] == "ok", by_key[key]
            assert "data" in by_key[key]
            assert "totals" in by_key[key]["data"]

    def test_v3_batch_partial_failure_one_malformed_of_twelve(self, acme):
        client = _client_for(acme["x"])
        queries = []
        for card_id in "ABCDEFGHIJKL":
            if card_id == "F":
                queries.append(
                    {
                        "key": "card-F",
                        "version": 1,
                        "source": "work_items",
                        "metrics": [{"key": "unknown_metric"}],
                        "time": {"preset": "none"},
                    }
                )
            else:
                queries.append(build_v3_card_query(card_id))
        assert len(queries) == 12
        response = client.post(
            _batch_url(acme["workspace"].slug),
            {"queries": queries},
            format="json",
        )
        assert response.status_code == 200
        by_key = {entry["key"]: entry for entry in response.data["results"]}
        assert by_key["card-F"]["status"] == "error"
        ok_keys = [k for k, v in by_key.items() if v["status"] == "ok"]
        assert len(ok_keys) == 11

    def test_v3_dashboard_batch_fits_max_batch_queries_cap(self):
        """12 cards + drill-down refetch headroom stays within MAX_BATCH_QUERIES."""
        assert V3_DASHBOARD_CARD_COUNT == 12
        assert V3_MAX_DRILLDOWN_REFETCHES_UNDER_CAP == 8
        assert V3_DASHBOARD_CARD_COUNT + V3_MAX_DRILLDOWN_REFETCHES_UNDER_CAP == MAX_BATCH_QUERIES
        # Document response envelope for batch-composer.ts (stable keys).
        envelope = v3_batch_response_contract_keys()
        assert "results" in envelope
        assert envelope["results"][0]["status"] == "ok"
        assert envelope["results"][1]["status"] == "error"


# ----- Legacy advance-analytics regression -------------------------------


@pytest.mark.django_db
class TestLegacyAdvanceAnalyticsUnaffected:
    """§44.2 — the V2 changes must not affect the legacy ``advance-analytics``
    endpoints.
    """

    def test_legacy_advance_analytics_endpoint_still_runs(self, acme):
        client = _client_for(acme["x"])
        url = f"/api/workspaces/{acme['workspace'].slug}/advance-analytics/?tab=overview&project_ids="
        response = client.get(url)
        # The legacy endpoint returns 200; it may legitimately report any
        # number, but it must not 5xx on a request shaped like the CE baseline.
        assert response.status_code == 200, response.data