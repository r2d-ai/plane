# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Metric registry for Analytics V2 (spec §13).

A metric is a stable string key plus its aggregation semantics: how the
underlying queryset should be filtered/aggregated, what semantic category it
falls into (``current_state``/``event``/``interval``), and what allocation
modes are valid for it.

Adding a metric = registering an entry below. The engine refuses unknown
metrics at validation time — never accepts a raw database field name from the
client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from django.db.models import Count, Q, QuerySet, Sum


# Semantic categories per §13.3. Used by the response metadata so callers know
# what kind of behaviour to expect from a metric.
SEMANTIC_CURRENT_STATE = "current_state"
SEMANTIC_EVENT = "event"
SEMANTIC_INTERVAL = "interval"


# Default allocation per §15.3. ``split_equal`` is the safe default for
# workload-oriented metrics; the rest default to ``full_credit`` because their
# values are unit-counted per issue, not split across assignees.
ALLOCATION_FULL_CREDIT = "full_credit"
ALLOCATION_SPLIT_EQUAL = "split_equal"
ALLOCATION_NONE = "none"

VALID_ALLOCATIONS = frozenset({ALLOCATION_FULL_CREDIT, ALLOCATION_SPLIT_EQUAL, ALLOCATION_NONE})


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    category: str
    # What default allocation mode this metric uses. ``none`` means the metric
    # cannot be allocated (e.g. estimate-point counts that belong to the issue,
    # not to any assignee).
    default_allocation: str
    # Optional queryset-level filter that restricts the count/sum to the
    # metric's predicate. ``None`` means: no extra filter.
    predicate: Optional[Callable[[], Q]] = None
    # Aggregation strategy. ``count`` is Count(id) filtered by predicate,
    # ``estimate_sum`` is Sum(estimate_point__value) filtered by predicate,
    # ``count_distinct`` is Count(id, distinct=True) (used for drill-down).
    aggregation: str = "count"
    # Whether ``split_equal`` allocation is meaningful for this metric. Estimate
    # points are split-equally across assignees; current-state flags are not.
    supports_split_equal: bool = False


def _q(completed: bool = False) -> Q:
    if completed:
        return Q(state__group="completed")
    return Q()


def _q_pending() -> Q:
    return Q(state__group__in=["backlog", "unstarted"])


def _q_in_progress() -> Q:
    return Q(state__group="started")


def _q_blocked() -> Q:
    # An issue is blocked if some IssueBlocker row has it as ``blocked_by`` and
    # the blocker still exists.
    return Q(issue_blocked_issues__isnull=False, issue_blocked_issues__deleted_at__isnull=True)


def _q_overdue() -> Q:
    # Overdue = target_date < today AND state not in (completed, cancelled)
    from django.utils import timezone

    today = timezone.now().date()
    return Q(target_date__lt=today) & ~Q(state__group__in=["completed", "cancelled"])


def _q_unassigned() -> Q:
    return Q(assignees__isnull=True) | Q(issue_assignee__deleted_at__isnull=False)


def _q_due_today() -> Q:
    from django.utils import timezone

    return Q(target_date=timezone.now().date())


def _q_due_this_week() -> Q:
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now().date()
    return Q(target_date__gte=today, target_date__lte=today + timedelta(days=7))


