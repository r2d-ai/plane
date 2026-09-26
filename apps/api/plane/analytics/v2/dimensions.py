# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dimension registry for Analytics V2 (spec §12).

Each dimension is a stable string key plus its resolution strategy: how to
group the queryset by it, whether it's multi-valued, and whether the engine
should bucket by day/week/month/quarter/year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Union

from django.db.models import F, QuerySet


CATEGORY_CATEGORICAL = "categorical"
CATEGORY_DATE = "date"

# Date basis options for date dimensions. Validated against ``time_scope.ALL_DATE_BASIS``.
DATE_BASIS_FIELD = {
    "created_date": "created_at",
    "completed_date": "completed_at",
    "start_date": "start_date",
    "due_date": "target_date",
}


@dataclass(frozen=True)
class DimensionSpec:
    key: str
    label: str
    category: str
    multi_valued: bool
    # Optional callable returning the queryset annotated with ``dim_key`` —
    # the annotation name used for grouping. If ``None``, the engine groups by
    # ``dim_key`` directly. Multi-valued dimensions always need an explicit
    # annotator (typically a ``distinct`` aggregation path downstream).
    annotator: Optional[Callable[[QuerySet, str], QuerySet]] = None
    # The annotation/DB column used for grouping. Defaults to ``key``.
    group_field: Optional[str] = None
    # True iff the dimension's underlying field is a date column and can be
    # bucketed by ``day``/``week``/``month``/``quarter``/``year``.
    is_date: bool = False
    # For date dimensions, the underlying date basis the engine should resolve
    # this dimension against. Default: created_at.
    date_basis: Optional[str] = None

    @property
    def group_field_resolved(self) -> str:
        return self.group_field or self.key

    @property
    def effective_field(self) -> str:
        """The real DB column this dimension groups on.

        Date dimensions are named after the *bucket* (``created_date``), not
        the column (``created_at``), so the registry maps them explicitly —
        without this the engine would raise ``FieldError`` for every calendar
        x-axis (§9.3, §12).
        """
        if self.is_date:
            return DATE_BASIS_FIELD.get(self.key, self.group_field_resolved)
        return self.group_field_resolved


def _annotate_labels(qs: QuerySet, alias: str) -> QuerySet:
    return qs.annotate(**{alias: F("labels__id")})


def _annotate_assignees(qs: QuerySet, alias: str) -> QuerySet:
    return qs.annotate(**{alias: F("assignees__id")})


def _annotate_modules(qs: QuerySet, alias: str) -> QuerySet:
    return qs.annotate(**{alias: F("issue_module__module_id")})


def _annotate_cycles(qs: QuerySet, alias: str) -> QuerySet:
    return qs.annotate(**{alias: F("issue_cycle__cycle_id")})


REGISTRY: Dict[str, DimensionSpec] = {
    "state": DimensionSpec(
        key="state",
        label="State",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="state_id",
    ),
    "state_group": DimensionSpec(
        key="state_group",
        label="State group",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="state__group",
    ),
    "project": DimensionSpec(
        key="project",
        label="Project",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="project_id",
    ),
    "priority": DimensionSpec(
        key="priority",
        label="Priority",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="priority",
    ),
    "assignees": DimensionSpec(
        key="assignees",
        label="Assignee",
        category=CATEGORY_CATEGORICAL,
        multi_valued=True,
        annotator=_annotate_assignees,
    ),
    "created_by": DimensionSpec(
        key="created_by",
        label="Created by",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="created_by_id",
    ),
    "labels": DimensionSpec(
        key="labels",
        label="Label",
        category=CATEGORY_CATEGORICAL,
        multi_valued=True,
        annotator=_annotate_labels,
    ),
    "cycle": DimensionSpec(
        key="cycle",
        label="Cycle",
        category=CATEGORY_CATEGORICAL,
        multi_valued=True,
        annotator=_annotate_cycles,
    ),
    "module": DimensionSpec(
        key="module",
        label="Module",
        category=CATEGORY_CATEGORICAL,
        multi_valued=True,
        annotator=_annotate_modules,
    ),
    "work_item_type": DimensionSpec(
        key="work_item_type",
        label="Work item type",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="type_id",
    ),
    "estimate_point": DimensionSpec(
        key="estimate_point",
        label="Estimate point",
        category=CATEGORY_CATEGORICAL,
        multi_valued=False,
        group_field="estimate_point_id",
    ),
    "created_date": DimensionSpec(
        key="created_date",
        label="Created date",
        category=CATEGORY_DATE,
        multi_valued=False,
        is_date=True,
        date_basis="created_at",
    ),
    "completed_date": DimensionSpec(
        key="completed_date",
        label="Completed date",
        category=CATEGORY_DATE,
        multi_valued=False,
        is_date=True,
        date_basis="completed_at",
    ),
    "start_date": DimensionSpec(
        key="start_date",
        label="Start date",
        category=CATEGORY_DATE,
        multi_valued=False,
        is_date=True,
        date_basis="start_date",
    ),
    "due_date": DimensionSpec(
        key="due_date",
        label="Due date",
        category=CATEGORY_DATE,
        multi_valued=False,
        is_date=True,
        date_basis="target_date",
    ),
}


def bucket_label(value: Union[date, datetime, None], group: str) -> Optional[str]:
    """Bucket a raw date value into the chart label for ``group`` (§9.3).

    Labels are ISO-shaped so they sort chronologically as plain strings:
    ``2026-07-12`` (day/week), ``2026-07`` (month), ``2026-Q3`` (quarter),
    ``2026`` (year). ``None`` stays ``None`` so "no date" keeps its own group.
    """
    if value is None:
        return None
    day = value.date() if isinstance(value, datetime) else value
    if not isinstance(day, date):
        return str(value)
    if group == "year":
        return f"{day.year:04d}"
    if group == "quarter":
        return f"{day.year:04d}-Q{((day.month - 1) // 3) + 1}"
    if group == "month":
        return f"{day.year:04d}-{day.month:02d}"
    if group == "week":
        monday = day - timedelta(days=day.weekday())
        return monday.strftime("%Y-%m-%d")
    return day.strftime("%Y-%m-%d")


def validate_dimension_keys(keys: List[str]) -> None:
    unknown = [k for k in keys if k not in REGISTRY]
    if unknown:
        raise ValueError(f"Unknown dimension keys: {unknown}")


def annotate_dimension(qs: QuerySet, spec: DimensionSpec, alias: str) -> QuerySet:
    if spec.annotator is not None:
        return spec.annotator(qs, alias)
    return qs.annotate(**{alias: F(spec.group_field_resolved)})


def group_by_dim_alias() -> str:
    """The shared annotation alias for ``GROUP BY`` downstream code."""
    return "_dim"