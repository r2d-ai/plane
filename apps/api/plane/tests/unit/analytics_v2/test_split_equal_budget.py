# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""§40.1 split_equal work-budget enforcement (RD-468)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.allocation import ALLOCATION_SPLIT_EQUAL
from plane.analytics.v2.query import (
    AGGREGATE_WORK_BUDGET,
    SPLIT_EQUAL_WORK_PER_ISSUE,
    WARNING_RESULT_TRUNCATED,
)
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


def _seed_project_issues(workspace: Workspace, user: User, name: str, issue_count: int) -> Project:
    project = _project(workspace, user, name=name)
    state = State.objects.create(
        project=project,
        name="Backlog",
        color="#000000",
        group="backlog",
    )
    for index in range(issue_count):
        Issue.objects.create(
            project=project,
            workspace=workspace,
            name=f"{name}-{index}",
            state=state,
            priority="medium",
            created_by=user,
        )
    return project


@pytest.mark.django_db
class TestSplitEqualWorkBudget:
    def test_split_equal_query_stays_within_work_budget_queries(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        for index in range(20):
            _seed_project_issues(workspace, user, name=f"P{index}", issue_count=100)

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count", "allocation": ALLOCATION_SPLIT_EQUAL}],
            dimensions=[{"key": "project"}],
            limit=20,
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)

        with CaptureQueriesContext(connection) as captured:
            engine.execute(query)

        max_queries = AGGREGATE_WORK_BUDGET * SPLIT_EQUAL_WORK_PER_ISSUE + 50
        assert len(captured) <= max_queries

    def test_multi_bucket_at_per_bucket_cap_emits_truncation_warning(self):
        workspace = _make_workspace()
        user = workspace.owner
        _member(user, workspace)
        for index in range(20):
            _seed_project_issues(workspace, user, name=f"Q{index}", issue_count=100)

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count", "allocation": ALLOCATION_SPLIT_EQUAL}],
            dimensions=[{"key": "project"}],
            limit=20,
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=user)
        response = engine.execute(query)

        codes = {w["code"] for w in response.warnings}
        assert WARNING_RESULT_TRUNCATED in codes
