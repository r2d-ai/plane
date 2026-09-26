# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression tests for §40.1 work caps (RD-466)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2 import metrics as metrics_module
from plane.analytics.v2.acl import base_issue_queryset
from plane.analytics.v2.query import MAX_BATCH_QUERIES, WARNING_RESULT_TRUNCATED
from plane.db.models import (
    Issue,
    Project,
    ProjectMember,
    ProjectNetwork,
    State,
    User,
    Workspace,
    WorkspaceMember,
)


pytestmark = pytest.mark.unit


def _make_workspace(slug: str | None = None) -> Workspace:
    slug = slug or f"ws-{uuid4().hex[:8]}"
    owner = User.objects.create(
        email=f"owner-{slug}@plane.so",
        username=f"owner-{slug}",
    )
    owner.set_password("pw")
    owner.save()
    return Workspace.objects.create(name="WS", slug=slug, owner=owner, timezone="UTC")


def _member(user: User, workspace: Workspace) -> None:
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20, is_active=True)


def _project(workspace: Workspace, user: User, name: str) -> Project:
    project = Project.objects.create(
        workspace=workspace,
        name=name,
        identifier=name[:4].upper(),
        created_by=user,
        updated_by=user,
        network=ProjectNetwork.PUBLIC.value,
    )
    ProjectMember.objects.create(project=project, member=user, role=20, is_active=True)
    return project


@pytest.mark.django_db
class TestDimensionBucketWorkCap:
    def test_limit_one_caps_metric_aggregates_despite_many_groups(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        for index in range(25):
            project = _project(workspace, user, name=f"P{index}")
            state = State.objects.create(
                project=project,
                name="Backlog",
                color="#000000",
                group="backlog",
            )
            Issue.objects.create(
                project=project,
                workspace=workspace,
                name=f"issue-{index}",
                state=state,
                priority="medium",
                created_by=user,
            )

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "project"}],
            limit=1,
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)

        aggregate_calls = 0
        original = metrics_module.aggregate

        def counting_aggregate(*args, **kwargs):
            nonlocal aggregate_calls
            aggregate_calls += 1
            return original(*args, **kwargs)

        with patch.object(metrics_module, "aggregate", side_effect=counting_aggregate):
            response = engine.execute(query)

        assert len(response.data) <= 1
        assert aggregate_calls <= 1

    def test_truncation_warning_when_groups_exceed_work_cap(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        for index in range(25):
            project = _project(workspace, user, name=f"Q{index}")
            state = State.objects.create(
                project=project,
                name="Backlog",
                color="#000000",
                group="backlog",
            )
            Issue.objects.create(
                project=project,
                workspace=workspace,
                name=f"wi-{index}",
                state=state,
                priority="medium",
                created_by=user,
            )

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "project"}],
            limit=5,
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)
        response = engine.execute(query)

        codes = {w["code"] for w in response.warnings}
        assert WARNING_RESULT_TRUNCATED in codes


@pytest.mark.django_db
class TestBatchScopeReuse:
    def test_engine_reuses_acl_queryset_within_batch(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        project = _project(workspace, user, name="Only")
        state = State.objects.create(
            project=project,
            name="Backlog",
            color="#000000",
            group="backlog",
        )
        Issue.objects.create(
            project=project,
            workspace=workspace,
            name="one",
            state=state,
            priority="medium",
            created_by=user,
        )

        payload = {
            "version": 1,
            "metrics": [{"key": "work_item_count"}],
            "dimensions": [{"key": "project"}],
            "time": {"preset": "none"},
        }
        query = AnalyticsQueryV2.from_payload(payload)
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)

        with patch(
            "plane.analytics.v2.query.base_issue_queryset",
            wraps=base_issue_queryset,
        ) as acl_mock:
            for _ in range(5):
                engine.execute(query)

        assert acl_mock.call_count == 1


@pytest.mark.django_db
class TestBatchEndpointCap:
    def test_oversized_batch_rejected(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        client = APIClient()
        client.force_authenticate(user=user)

        entry = {
            "version": 1,
            "metrics": [{"key": "work_item_count"}],
            "time": {"preset": "none"},
        }
        response = client.post(
            f"/api/workspaces/{workspace.slug}/analytics/v2/batch/",
            {"queries": [entry] * (MAX_BATCH_QUERIES + 1)},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["code"] == "INVALID_QUERY"
