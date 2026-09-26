# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Regression tests for §40.1 work caps (RD-466)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2 import metrics as metrics_module
from plane.analytics.v2.acl import base_issue_queryset
from plane.analytics.v2.query import (
    AGGREGATE_WORK_BUDGET,
    MAX_BATCH_QUERIES,
    WARNING_RESULT_TRUNCATED,
)
from plane.db.models import (
    Issue,
    IssueAssignee,
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
    def test_limit_one_still_returns_highest_metric_group(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)

        project_heavy = _project(workspace, user, name="Heavy")
        state_heavy = State.objects.create(
            project=project_heavy,
            name="Backlog",
            color="#000000",
            group="backlog",
        )
        for index in range(5):
            Issue.objects.create(
                project=project_heavy,
                workspace=workspace,
                name=f"heavy-{index}",
                state=state_heavy,
                priority="medium",
                created_by=user,
            )

        project_light = _project(workspace, user, name="Light")
        state_light = State.objects.create(
            project=project_light,
            name="Backlog",
            color="#000000",
            group="backlog",
        )
        Issue.objects.create(
            project=project_light,
            workspace=workspace,
            name="light-newest",
            state=state_light,
            priority="medium",
            created_by=user,
            created_at=timezone.now(),
        )

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "project"}],
            limit=1,
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)
        response = engine.execute(query)

        assert len(response.data) == 1
        assert str(response.data[0]["group"]) == str(project_heavy.id)
        assert response.data[0]["value"] == 5.0

    def test_aggregate_work_bounded_for_many_one_dimension_groups(self):
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
            engine.execute(query)

        assert aggregate_calls <= AGGREGATE_WORK_BUDGET

    def test_truncation_warning_when_groups_exceed_work_cap(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        for index in range(125):
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
        assert len(response.data) <= 5

    def test_two_dimension_aggregate_calls_within_budget(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        project = _project(workspace, user, name="Matrix")
        state = State.objects.create(
            project=project,
            name="Backlog",
            color="#000000",
            group="backlog",
        )
        assignees = []
        for idx in range(6):
            assignee = User.objects.create(email=f"a{idx}@plane.so", username=f"assignee-{idx}")
            assignee.set_password("pw")
            assignee.save()
            _member(assignee, workspace)
            ProjectMember.objects.create(project=project, member=assignee, role=20, is_active=True)
            assignees.append(assignee)

        priorities = ["medium", "high", "low", "urgent", "none", "critical"]
        for index, priority in enumerate(priorities):
            issue = Issue.objects.create(
                project=project,
                workspace=workspace,
                name=f"m-{index}",
                state=state,
                priority=priority,
                created_by=user,
            )
            IssueAssignee.objects.create(
                project=project,
                workspace=workspace,
                issue=issue,
                assignee=assignees[index],
            )

        metric_keys = [{"key": "work_item_count"}] * 20
        query = AnalyticsQueryV2(
            metrics=metric_keys,
            dimensions=[{"key": "priority"}, {"key": "assignees"}],
            limit=10,
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

        assert aggregate_calls <= AGGREGATE_WORK_BUDGET
        assert WARNING_RESULT_TRUNCATED in {w["code"] for w in response.warnings}


@pytest.mark.django_db
class TestBatchScopeReuse:
    def test_engine_reuses_acl_queryset_across_executes(self):
        """Proxy for batch view sharing one engine; not an HTTP batch integration test."""
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

    def test_acl_cache_key_includes_project_ids(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        project_a = _project(workspace, user, name="A")
        project_b = _project(workspace, user, name="B")
        for project in (project_a, project_b):
            state = State.objects.create(
                project=project,
                name="Backlog",
                color="#000000",
                group="backlog",
            )
            Issue.objects.create(
                project=project,
                workspace=workspace,
                name=f"issue-{project.identifier}",
                state=state,
                priority="medium",
                created_by=user,
            )

        engine = AnalyticsEngineV2(workspace=workspace, principal=user)
        base_payload = {
            "version": 1,
            "metrics": [{"key": "work_item_count"}],
            "time": {"preset": "none"},
        }
        query_a = AnalyticsQueryV2.from_payload({**base_payload, "project_ids": [str(project_a.id)]})
        query_b = AnalyticsQueryV2.from_payload({**base_payload, "project_ids": [str(project_b.id)]})

        with patch(
            "plane.analytics.v2.query.base_issue_queryset",
            wraps=base_issue_queryset,
        ) as acl_mock:
            engine.execute(query_a)
            engine.execute(query_b)

        project_calls = [c.kwargs.get("project_ids") for c in acl_mock.call_args_list]
        assert [str(project_a.id)] in project_calls
        assert [str(project_b.id)] in project_calls
        assert acl_mock.call_count >= 2


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
