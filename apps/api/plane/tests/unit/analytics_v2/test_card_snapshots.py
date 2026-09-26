# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Baseline snapshots for spec §7 default dashboard cards (A–L).

Pins current :class:`AnalyticsEngineV2` output before the fixed workspace
dashboard (RD-475 Phase C) wires these queries into the product registry.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List
from uuid import uuid4

import pytest
import pytz
from django.utils import timezone
from freezegun import freeze_time

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.normalization import (
    DISPLAY_VALUE_AND_PCT,
    NORMALIZATION_GRAND_TOTAL,
    NORMALIZATION_GROUP_TOTAL,
)
from plane.analytics.v2.serializer import serialise_response
from plane.db.models import (
    Issue,
    IssueAssignee,
    IssueBlocker,
    Project,
    ProjectMember,
    ProjectNetwork,
    State,
    User,
    Workspace,
    WorkspaceMember,
)

pytestmark = pytest.mark.unit

FROZEN_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=pytz.UTC)

# Product-default Analytics V2 payloads for cards A–L (spec §7).
SECTION_7_CARD_QUERIES: Dict[str, Dict[str, Any]] = {
    "A": {
        "metrics": [{"key": "pending_work_items"}],
        "time": {"preset": "none"},
    },
    "B": {
        "metrics": [{"key": "in_progress_work_items"}],
        "time": {"preset": "none"},
    },
    "C": {
        "metrics": [{"key": "completed_work_items"}],
        "time": {"preset": "this_month", "basis": "completed_at"},
    },
    "D": {
        "metrics": [{"key": "overdue_work_items"}],
        "time": {"preset": "none"},
    },
    "E": {
        "metrics": [{"key": "blocked_work_items"}],
        "time": {"preset": "none"},
    },
    "F": {
        "metrics": [{"key": "work_item_count"}, {"key": "completed_work_items"}],
        "dimensions": [{"key": "created_date"}],
        "time": {"preset": "this_month", "basis": "created_at", "group": "week"},
    },
    "G": {
        "metrics": [{"key": "work_item_count"}],
        "dimensions": [{"key": "state_group"}],
        "display": DISPLAY_VALUE_AND_PCT,
        "normalization": NORMALIZATION_GROUP_TOTAL,
        "time": {"preset": "none"},
    },
    "H": {
        "metrics": [{"key": "work_item_count", "allocation": "split_equal"}],
        "dimensions": [{"key": "assignees"}],
        "display": DISPLAY_VALUE_AND_PCT,
        "normalization": NORMALIZATION_GROUP_TOTAL,
        "allocation": "split_equal",
        "time": {"preset": "none"},
    },
    "I": {
        "metrics": [{"key": "work_item_count", "allocation": "split_equal"}],
        "dimensions": [{"key": "assignees"}, {"key": "project"}],
        "display": DISPLAY_VALUE_AND_PCT,
        "normalization": NORMALIZATION_GRAND_TOTAL,
        "allocation": "split_equal",
        "time": {"preset": "none"},
    },
    "J": {
        "metrics": [{"key": "work_item_count"}],
        "dimensions": [{"key": "priority"}],
        "display": DISPLAY_VALUE_AND_PCT,
        "normalization": NORMALIZATION_GROUP_TOTAL,
        "time": {"preset": "none"},
    },
    "K": {
        "metrics": [{"key": "work_item_count"}],
        "dimensions": [{"key": "project"}],
        "display": DISPLAY_VALUE_AND_PCT,
        "normalization": NORMALIZATION_GROUP_TOTAL,
        "time": {"preset": "none"},
    },
    # Attention table (§7.5): P0 pins a deterministic urgent-work slice until the
    # dedicated work-item table renderer lands in Phase C.
    "L": {
        "metrics": [{"key": "work_item_count"}],
        "filters": {"priority": ["urgent"]},
        "time": {"preset": "none"},
    },
}


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            "" if row.get("group") is None else str(row.get("group")),
            "" if row.get("series") is None else str(row.get("series")),
        ),
    )


def _label_dimension(value: Any, id_labels: Dict[str, str]) -> Any:
    if value is None or value == "-":
        return value
    return id_labels.get(str(value), value)


def _snapshot_engine_payload(
    serialised: Dict[str, Any], *, id_labels: Dict[str, str]
) -> Dict[str, Any]:
    """Stable subset for golden comparisons (no workspace/project UUIDs)."""
    data: List[Dict[str, Any]] = []
    for row in serialised.get("data") or []:
        labelled = dict(row)
        labelled["group"] = _label_dimension(row.get("group"), id_labels)
        labelled["series"] = _label_dimension(row.get("series"), id_labels)
        data.append(labelled)
    return {
        "data": _sort_rows(data),
        "totals": serialised.get("totals") or {},
        "warnings": serialised.get("warnings") or [],
    }


