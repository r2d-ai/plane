# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Date dimensions and date grouping (spec §9.3, §12; RD-454).

Before RD-454 the registry exposed ``created_date`` / ``completed_date`` /
``start_date`` / ``due_date`` but the engine grouped on a column of the same
name, which does not exist on ``Issue`` — any calendar x-axis raised
``FieldError``. ``time.group`` was validated and then ignored, so quarter
grouping never happened. These tests pin both behaviours.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest
from django.utils import timezone

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.dimensions import DATE_BASIS_FIELD, REGISTRY, bucket_label
from plane.db.models import Issue, Project, ProjectMember, ProjectNetwork, State, User, Workspace, WorkspaceMember


pytestmark = pytest.mark.unit


# ----- pure bucketing -----------------------------------------------------


class TestBucketLabel:
    @pytest.mark.parametrize(
        "group,expected",
        [
            ("day", "2026-07-12"),
            ("month", "2026-07"),
            ("quarter", "2026-Q3"),
            ("year", "2026"),
        ],
    )
    def test_day_month_quarter_year(self, group, expected):
        assert bucket_label(date(2026, 7, 12), group) == expected

    def test_week_bundles_to_monday(self):
        # 2026-07-12 is a Sunday → belongs to the week starting Mon 2026-07-06.
        assert bucket_label(date(2026, 7, 12), "week") == "2026-07-06"
        assert bucket_label(date(2026, 7, 6), "week") == "2026-07-06"

    def test_datetime_values_are_supported(self):
        assert bucket_label(datetime(2026, 9, 30, 23, 59), "quarter") == "2026-Q3"

    def test_none_stays_none(self):
        assert bucket_label(None, "month") is None

    def test_labels_sort_chronologically_as_strings(self):
        labels = [bucket_label(d, "quarter") for d in (date(2026, 11, 1), date(2026, 1, 1), date(2025, 7, 1))]
        assert sorted(labels) == ["2025-Q3", "2026-Q1", "2026-Q4"]


class TestDateDimensionFieldMapping:
    @pytest.mark.parametrize("key", ["created_date", "completed_date", "start_date", "due_date"])
    def test_date_dimensions_resolve_to_a_real_issue_column(self, key):
        spec = REGISTRY[key]
        assert spec.is_date is True
        assert spec.effective_field == DATE_BASIS_FIELD[key]
        # The point of the mapping: the naive key is NOT a column on Issue.
        assert spec.group_field_resolved != spec.effective_field or spec.group_field_resolved == DATE_BASIS_FIELD[key]


# ----- ORM-backed ---------------------------------------------------------


def _setup():
    owner = User.objects.create(email=f"o-{uuid4().hex[:6]}@plane.so", username=f"o-{uuid4().hex[:6]}")
    owner.set_password("pw")
    owner.save()
    workspace = Workspace.objects.create(name="WS", slug=f"ws-{uuid4().hex[:6]}", owner=owner, timezone="UTC")
    project = Project.objects.create(
        workspace=workspace,
        name="P",
        identifier=f"P{uuid4().hex[:4].upper()}",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    ProjectMember.objects.create(project=project, member=owner, role=20, is_active=True)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    state = State.objects.create(project=project, name="Backlog", color="#000000", group="backlog")
    return workspace, project, owner, state


def _make_issue(project: Workspace | Project, workspace, owner, state, created_at: datetime, priority: str = "medium"):
    issue = Issue.objects.create(
        project=project,
        workspace=workspace,
        name=f"Issue {created_at.date()}",
        state=state,
        priority=priority,
        created_by=owner,
    )
    Issue.objects.filter(id=issue.id).update(created_at=created_at)
    issue.refresh_from_db()
    return issue


@pytest.fixture
def date_setup(db):
    workspace, project, owner, state = _setup()
    issues = [
        _make_issue(project, workspace, owner, state, timezone.make_aware(datetime(2026, 1, 15, 10, 0)), "low"),
        _make_issue(project, workspace, owner, state, timezone.make_aware(datetime(2026, 3, 2, 10, 0)), "high"),
        _make_issue(project, workspace, owner, state, timezone.make_aware(datetime(2026, 7, 20, 10, 0)), "medium"),
        _make_issue(project, workspace, owner, state, timezone.make_aware(datetime(2026, 9, 1, 10, 0)), "urgent"),
    ]
    return {"workspace": workspace, "project": project, "owner": owner, "state": state, "issues": issues}


def _groups(workspace, principal, dimension, group=None, extra_dimensions=None):
    time = {"preset": "none"}
    if group:
        time["group"] = group
    query = AnalyticsQueryV2(
        metrics=[{"key": "work_item_count"}],
        dimensions=[{"key": dimension}] + (extra_dimensions or []),
        time=time,
    )
    engine = AnalyticsEngineV2(workspace=workspace, principal=principal)
    return engine.execute(query)


@pytest.mark.unit
class TestDateDimensionExecution:
    """The calendar x-axes must not raise and must bucket by ``time.group``."""

    def test_created_date_by_month(self, date_setup):
        response = _groups(date_setup["workspace"], date_setup["owner"], "created_date", group="month")
        assert [row["group"] for row in response.data] == ["2026-01", "2026-03", "2026-07", "2026-09"]
        assert all(row["value"] == 1.0 for row in response.data)

    def test_created_date_by_quarter(self, date_setup):
        """§9.3 — quarter is an intentional CE extension."""
        response = _groups(date_setup["workspace"], date_setup["owner"], "created_date", group="quarter")
        groups = [row["group"] for row in response.data]
        assert groups == ["2026-Q1", "2026-Q3"]
        assert [row["value"] for row in response.data] == [2.0, 2.0]

    def test_created_date_by_year(self, date_setup):
        response = _groups(date_setup["workspace"], date_setup["owner"], "created_date", group="year")
        assert [row["group"] for row in response.data] == ["2026"]
        assert response.data[0]["value"] == 4.0

    def test_date_dimension_defaults_to_day(self, date_setup):
        response = _groups(date_setup["workspace"], date_setup["owner"], "created_date")
        assert [row["group"] for row in response.data] == [
            "2026-01-15",
            "2026-03-02",
            "2026-07-20",
            "2026-09-01",
        ]

    def test_due_date_dimension_resolves_to_target_date(self, date_setup):
        issue = date_setup["issues"][0]
        Issue.objects.filter(id=issue.id).update(target_date=date(2026, 10, 1))
        response = _groups(date_setup["workspace"], date_setup["owner"], "due_date", group="quarter")
        # The other three work items have no due date and stay in their own group.
        assert response.data[0]["group"] == "2026-Q4"
        assert response.data[0]["value"] == 1.0

    def test_two_dimension_date_by_quarter_and_priority(self, date_setup):
        response = _groups(
            date_setup["workspace"],
            date_setup["owner"],
            "created_date",
            group="quarter",
            extra_dimensions=[{"key": "priority"}],
        )
        pairs = {(row["group"], row["series"]) for row in response.data}
        assert pairs == {
            ("2026-Q1", "low"),
            ("2026-Q1", "high"),
            ("2026-Q3", "medium"),
            ("2026-Q3", "urgent"),
        }