# The full P0 registry. Adding a metric = adding an entry here. Order matters
# only for stable serialisation in the response schema.
REGISTRY: Dict[str, MetricSpec] = {
    "work_item_count": MetricSpec(
        key="work_item_count",
        label="Work item count",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        aggregation="count",
        supports_split_equal=True,
    ),
    "estimate_points": MetricSpec(
        key="estimate_points",
        label="Estimate points",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        aggregation="estimate_sum",
        supports_split_equal=True,
    ),
    "pending_work_items": MetricSpec(
        key="pending_work_items",
        label="Pending work items",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_pending,
        supports_split_equal=True,
    ),
    "completed_work_items": MetricSpec(
        key="completed_work_items",
        label="Completed work items",
        category=SEMANTIC_EVENT,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=lambda: _q(completed=True),
        supports_split_equal=True,
    ),
    "in_progress_work_items": MetricSpec(
        key="in_progress_work_items",
        label="In progress work items",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_in_progress,
        supports_split_equal=True,
    ),
    "due_today": MetricSpec(
        key="due_today",
        label="Due today",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_due_today,
        supports_split_equal=True,
    ),
    "due_this_week": MetricSpec(
        key="due_this_week",
        label="Due this week",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_due_this_week,
        supports_split_equal=True,
    ),
    "blocked_work_items": MetricSpec(
        key="blocked_work_items",
        label="Blocked work items",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_blocked,
        supports_split_equal=True,
    ),
    "overdue_work_items": MetricSpec(
        key="overdue_work_items",
        label="Overdue work items",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_FULL_CREDIT,
        predicate=_q_overdue,
        supports_split_equal=True,
    ),
    "unassigned_work_items": MetricSpec(
        key="unassigned_work_items",
        label="Unassigned work items",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_NONE,
        predicate=_q_unassigned,
    ),
    # Allocated flavours — used when the caller explicitly asks for split_equal
    # or when the metric's default allocation should be honoured.
    "allocated_work_item_count": MetricSpec(
        key="allocated_work_item_count",
        label="Allocated work-item count",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_SPLIT_EQUAL,
        aggregation="count",
        supports_split_equal=True,
    ),
    "allocated_estimate_points": MetricSpec(
        key="allocated_estimate_points",
        label="Allocated estimate points",
        category=SEMANTIC_CURRENT_STATE,
        default_allocation=ALLOCATION_SPLIT_EQUAL,
        aggregation="estimate_sum",
        supports_split_equal=True,
    ),
}


@dataclass(frozen=True)
class MetricRequest:
    """A single metric as it appears in the query.

    ``allocation`` defaults to the metric's :attr:`MetricSpec.default_allocation`
    but the caller may override it explicitly. ``key`` MUST be in the registry.
    """

    key: str
    allocation: str = ""

    def resolved_allocation(self) -> str:
        spec = REGISTRY.get(self.key)
        if spec is None:
            raise ValueError(f"Unknown metric key: {self.key!r}")
        if not self.allocation:
            return spec.default_allocation
        if self.allocation not in VALID_ALLOCATIONS:
            raise ValueError(f"Unknown allocation: {self.allocation!r}")
        if self.allocation == ALLOCATION_SPLIT_EQUAL and not spec.supports_split_equal:
            raise ValueError(
                f"Metric {self.key!r} does not support split_equal allocation"
            )
        return self.allocation


def aggregate(queryset, spec: MetricSpec, distinct: bool = False):
    """Aggregate ``queryset`` according to ``spec``. Returns a float-like value
    suitable for normalisation.

    ``distinct=True`` is used by allocation paths to avoid double-counting
    rows that joined multiple times (e.g. for label/assignee dimensions)."""

    if spec.predicate is not None:
        qs = queryset.filter(spec.predicate())
    else:
        qs = queryset

    if spec.aggregation == "count":
        if distinct:
            return qs.distinct().count()
        return qs.count()
    if spec.aggregation == "estimate_sum":
        from django.db.models import FloatField
        from django.db.models.functions import Cast

        # estimate_point__value is stored as a string; cast for correct sum.
        # Sum() returns ``None`` for empty sets — normalise to 0.0 here so
        # downstream arithmetic never has to handle ``None``.
        total = qs.aggregate(total=Sum(Cast("estimate_point__value", output_field=FloatField())))[
            "total"
        ]
        return float(total) if total is not None else 0.0
    raise ValueError(f"Unknown aggregation: {spec.aggregation!r}")


def validate_metric_keys(keys: List[str]) -> None:
    """Raise :class:`ValueError` if any key is not in the registry."""
    unknown = [k for k in keys if k not in REGISTRY]
    if unknown:
        raise ValueError(f"Unknown metric keys: {unknown}")