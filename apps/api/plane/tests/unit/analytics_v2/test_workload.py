# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workload + time-basis integration tests (spec §49.4, §49.5).

Uses real ORM models so we exercise the full aggregation path including
multi-assignee joins, time-basis filtering, and lifecycle_overlap.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytz
from django.utils import timezone

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.allocation import ALLOCATION_FULL_CREDIT, ALLOCATION_SPLIT_EQUAL
from plane.analytics.v2.time_scope import (
    DATE_BASIS_COMPLETED,
    DATE_BASIS_CREATED,
    DATE_BASIS_LIFECYCLE,
    PRESET_CUSTOM,
)
from plane.db.models import (
    Estimate,
    EstimatePoint,
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


# ----- helpers ------------------------------------------------------------


def _make_workspace(slug: str = "ws") -> Workspace:
    owner = User.objects.create(
        email=f"owner-{slug}-{uuid4().hex[:6]}@plane.so",
        username=f"owner-{slug}-{uuid4().hex[:6]}",
    )
    owner.set_password("pw")
    owner.save()
    return Workspace.objects.create(name="WS", slug=slug, owner=owner, timezone="UTC")


def _make_state(project: Project, group: str, name: str = "Backlog") -> State:
    return State.objects.create(
        project=project,
        name=name,
        color="#000000",
        group=group,
    )


def _add_to_workspace(user: User, workspace: Workspace, role: int = 20) -> None:
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)


def _add_to_project(user: User, project: Project, role: int = 20) -> None:
    ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    WorkspaceMember.objects.get_or_create(
        workspace=project.workspace, member=user, defaults={"role": role, "is_active": True}
    )


def _make_project(workspace: Workspace, network: int = ProjectNetwork.PUBLIC.value, name: str = "P") -> Project:
    return Project.objects.create(
        workspace=workspace,
        name=name,
        identifier=f"P{uuid4().hex[:4].upper()}",
        created_by=workspace.owner,
        updated_by=workspace.owner,
        network=network,
    )


@pytest.fixture
def engine_setup(db):
    workspace = _make_workspace("ws-wl")
    project_a = _make_project(workspace, network=ProjectNetwork.PUBLIC.value, name="A")
    project_b = _make_project(workspace, network=ProjectNetwork.PUBLIC.value, name="B")

    state = _make_state(project_a, "started")
    # Create states for both projects so IssueManager doesn't filter them out.
    State.objects.create(project=project_b, name="Backlog", color="#000000", group="backlog")

    user_x = User.objects.create(email=f"x-{uuid4().hex[:6]}@plane.so", username=f"x-{uuid4().hex[:6]}")
    user_x.set_password("pw")
    user_x.save()
    user_y = User.objects.create(email=f"y-{uuid4().hex[:6]}@plane.so", username=f"y-{uuid4().hex[:6]}")
    user_y.set_password("pw")
    user_y.save()
    user_z = User.objects.create(email=f"z-{uuid4().hex[:6]}@plane.so", username=f"z-{uuid4().hex[:6]}")
    user_z.set_password("pw")
    user_z.save()

    for u in (user_x, user_y, user_z):
        _add_to_workspace(u, workspace)
        _add_to_project(u, project_a)
        _add_to_project(u, project_b)

    # EstimatePoint of 10 for project A so estimate_points metric has data.
    estimate = Estimate.objects.create(
        project=project_a, workspace=workspace, name="T-Shirt", type="points", created_by=user_x
    )
    estimate_point = EstimatePoint.objects.create(
        project=project_a,
        workspace=workspace,
        estimate=estimate,
        key=10,
        value="10",
    )

    # Single 10-point issue assigned to BOTH X and Y. Z is unassigned.
    issue = Issue.objects.create(
        project=project_a,
        workspace=workspace,
        name="Split issue",
        state=state,
        priority="medium",
        point=10,
        estimate_point=estimate_point,
        created_by=user_x,
    )
    IssueAssignee.objects.create(issue=issue, assignee=user_x, project=project_a, workspace=workspace)
    IssueAssignee.objects.create(issue=issue, assignee=user_y, project=project_a, workspace=workspace)

    yield {
        "workspace": workspace,
        "project_a": project_a,
        "project_b": project_b,
        "user_x": user_x,
        "user_y": user_y,
        "user_z": user_z,
        "issue": issue,
        "estimate_point": estimate_point,
    }