def _build_card_snapshot_world():
    owner = User.objects.create(
        email=f"owner-{uuid4().hex[:6]}@plane.so",
        username=f"owner-{uuid4().hex[:6]}",
    )
    owner.set_password("pw")
    owner.save()
    workspace = Workspace.objects.create(
        name="Card snapshot WS",
        slug=f"ws-cards-{uuid4().hex[:6]}",
        owner=owner,
        timezone="UTC",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)

    project_alpha = Project.objects.create(
        workspace=workspace,
        name="Alpha",
        identifier=f"A{uuid4().hex[:3].upper()}",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    project_beta = Project.objects.create(
        workspace=workspace,
        name="Beta",
        identifier=f"B{uuid4().hex[:3].upper()}",
        created_by=owner,
        updated_by=owner,
        network=ProjectNetwork.PUBLIC.value,
    )
    for project in (project_alpha, project_beta):
        ProjectMember.objects.create(project=project, member=owner, role=20, is_active=True)

    assignee = User.objects.create(
        email=f"assignee-{uuid4().hex[:6]}@plane.so",
        username=f"assignee-{uuid4().hex[:6]}",
    )
    assignee.set_password("pw")
    assignee.save()
    WorkspaceMember.objects.create(workspace=workspace, member=assignee, role=15, is_active=True)
    for project in (project_alpha, project_beta):
        ProjectMember.objects.create(project=project, member=assignee, role=15, is_active=True)

    states = {
        "backlog": State.objects.create(
            project=project_alpha, name="Backlog", color="#111111", group="backlog"
        ),
        "started": State.objects.create(
            project=project_alpha, name="Started", color="#222222", group="started"
        ),
        "completed": State.objects.create(
            project=project_alpha, name="Done", color="#333333", group="completed"
        ),
    }
    for group, name in (
        ("backlog", "Backlog B"),
        ("started", "Started B"),
        ("completed", "Done B"),
    ):
        State.objects.create(project=project_beta, name=name, color="#000000", group=group)

    def _issue(
        *,
        name: str,
        project: Project,
        state: State,
        priority: str = "medium",
        target_date: date | None = None,
        created_at: datetime | None = None,
        assignee: User | None = None,
    ) -> Issue:
        issue = Issue.objects.create(
            project=project,
            workspace=workspace,
            name=name,
            state=state,
            priority=priority,
            target_date=target_date,
            created_by=owner,
        )
        if created_at is not None:
            Issue.objects.filter(id=issue.id).update(created_at=created_at)
            issue.refresh_from_db()
        if assignee is not None:
            IssueAssignee.objects.create(
                issue=issue,
                assignee=assignee,
                project=project,
                workspace=workspace,
            )
        return issue

    with freeze_time(FROZEN_NOW):
        backlog = _issue(
            name="Pending item",
            project=project_alpha,
            state=states["backlog"],
            priority="low",
            created_at=timezone.make_aware(datetime(2026, 9, 1, 9, 0)),
            assignee=assignee,
        )
        in_progress = _issue(
            name="Active item",
            project=project_beta,
            state=State.objects.get(project=project_beta, group="started"),
            priority="high",
            created_at=timezone.make_aware(datetime(2026, 9, 10, 9, 0)),
            assignee=assignee,
        )
        completed = _issue(
            name="Finished item",
            project=project_alpha,
            state=states["completed"],
            priority="medium",
            created_at=timezone.make_aware(datetime(2026, 9, 5, 9, 0)),
            assignee=assignee,
        )
        Issue.objects.filter(id=completed.id).update(
            completed_at=timezone.make_aware(datetime(2026, 9, 8, 15, 0))
        )
        overdue = _issue(
            name="Overdue item",
            project=project_alpha,
            state=states["started"],
            priority="urgent",
            target_date=date(2026, 9, 1),
            created_at=timezone.make_aware(datetime(2026, 8, 20, 9, 0)),
        )
        blocked = _issue(
            name="Blocked item",
            project=project_beta,
            state=State.objects.get(project=project_beta, group="backlog"),
            priority="medium",
            created_at=timezone.make_aware(datetime(2026, 9, 12, 9, 0)),
        )
        blocker = _issue(
            name="Blocker",
            project=project_beta,
            state=State.objects.get(project=project_beta, group="started"),
            priority="low",
            created_at=timezone.make_aware(datetime(2026, 9, 11, 9, 0)),
        )
        IssueBlocker.objects.create(
            block=blocked,
            blocked_by=blocker,
            project=project_beta,
            workspace=workspace,
            created_by=owner,
        )

    return {
        "workspace": workspace,
        "owner": owner,
        "assignee": assignee,
        "id_labels": {
            str(project_alpha.id): "Alpha",
            str(project_beta.id): "Beta",
            str(assignee.id): "assignee",
        },
        "issues": {
            "backlog": backlog,
            "in_progress": in_progress,
            "completed": completed,
            "overdue": overdue,
            "blocked": blocked,
        },
    }


@pytest.fixture
def card_snapshot_world(db):
    return _build_card_snapshot_world()


@pytest.mark.parametrize("card_id", list(SECTION_7_CARD_QUERIES))
def test_section_7_card_aggregate_snapshot(card_snapshot_world, card_id):
    body = SECTION_7_CARD_QUERIES[card_id]
    query = AnalyticsQueryV2.from_payload({"version": 1, "source": "work_items", **body})
    engine = AnalyticsEngineV2(
        workspace=card_snapshot_world["workspace"],
        principal=card_snapshot_world["owner"],
    )
    with freeze_time(FROZEN_NOW):
        response = engine.execute(query)
    snapshot = _snapshot_engine_payload(
        serialise_response(response),
        id_labels=card_snapshot_world["id_labels"],
    )
    assert snapshot == EXPECTED_AGGREGATE_SNAPSHOTS[card_id]


# Golden baselines — update only when Analytics V2 semantics intentionally change.
EXPECTED_AGGREGATE_SNAPSHOTS: Dict[str, Dict[str, Any]] = {
    "A": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 2.0}],
        "totals": {"pending_work_items": 2.0},
        "warnings": [],
    },
    "B": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 3.0}],
        "totals": {"in_progress_work_items": 3.0},
        "warnings": [],
    },
    "C": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 1.0}],
        "totals": {"completed_work_items": 1.0},
        "warnings": [],
    },
    "D": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 1.0}],
        "totals": {"overdue_work_items": 1.0},
        "warnings": [],
    },
    "E": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 1.0}],
        "totals": {"blocked_work_items": 1.0},
        "warnings": [],
    },
    "F": {
        "data": [
            {"group": "2026-08-31", "percentage": None, "series": "-", "value": 2.0},
            {"group": "2026-09-07", "percentage": None, "series": "-", "value": 3.0},
        ],
        "totals": {"completed_work_items": 1.0, "work_item_count": 5.0},
        "warnings": [],
    },
    "G": {
        "data": [
            {
                "display": "2 · 100.0%",
                "group": "backlog",
                "percentage": 1.0,
                "series": "-",
                "value": 2.0,
            },
            {
                "display": "1 · 100.0%",
                "group": "completed",
                "percentage": 1.0,
                "series": "-",
                "value": 1.0,
            },
            {
                "display": "3 · 100.0%",
                "group": "started",
                "percentage": 1.0,
                "series": "-",
                "value": 3.0,
            },
        ],
        "totals": {"work_item_count": 6.0},
        "warnings": [],
    },
    "H": {
        "data": [
            {
                "display": "3 · 100.0%",
                "group": None,
                "percentage": 1.0,
                "series": "-",
                "value": 3.0,
            },
            {
                "display": "3 · 100.0%",
                "group": "assignee",
                "percentage": 1.0,
                "series": "-",
                "value": 3.0,
            },
        ],
        "totals": {"work_item_count": 6.0},
        "warnings": [
            {
                "code": "MULTI_MEMBERSHIP_PCT",
                "message": "Work items can belong to multiple values in this dimension. "
                "Shares across groups may exceed 100%.",
            }
        ],
    },
    "I": {
        "data": [
            {
                "display": "1 · 16.7%",
                "group": None,
                "percentage": 0.16666666666666666,
                "series": "Alpha",
                "value": 1.0,
            },
            {
                "display": "2 · 33.3%",
                "group": None,
                "percentage": 0.3333333333333333,
                "series": "Beta",
                "value": 2.0,
            },
            {
                "display": "2 · 33.3%",
                "group": "assignee",
                "percentage": 0.3333333333333333,
                "series": "Alpha",
                "value": 2.0,
            },
            {
                "display": "1 · 16.7%",
                "group": "assignee",
                "percentage": 0.16666666666666666,
                "series": "Beta",
                "value": 1.0,
            },
        ],
        "totals": {"work_item_count": 6.0},
        "warnings": [],
    },
    "J": {
        "data": [
            {
                "display": "1 · 100.0%",
                "group": "high",
                "percentage": 1.0,
                "series": "-",
                "value": 1.0,
            },
            {
                "display": "2 · 100.0%",
                "group": "low",
                "percentage": 1.0,
                "series": "-",
                "value": 2.0,
            },
            {
                "display": "2 · 100.0%",
                "group": "medium",
                "percentage": 1.0,
                "series": "-",
                "value": 2.0,
            },
            {
                "display": "1 · 100.0%",
                "group": "urgent",
                "percentage": 1.0,
                "series": "-",
                "value": 1.0,
            },
        ],
        "totals": {"work_item_count": 6.0},
        "warnings": [],
    },
    "K": {
        "data": [
            {
                "display": "3 · 100.0%",
                "group": "Alpha",
                "percentage": 1.0,
                "series": "-",
                "value": 3.0,
            },
            {
                "display": "3 · 100.0%",
                "group": "Beta",
                "percentage": 1.0,
                "series": "-",
                "value": 3.0,
            },
        ],
        "totals": {"work_item_count": 6.0},
        "warnings": [],
    },
    "L": {
        "data": [{"group": "-", "percentage": None, "series": "-", "value": 1.0}],
        "totals": {"work_item_count": 1.0},
        "warnings": [],
    },
}
