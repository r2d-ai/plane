# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Multi-membership warning + ACL safety tests (spec §16, §49.3).

* §16: a warning is returned when normalisation is applied on a multi-valued
  dimension (so the consumer knows percentages can exceed 100%).
* §49.3: the API + ACL regression scenario (public A, private B, private C,
  X sees A+B, Y sees A+C). The hidden project must not appear in any field.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.normalization import NORMALIZATION_GROUP_TOTAL
from plane.db.models import (
    Issue,
    IssueAssignee,
    Label,
    Project,
    ProjectMember,
    ProjectNetwork,
    State,
    User,
    Workspace,
    WorkspaceMember,
)


pytestmark = pytest.mark.unit


def _make_workspace(slug):
    owner = User.objects.create(email=f"owner-{slug}@plane.so", username=f"owner-{slug}")
    owner.set_password("pw")
    owner.save()
    return Workspace.objects.create(name="WS", slug=slug, owner=owner, timezone="UTC")


def _make_state(project, group):
    return State.objects.create(project=project, name="Backlog", color="#000", group=group)


def _make_project(workspace, network, name):
    return Project.objects.create(
        workspace=workspace,
        name=name,
        identifier=f"P{uuid4().hex[:4].upper()}",
        created_by=workspace.owner,
        updated_by=workspace.owner,
        network=network,
    )


def _add_to_workspace(user, workspace):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20, is_active=True)


def _add_to_project(user, project):
    ProjectMember.objects.create(project=project, member=user, role=20, is_active=True)
    WorkspaceMember.objects.get_or_create(
        workspace=project.workspace, member=user, defaults={"role": 20, "is_active": True}
    )


@pytest.mark.unit
class TestMultiMembershipWarning:
    @pytest.fixture
    def fixture(self, db):
        ws = _make_workspace("ws-mw")
        proj = _make_project(ws, ProjectNetwork.PUBLIC.value, "P")
        state = _make_state(proj, "started")

        # Three labels.
        labels = [
            Label.objects.create(workspace=ws, project=proj, name=f"L{i}", color="#fff")
            for i in range(3)
        ]

        user = User.objects.create(email=f"u-{uuid4().hex[:6]}@plane.so", username=f"u-{uuid4().hex[:6]}")
        user.set_password("pw")
        user.save()
        _add_to_workspace(user, ws)
        _add_to_project(user, proj)

        # One issue tagged with TWO labels — multi-membership means percentages
        # could exceed 100% when normalised by label.
        issue = Issue.objects.create(
            project=proj,
            workspace=ws,
            name="Multi-label issue",
            state=state,
            priority="medium",
            created_by=user,
        )
        from plane.db.models import IssueLabel

        for label in labels[:2]:
            IssueLabel.objects.create(issue=issue, label=label, project=proj, workspace=ws)

        yield {"workspace": ws, "user": user, "issue": issue, "labels": labels}

    def test_group_total_with_labels_emits_warning(self, fixture):
        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "labels"}],
            time={"preset": "none"},
            normalization=NORMALIZATION_GROUP_TOTAL,
        )
        engine = AnalyticsEngineV2(workspace=fixture["workspace"], principal=fixture["user"])
        response = engine.execute(query)
        codes = [w["code"] for w in response.warnings]
        assert "MULTI_MEMBERSHIP_PCT" in codes

    def test_no_warning_when_dimension_is_not_multi_valued(self, fixture):
        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "state"}],
            time={"preset": "none"},
            normalization=NORMALIZATION_GROUP_TOTAL,
        )
        engine = AnalyticsEngineV2(workspace=fixture["workspace"], principal=fixture["user"])
        response = engine.execute(query)
        codes = [w["code"] for w in response.warnings]
        assert "MULTI_MEMBERSHIP_PCT" not in codes


@pytest.mark.unit
class TestACLCrossProjectScenario:
    """§49.3 mandatory scenario: A public, B and C private.
    X has access to A+B. Y has access to A+C. Neither response leaks the
    hidden project.
    """

    @pytest.fixture
    def fixture(self, db):
        ws = _make_workspace("ws-acl")
        proj_a = _make_project(ws, ProjectNetwork.PUBLIC.value, "A")
        proj_b = _make_project(ws, ProjectNetwork.SECRET.value, "B-secret")
        proj_c = _make_project(ws, ProjectNetwork.SECRET.value, "C-secret")

        states = {p.id: _make_state(p, "started") for p in (proj_a, proj_b, proj_c)}

        x = User.objects.create(email=f"x-{uuid4().hex[:6]}@plane.so", username=f"x-{uuid4().hex[:6]}")
        x.set_password("pw")
        x.save()
        y = User.objects.create(email=f"y-{uuid4().hex[:6]}@plane.so", username=f"y-{uuid4().hex[:6]}")
        y.set_password("pw")
        y.save()

        # X joins A and B; Y joins A and C.
        _add_to_workspace(x, ws)
        _add_to_workspace(y, ws)
        _add_to_project(x, proj_a)
        _add_to_project(x, proj_b)
        _add_to_project(y, proj_a)
        _add_to_project(y, proj_c)

        # Issues per project.
        for project in (proj_a, proj_b, proj_c):
            Issue.objects.create(
                project=project,
                workspace=ws,
                name=f"Issue in {project.name}",
                state=states[project.id],
                priority="medium",
                created_by=x,
            )

        yield {
            "workspace": ws,
            "proj_a": proj_a,
            "proj_b": proj_b,
            "proj_c": proj_c,
            "x": x,
            "y": y,
        }

    def _totals(self, principal, workspace):
        query = AnalyticsQueryV2(
            metrics=[{"key": "work_item_count"}],
            dimensions=[{"key": "project"}],
            time={"preset": "none"},
        )
        engine = AnalyticsEngineV2(workspace=workspace, principal=principal)
        response = engine.execute(query)
        return response

    def _stringify(self, obj):
        return "" if obj is None else str(obj)

    def test_x_sees_a_and_b_only(self, fixture):
        response = self._totals(fixture["x"], fixture["workspace"])
        groups = {self._stringify(row["group"]) for row in response.data}
        # X should see projects A and B but never C.
        assert str(fixture["proj_a"].id) in groups
        assert str(fixture["proj_b"].id) in groups
        assert str(fixture["proj_c"].id) not in groups
        # Total is 2 — one issue each in A and B.
        assert response.totals["work_item_count"] == 2.0

    def test_y_sees_a_and_c_only(self, fixture):
        response = self._totals(fixture["y"], fixture["workspace"])
        groups = {self._stringify(row["group"]) for row in response.data}
        assert str(fixture["proj_a"].id) in groups
        assert str(fixture["proj_c"].id) in groups
        assert str(fixture["proj_b"].id) not in groups
        assert response.totals["work_item_count"] == 2.0

    def test_no_hidden_project_metadata_in_response(self, fixture):
        # Hidden project identifiers must not appear in any text/metadata.
        for user, hidden in (
            (fixture["x"], fixture["proj_c"]),
            (fixture["y"], fixture["proj_b"]),
        ):
            response = self._totals(user, fixture["workspace"])
            serialised = str(response.data) + str(response.totals) + str(response.resolved)
            assert str(hidden.id) not in serialised
            assert hidden.name not in serialised