@pytest.mark.unit
class TestWorkloadMultiAssignee:
    """§49.4: 10-point issue on A+B → full credit 10/10, split equal 5/5."""

    def _run_count(self, principal, workspace, allocation):
        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count", "allocation": allocation}],
            dimensions=[{"key": "assignees"}],
            time={"preset": "none"},
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=principal)
        response = engine.execute(query)
        return {row["group"]: row["value"] for row in response.data}

    def test_full_credit_gives_each_assignee_full_value(self, engine_setup):
        ws = engine_setup["workspace"]
        out = self._run_count(engine_setup["user_z"], ws, ALLOCATION_FULL_CREDIT)
        assert out.get(str(engine_setup["user_x"].id)) == 1.0
        assert out.get(str(engine_setup["user_y"].id)) == 1.0

    def test_split_equal_gives_each_assignee_half_value(self, engine_setup):
        ws = engine_setup["workspace"]
        out = self._run_count(engine_setup["user_z"], ws, ALLOCATION_SPLIT_EQUAL)
        assert out.get(str(engine_setup["user_x"].id)) == 0.5
        assert out.get(str(engine_setup["user_y"].id)) == 0.5

    def test_estimate_points_split_equal(self, engine_setup):
        """Same setup with estimate_points — each assignee should see 5."""
        query = AnalyticsQueryV2(
            metrics=[{"key": "estimate_points", "allocation": ALLOCATION_SPLIT_EQUAL}],
            dimensions=[{"key": "assignees"}],
            time={"preset": "none"},
        )
        engine = AnalyticsEngineV2(workspace=engine_setup["workspace"], principal=engine_setup["user_z"])
        response = engine.execute(query)
        out = {row["group"]: row["value"] for row in response.data}
        assert out.get(str(engine_setup["user_x"].id)) == 5.0
        assert out.get(str(engine_setup["user_y"].id)) == 5.0


@pytest.mark.unit
class TestDrillDownReturnsOneIssue:
    """§49.4: drill-down must still see the single issue, regardless of allocation."""

    def test_drill_down_returns_the_single_underlying_issue(self, engine_setup):
        from plane.analytics.v2.drilldown import DrilldownSelection

        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count", "allocation": ALLOCATION_SPLIT_EQUAL}],
            dimensions=[{"key": "assignees"}],
            time={"preset": "none"},
        )
        engine = AnalyticsEngineV2(workspace=engine_setup["workspace"], principal=engine_setup["user_z"])
        selection = DrilldownSelection(
            values={"assignees": [str(engine_setup["user_x"].id)]}
        )
        result = engine.drilldown(query=query, selection=selection)
        assert result["total"] == 1
        assert len(result["rows"]) == 1
        assert result["rows"][0]["id"] == str(engine_setup["issue"].id)
        # Split-equal contribution is 0.5, not 1.0
        assert result["contributions"]["work_item_count"] == 0.5


@pytest.mark.unit
class TestTimeBasis:
    """§49.5: created_at vs completed_at vs lifecycle_overlap, anchored to a
    single work item whose created_at is in July and completed_at is in September."""

    @pytest.fixture
    def time_setup(self, db):
        ws = _make_workspace("ws-time")
        proj = _make_project(ws, name="T")
        state = _make_state(proj, "completed", name="Done")

        user = User.objects.create(email=f"t-{uuid4().hex[:6]}@plane.so", username=f"t-{uuid4().hex[:6]}")
        user.set_password("pw")
        user.save()
        _add_to_workspace(user, ws)
        _add_to_project(user, proj)

        # An issue created in July, completed in September.
        issue = Issue.objects.create(
            project=proj,
            workspace=ws,
            name="Cross-month issue",
            state=state,
            priority="medium",
            created_by=user,
        )
        # Override the auto-managed completed_at/state by directly setting
        # fields. Issue.save() tries to manage state changes; we patch around it
        # via .update() to keep this test deterministic.
        Issue.objects.filter(pk=issue.pk).update(
            created_at=datetime(2026, 7, 10, 12, 0, tzinfo=pytz.UTC),
            completed_at=datetime(2026, 9, 12, 9, 0, tzinfo=pytz.UTC),
        )

        yield {
            "workspace": ws,
            "project": proj,
            "user": user,
            "issue": issue,
        }

    def _count(self, principal, ws, basis):
        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[],
            time={
                "preset": PRESET_CUSTOM,
                "basis": basis,
                "timezone": "UTC",
                "start": "2026-09-01",
                "end": "2026-09-30",
            },
        )
        engine = AnalyticsEngineV2(workspace=ws, principal=principal)
        return engine.execute(query).totals.get("work_item_count", 0.0)

    def test_created_at_excludes_september_issue(self, time_setup):
        total = self._count(time_setup["user"], time_setup["workspace"], DATE_BASIS_CREATED)
        assert total == 0.0

    def test_completed_at_includes_september_issue(self, time_setup):
        total = self._count(time_setup["user"], time_setup["workspace"], DATE_BASIS_COMPLETED)
        assert total == 1.0

    def test_lifecycle_overlap_includes_september_issue(self, time_setup):
        # created_at (Jul 10) <= end (Sep 30) AND (completed_at IS NULL OR >= Sep 1)
        # → completes condition holds (Sep 12 >= Sep 1).
        total = self._count(time_setup["user"], time_setup["workspace"], DATE_BASIS_LIFECYCLE)
        assert total == 1.0