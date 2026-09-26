# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Drill-down (spec §25).

A drill-down takes an Analytics V2 aggregate query plus the user's
selected dimension values, and returns the matching raw work-items under
the same ACL scope. The function never rebuilds filter logic from scratch
— it derives the row-level predicate from the *resolved* query the user
already saw on screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q, QuerySet


@dataclass(frozen=True)
class DrilldownSelection:
    """Selected dimension values that scope the drill-down.

    Each entry maps a dimension key (e.g. ``"labels"``) to one or more
    concrete values. Multi-valued dimensions allow lists. Unknown
    dimension keys raise — drill-down never invents columns.
    """

    values: Dict[str, Any]

    def __post_init__(self) -> None:
        from .dimensions import REGISTRY

        for k in self.values:
            if k not in REGISTRY:
                raise ValueError(f"Unknown dimension in drilldown: {k!r}")
            # Normalise to list for stable downstream behaviour.
            v = self.values[k]
            if v is None:
                continue
            if not isinstance(v, (list, tuple)):
                self.values[k] = [v]


def build_drilldown_queryset(
    base_queryset: QuerySet,
    selection: DrilldownSelection,
) -> QuerySet:
    """Return the ACL-filtered queryset restricted to the selected cells.

    The base queryset must already be ACL-filtered (see :mod:`acl`). The
    selection translates 1:1 into ``WHERE`` predicates against the same
    allowlisted ORM fields used by the dimension registry.
    """
    qs = base_queryset
    for dim_key, values in selection.values.items():
        if values is None:
            continue
        values = [v for v in (values if isinstance(values, (list, tuple)) else [values]) if v]
        if not values:
            continue
        # Map dimension keys to ORM filters. Keep aligned with dimensions.REGISTRY.
        if dim_key == "labels":
            qs = qs.filter(labels__id__in=values, labels__issue_label__deleted_at__isnull=True)
        elif dim_key == "assignees":
            qs = qs.filter(assignees__id__in=values, assignees__issue_assignee__deleted_at__isnull=True)
        elif dim_key == "module":
            qs = qs.filter(
                issue_module__module_id__in=values,
                issue_module__deleted_at__isnull=True,
            )
        elif dim_key == "cycle":
            qs = qs.filter(
                issue_cycle__cycle_id__in=values,
                issue_cycle__deleted_at__isnull=True,
            )
        elif dim_key == "state":
            qs = qs.filter(state_id__in=values)
        elif dim_key == "state_group":
            qs = qs.filter(state__group__in=values)
        elif dim_key == "priority":
            qs = qs.filter(priority__in=values)
        elif dim_key == "project":
            qs = qs.filter(project_id__in=values)
        elif dim_key == "created_by":
            qs = qs.filter(created_by_id__in=values)
        elif dim_key == "work_item_type":
            qs = qs.filter(type_id__in=values)
        elif dim_key == "estimate_point":
            qs = qs.filter(estimate_point_id__in=values)
        else:  # pragma: no cover — validated at construction time
            raise ValueError(f"Unknown drilldown dimension: {dim_key!r}")
    return qs.distinct()


def paginate(queryset, *, page: int = 1, page_size: int = 25, max_page_size: int = 100) -> Dict[str, Any]:
    """Apply pagination, enforcing §40.1 caps."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25
    if page_size > max_page_size:
        page_size = max_page_size
    start = (page - 1) * page_size
    end = start + page_size
    total = queryset.count()
    rows = list(queryset[start:end])
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "rows": rows,
    }


def serialize_drilldown(items: List[Any]) -> List[Dict[str, Any]]:
    """Serialise the work-item rows for the drill-down response.

    Uses ``model_to_dict``-style fields expected by the frontend; ACL is
    already enforced upstream so no extra filtering is done here.
    """
    out: List[Dict[str, Any]] = []
    for issue in items:
        out.append(
            {
                "id": str(issue.id),
                "sequence_id": issue.sequence_id,
                "project_id": str(issue.project_id),
                "name": issue.name,
                "priority": issue.priority,
                "state_id": str(issue.state_id) if issue.state_id else None,
                "state_group": getattr(getattr(issue, "state", None), "group", None),
                "estimate_point": float(issue.estimate_point.value)
                if getattr(issue, "estimate_point", None) and getattr(issue.estimate_point, "value", None) is not None
                else None,
                "start_date": issue.start_date.isoformat() if issue.start_date else None,
                "target_date": issue.target_date.isoformat() if issue.target_date else None,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "completed_at": issue.completed_at.isoformat() if issue.completed_at else None,
            }
        )
    return out