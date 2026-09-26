# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Analytics Engine V2 — single canonical query API (spec §11, §36).

Public surface:

* :class:`AnalyticsQueryV2`   — declarative query model
* :class:`AnalyticsResponseV2` — structured response
* :class:`AnalyticsEngineV2`  — the entry point; takes a query + workspace +
  principal, returns a response.

The engine never mutates persisted data, never accepts raw DB field names
from the client, and resolves ACL first (§37.1).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.db.models import Q, QuerySet

from . import allocation as allocation_module
from . import filters as filters_module
from . import metrics as metrics_module
from . import dimensions as dimensions_module
from .acl import base_issue_queryset
from .comparison import resolve_comparison
from .drilldown import DrilldownSelection, build_drilldown_queryset, paginate, serialize_drilldown
from .normalization import (
    DISPLAY_VALUE,
    DISPLAY_VALUE_AND_PCT,
    NORMALIZATION_NONE,
    VALID_DISPLAYS,
    VALID_NORMALIZATIONS,
    Cell,
    format_display,
    normalize,
)
from .time_scope import (
    ALL_DATE_BASIS,
    ALL_DATE_GROUPS,
    ALL_PRESETS,
    DATE_GROUP_DAY,
    ResolvedTimeScope,
    apply_time_basis,
    resolve_preset,
)


SOURCE_WORK_ITEMS = "work_items"
VALID_SOURCES = frozenset({SOURCE_WORK_ITEMS})

# §40.1 caps.
MAX_GROUPS = 20
MAX_ROWS = 100
MAX_MATRIX_ROWS = 50
MAX_MATRIX_COLS = 30
# Hard ceiling on metric aggregate calls per query (1D and 2D share this budget).
AGGREGATE_WORK_BUDGET = MAX_ROWS
MAX_BATCH_QUERIES = 20
MAX_SPLIT_EQUAL_ISSUES = MAX_ROWS
# Per-issue ORM cost for split_equal (assignee count + up to two aggregates).
SPLIT_EQUAL_WORK_PER_ISSUE = 3

WARNING_RESULT_TRUNCATED = "RESULT_TRUNCATED"


@dataclass
class AnalyticsQueryV2:
    """The V2 declarative query.

    ``metrics`` and ``dimensions`` are keys validated against the registries.
    The ``time`` block drives preset resolution and date basis. ``comparison``
    is optional and resolves an additional previous-period scope.
    """

    version: int = 1
    source: str = SOURCE_WORK_ITEMS
    project_ids: List[str] = field(default_factory=list)
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    dimensions: List[Dict[str, Any]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    time: Dict[str, Any] = field(default_factory=dict)
    comparison: Dict[str, Any] = field(default_factory=dict)
    normalization: str = NORMALIZATION_NONE
    display: str = DISPLAY_VALUE
    allocation: str = ""
    sort: List[Dict[str, Any]] = field(default_factory=list)
    limit: int = MAX_GROUPS

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "AnalyticsQueryV2":
        if not isinstance(payload, dict):
            raise ValueError("Query payload must be an object")
        if payload.get("version", 1) != 1:
            raise ValueError(f"Unsupported query version: {payload.get('version')}")
        source = payload.get("source", SOURCE_WORK_ITEMS)
        if source not in VALID_SOURCES:
            raise ValueError(f"Unknown source: {source!r}")
        metrics = payload.get("metrics") or []
        dimensions = payload.get("dimensions") or []
        if not metrics:
            raise ValueError("At least one metric is required")
        if len(metrics) > MAX_GROUPS:
            raise ValueError(f"Too many metrics: {len(metrics)} > {MAX_GROUPS}")
        if len(dimensions) > 2:
            raise ValueError("At most two dimensions are supported in P0")
        for m in metrics:
            if "key" not in m:
                raise ValueError("Each metric must include a key")
        for d in dimensions:
            if "key" not in d:
                raise ValueError("Each dimension must include a key")

        time = payload.get("time") or {}
        comparison = payload.get("comparison") or {}
        limit = int(payload.get("limit") or MAX_GROUPS)
        if limit > MAX_ROWS:
            raise ValueError(f"limit {limit} exceeds cap {MAX_ROWS}")

        normalization = payload.get("normalization") or NORMALIZATION_NONE
        if normalization not in VALID_NORMALIZATIONS:
            raise ValueError(f"Unknown normalization: {normalization!r}")
        display = payload.get("display") or DISPLAY_VALUE
        if display not in VALID_DISPLAYS:
            raise ValueError(f"Unknown display mode: {display!r}")
        allocation = payload.get("allocation") or ""

        return cls(
            version=int(payload.get("version", 1)),
            source=source,
            project_ids=payload.get("project_ids") or [],
            metrics=metrics,
            dimensions=dimensions,
            filters=payload.get("filters") or {},
            time=time,
            comparison=comparison,
            normalization=normalization,
            display=display,
            allocation=allocation,
            sort=payload.get("sort") or [],
            limit=limit,
        )


@dataclass
class AnalyticsResponseV2:
    """The V2 response envelope (§32.1).

    ``resolved`` is plain JSON (no Django types). ``schema`` describes each
    dimension/metric column. ``data`` is the cell list after normalisation.
    ``totals`` is the grand-total per metric. ``warnings`` collects soft
    warnings (e.g. multi-label exceeds 100%).
    """

    query: Dict[str, Any]
    resolved: Dict[str, Any]
    schema: Dict[str, Any]
    data: List[Dict[str, Any]]
    totals: Dict[str, float]
    warnings: List[Dict[str, Any]]


class AnalyticsRequestScope:
    """Per-request memoisation shared across batch ``execute`` calls."""

    __slots__ = ("_visible_project_count", "_lock")

    def __init__(self) -> None:
        self._visible_project_count: Optional[int] = None
        self._lock = threading.Lock()


class AnalyticsEngineV2:
    """The single entry point.

    Construct one instance per HTTP request (or batch request). Instances memoize
    ACL querysets and resolved time scopes for repeated ``execute`` calls within
    that request; do not reuse across requests or background jobs.
    """

    def __init__(self, *, workspace, principal, request_scope: Optional[AnalyticsRequestScope] = None):
        self.workspace = workspace
        self.principal = principal
        self._request_scope = request_scope or AnalyticsRequestScope()
        self._default_allocation = ""
        self._scope_cache: Dict[tuple, ResolvedTimeScope] = {}
        self._base_qs_cache: Dict[tuple, QuerySet] = {}
        self._aggregate_warnings: List[Dict[str, Any]] = []

    # ----- top-level API --------------------------------------------------

    def execute(self, query: AnalyticsQueryV2) -> AnalyticsResponseV2:
        self._validate_query(query)
        self._aggregate_warnings = []
        # memoize per-request default allocation so it threads into _aggregate
        self._default_allocation = query.allocation

        scope = self._get_scope(query)
        base_qs = self._get_base_qs(query)
        filtered = self._apply_filters_and_time(query, base_qs, scope)

        rows = self._aggregate(query, filtered)
        cells = self._materialise_cells(query, rows)
        normalised = normalize(
            cells,
            mode=query.normalization,
        )
        data = self._format_data(query, normalised)
        totals = self._compute_totals(rows)

        warnings = self._build_warnings(query, normalised)
        warnings.extend(self._aggregate_warnings)

        response = AnalyticsResponseV2(
            query=_echo_query(query),
            resolved={
                "start": scope.start.isoformat() if scope.start else None,
                "end": scope.end.isoformat() if scope.end else None,
                "timezone": scope.timezone,
                "preset": scope.preset,
                "visible_project_count": self._visible_project_count(),
                # §37.2: never reveal the count of *hidden* projects, only the
                # number of accessible ones.
            },
            schema={
                "metrics": [
                    {"key": m["key"], "category": metrics_module.REGISTRY[m["key"]].category}
                    for m in query.metrics
                ],
                "dimensions": [
                    {"key": d["key"], "category": dimensions_module.REGISTRY[d["key"]].category}
                    for d in query.dimensions
                ],
            },
            data=data,
            totals=totals,
            warnings=warnings,
        )

        if query.comparison and query.comparison.get("type") and query.comparison.get("type") != "none":
            response.resolved["comparison"] = self._comparison_block(query, base_qs, scope)

        return response

    def drilldown(
        self,
        *,
        query: AnalyticsQueryV2,
        selection: DrilldownSelection,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """Return the drill-down payload for a selected cell."""
        self._validate_query(query)
        self._default_allocation = query.allocation

        scope = self._get_scope(query)
        base_qs = self._get_base_qs(query)
        filtered = self._apply_filters_and_time(query, base_qs, scope)
        drilldown_qs = build_drilldown_queryset(filtered, selection)

        # Contribution calculation per metric.
        contributions: Dict[str, float] = {}
        for m in query.metrics:
            spec = metrics_module.REGISTRY[m["key"]]
            mode = self._resolve_metric_allocation(m)
            value = self._metric_value_for_drilldown(drilldown_qs, spec, mode)
            contributions[m["key"]] = value

        paged = paginate(drilldown_qs, page=page, page_size=page_size)
        return {
            "query": _echo_query(query),
            "resolved": {
                "start": scope.start.isoformat() if scope.start else None,
                "end": scope.end.isoformat() if scope.end else None,
                "timezone": scope.timezone,
                "preset": scope.preset,
            },
            "selection": selection.values,
            "total": paged["total"],
            "page": paged["page"],
            "page_size": paged["page_size"],
            "rows": serialize_drilldown(paged["rows"]),
            "contributions": contributions,
        }

    # ----- internals ------------------------------------------------------

    def _validate_query(self, query: AnalyticsQueryV2) -> None:
        if query.source not in VALID_SOURCES:
            raise ValueError(f"Unknown source: {query.source!r}")
        metrics_module.validate_metric_keys([m["key"] for m in query.metrics])
        dimensions_module.validate_dimension_keys([d["key"] for d in query.dimensions])
        if query.time:
            preset = query.time.get("preset")
            if preset is not None and preset not in ALL_PRESETS:
                raise ValueError(f"Unknown time preset: {preset!r}")
            basis = query.time.get("basis")
            if basis is not None and basis not in ALL_DATE_BASIS:
                raise ValueError(f"Unknown date basis: {basis!r}")
            grouping = query.time.get("group")
            if grouping is not None and grouping not in ALL_DATE_GROUPS:
                raise ValueError(f"Unknown date grouping: {grouping!r}")

    def _resolve_scope(self, query: AnalyticsQueryV2) -> ResolvedTimeScope:
        tz_name = (query.time or {}).get("timezone") or self.workspace.timezone or "UTC"
        preset = (query.time or {}).get("preset") or "none"
        custom_start = (query.time or {}).get("start")
        custom_end = (query.time or {}).get("end")
        return resolve_preset(
            preset,
            timezone_name=tz_name,
            custom_start=custom_start,
            custom_end=custom_end,
        )

    def _scope_cache_key(self, query: AnalyticsQueryV2) -> tuple:
        t = query.time or {}
        return (
            t.get("timezone") or self.workspace.timezone or "UTC",
            t.get("preset") or "none",
            t.get("start"),
            t.get("end"),
        )

    def _get_scope(self, query: AnalyticsQueryV2) -> ResolvedTimeScope:
        key = self._scope_cache_key(query)
        cached = self._scope_cache.get(key)
        if cached is None:
            cached = self._resolve_scope(query)
            self._scope_cache[key] = cached
        return cached

    def _get_base_qs(self, query: AnalyticsQueryV2) -> QuerySet:
        key = tuple(sorted(query.project_ids or []))
        cached = self._base_qs_cache.get(key)
        if cached is None:
            cached = base_issue_queryset(
                workspace=self.workspace,
                principal=self.principal,
                project_ids=query.project_ids,
            )
            self._base_qs_cache[key] = cached
        return cached

    def _visible_project_count(self) -> int:
        scope = self._request_scope
        if scope._visible_project_count is not None:
            return scope._visible_project_count
        with scope._lock:
            if scope._visible_project_count is None:
                scope._visible_project_count = len(
                    self._get_base_qs(
                        AnalyticsQueryV2(metrics=[{"key": "work_item_count"}], project_ids=[])
                    )
                    .values_list("project_id", flat=True)
                    .distinct()
                )
            return scope._visible_project_count

    def _metric_uses_split_equal(self, spec, mode: str) -> bool:
        return (
            spec.key in {"work_item_count", "estimate_points"}
            and mode == allocation_module.ALLOCATION_SPLIT_EQUAL
        )

    def _min_bucket_work(self, metrics: Sequence[Tuple[Any, str]]) -> int:
        """Minimum work units required to aggregate one dimension bucket."""
        cost = 0
        for spec, mode in metrics:
            if self._metric_uses_split_equal(spec, mode):
                cost += SPLIT_EQUAL_WORK_PER_ISSUE
            else:
                cost += 1
        return max(1, cost)

    def _bucket_work_cap(self, metrics: Sequence[Tuple[Any, str]]) -> int:
        """Maximum dimension buckets to aggregate before sort/limit."""
        return max(1, AGGREGATE_WORK_BUDGET // max(1, len(metrics)))

    def _consume_aggregate_work(self, units: int) -> bool:
        if units > self._aggregate_work_remaining:
            self._note_truncation()
            return False
        self._aggregate_work_remaining -= units
        return True

    def _note_truncation(self) -> None:
        warning = {
            "code": WARNING_RESULT_TRUNCATED,
            "message": "The query matched more dimension values than the server cap allows; results may be incomplete.",
        }
        if warning not in self._aggregate_warnings:
            self._aggregate_warnings.append(warning)

    def _apply_filters_and_time(self, query: AnalyticsQueryV2, qs: QuerySet, scope: ResolvedTimeScope) -> QuerySet:
        qs = filters_module.apply_structured_filters(qs, query.filters)
        basis = (query.time or {}).get("basis") or "created_at"
        qs = apply_time_basis(qs, basis, scope)
        return qs

    def _aggregate(
        self, query: AnalyticsQueryV2, qs: QuerySet
    ) -> List[Tuple[Tuple[object, ...], Dict[str, float]]]:
        """Return rows of ``((dim_value, ...), {metric_key: value, ...})``.

        Single dimension (most charts): rows are ``((dim_value,), {metric: value})``.
        Two dimensions (matrix): ``((group_value, series_value), {metric: value})``.
        """
        dimensions = [dimensions_module.REGISTRY[d["key"]] for d in query.dimensions]
        metrics = [(metrics_module.REGISTRY[m["key"]], self._resolve_metric_allocation(m, query.allocation)) for m in query.metrics]
        self._aggregate_work_remaining = AGGREGATE_WORK_BUDGET

        # Use the dimension's underlying ``group_field`` for both the iteration
        # and the bucket filter. Annotations are skipped because the underlying
        # ``Issue`` queryset already carries joins from the IssueManager
        # (state, project), and ``F("project_id")`` can resolve to a joined
        # table — that produces duplicate rows when filtering.
        work_cap = self._bucket_work_cap(metrics)
        date_group = (query.time or {}).get("group") or DATE_GROUP_DAY

        if len(dimensions) == 0:
            rows = list(self._no_dimension_rows(qs, metrics))
        elif len(dimensions) == 1:
            rows = list(
                self._one_dimension_rows(
                    qs, dimensions[0], metrics, date_group=date_group, work_cap=work_cap
                )
            )
        else:
            rows = list(
                self._two_dimension_rows(
                    qs,
                    dimensions[0],
                    dimensions[1],
                    metrics,
                    date_group=date_group,
                    work_cap=work_cap,
                )
            )

        # Sort + cap.
        rows = self._sort_and_cap(rows, query)
        return rows

    def _no_dimension_rows(self, qs: QuerySet, metrics):
        # Aggregate whole queryset to a single row.
        values = {spec.key: self._aggregate_metric(qs, spec, mode) for spec, mode in metrics}
        return [((), values)]

    def _one_dimension_rows(
        self, qs: QuerySet, spec_dim, metrics, *, date_group: str, work_cap: int
    ):
        # Distinct values for the underlying field. Use the original column
        # rather than an annotation alias so that the bucket filter resolves
        # to the Issue table itself and never picks up a joined column.
        out = []
        buckets = self._dimension_buckets(qs, spec_dim, date_group)
        min_work = self._min_bucket_work(metrics)
        for index, (label, bucket_q) in enumerate(buckets):
            if index >= work_cap:
                self._note_truncation()
                break
            if self._aggregate_work_remaining < min_work:
                self._note_truncation()
                break
            bucket = qs.filter(bucket_q).distinct()
            values = {spec.key: self._aggregate_metric(bucket, spec, mode) for spec, mode in metrics}
            out.append(((label,), values))
        return out

    def _dimension_buckets(self, qs: QuerySet, spec, date_group: str) -> List[Tuple[Any, Q]]:
        """Return ``(label, Q)`` for every chart bucket of ``spec``.

        Categorical dimensions bucket one-per-distinct-value using the real
        Issue column (never a joined alias). Date dimensions bucket by
        ``time.group`` — day / week / month / quarter / year (§9.3) — so a
        calendar axis is not exploded into one bar per day.
        """
        field = spec.effective_field
        # ``values_list(...).distinct()`` can still return duplicate dimension
        # values when the queryset carries joins; dedupe while reading.
        raw_values: List[Any] = []
        seen: set = set()
        for value in qs.order_by(field).values_list(field, flat=True).distinct().iterator():
            if value in seen:
                continue
            seen.add(value)
            raw_values.append(value)

        if not spec.is_date:
            return [
                (
                    self._stringify(value),
                    Q(**{f"{field}__isnull": True}) if value is None else Q(**{field: value}),
                )
                for value in raw_values
            ]

        buckets: Dict[str, List[Any]] = {}
        for value in raw_values:
            label = dimensions_module.bucket_label(value, date_group)
            if label is None:
                continue
            buckets.setdefault(label, []).append(value)
        return [
            (label, Q(**{f"{field}__in": values}))
            for label, values in sorted(buckets.items())
        ]

    def _two_dimension_rows(
        self, qs: QuerySet, spec_dim_a, spec_dim_b, metrics, *, date_group: str, work_cap: int
    ):
        field_a = spec_dim_a.effective_field
        field_b = spec_dim_b.effective_field
        pair_rows = (
            qs.order_by(field_a, field_b)
            .values(field_a, field_b)
            .distinct()
            .iterator()
        )
        # Collapse raw pairs into label pairs so a date bucket (many raw dates)
        # and a categorical value stay aligned without a cartesian product.
        grouped: Dict[Tuple[Any, Any], Tuple[List[Any], List[Any]]] = {}
        truncated = False
        for row in pair_rows:
            g = row[field_a]
            s = row[field_b]
            label_a = (
                dimensions_module.bucket_label(g, date_group)
                if spec_dim_a.is_date
                else self._stringify(g)
            )
            label_b = (
                dimensions_module.bucket_label(s, date_group)
                if spec_dim_b.is_date
                else self._stringify(s)
            )
            if (label_a, label_b) not in grouped and len(grouped) >= work_cap:
                truncated = True
                break
            gvals, svals = grouped.setdefault((label_a, label_b), ([], []))
            if g is not None:
                gvals.append(g)
            if s is not None:
                svals.append(s)
        if truncated:
            self._note_truncation()
        out = []
        min_work = self._min_bucket_work(metrics)
        for (label_a, label_b), (gvals, svals) in grouped.items():
            if self._aggregate_work_remaining < min_work:
                self._note_truncation()
                break
            bucket_q = Q()
            bucket_q &= (
                Q(**{f"{field_a}__isnull": True}) if not gvals else Q(**{f"{field_a}__in": gvals})
            )
            bucket_q &= (
                Q(**{f"{field_b}__isnull": True}) if not svals else Q(**{f"{field_b}__in": svals})
            )
            bucket = qs.filter(bucket_q).distinct()
            values = {spec.key: self._aggregate_metric(bucket, spec, mode) for spec, mode in metrics}
            out.append(((label_a, label_b), values))
        return out

    def _aggregate_metric(self, qs: QuerySet, spec, mode: str) -> float:
        if self._metric_uses_split_equal(spec, mode):
            return _split_equal_total(
                qs,
                spec,
                on_truncated=self._note_truncation,
                consume_work=self._consume_aggregate_work,
            )
        if not self._consume_aggregate_work(1):
            return 0.0
        # Count metrics must use DISTINCT because the Issue queryset can carry
        # joins that duplicate rows; drill-down already does this (§37).
        use_distinct = spec.predicate is not None or spec.aggregation == "count"
        return float(metrics_module.aggregate(qs, spec, distinct=use_distinct))

    def _resolve_metric_allocation(self, metric: Dict[str, Any], query_default: str = "") -> str:
        spec = metrics_module.REGISTRY[metric["key"]]
        requested = metric.get("allocation") or query_default
        if not requested:
            return spec.default_allocation
        if requested not in allocation_module.VALID_ALLOCATIONS:
            raise ValueError(f"Unknown allocation: {requested!r}")
        if requested == allocation_module.ALLOCATION_SPLIT_EQUAL and not spec.supports_split_equal:
            raise ValueError(f"Metric {metric['key']!r} does not support split_equal allocation")
        return requested

    def _materialise_cells(self, query: AnalyticsQueryV2, rows) -> List[Tuple[object, object, float]]:
        """Flatten aggregate rows into ``(group, series, primary_metric_value)``.

        The primary metric is the first one in the query. ``group`` is the
        primary dimension value (or ``"-"`` when there are no dimensions) and
        ``series`` is the secondary dimension value (or ``"-"`` for one
        dimension). This matches what the chart/table renderer expects.
        """
        cells: List[Tuple[object, object, float]] = []
        metric_key = query.metrics[0]["key"]
        for keys, values in rows:
            group = self._stringify(keys[0]) if len(keys) >= 1 else "-"
            series = self._stringify(keys[1]) if len(keys) >= 2 else "-"
            cells.append((group, series, float(values.get(metric_key, 0.0))))
        return cells

    @staticmethod
    def _stringify(value):
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _format_data(self, query: AnalyticsQueryV2, normalised: List[Cell]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        unit = _unit_for_metric(query.metrics[0]["key"]) if query.metrics else ""
        for cell in normalised:
            entry: Dict[str, Any] = {
                "group": cell.group,
                "series": cell.series,
                "value": cell.value,
                "percentage": cell.percentage,
            }
            if query.display != "value":
                entry["display"] = format_display(cell, query.display, unit=unit)
            out.append(entry)
        return out

    def _compute_totals(self, rows) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for _, values in rows:
            for k, v in values.items():
                totals[k] = totals.get(k, 0.0) + float(v)
        return totals

    def _build_warnings(self, query: AnalyticsQueryV2, normalised: List[Cell]) -> List[Dict[str, Any]]:
        warnings: List[Dict[str, Any]] = []
        # §16: warn if normalisation by a multi-valued dimension could exceed 100%.
        dims = query.dimensions
        if query.normalization in ("series_total", "group_total") and any(
            dimensions_module.REGISTRY[d["key"]].multi_valued for d in dims
        ):
            warnings.append(
                {
                    "code": "MULTI_MEMBERSHIP_PCT",
                    "message": "Work items can belong to multiple values in this dimension. Shares across groups may exceed 100%.",
                }
            )
        return warnings

    def _comparison_block(
        self, query: AnalyticsQueryV2, base_qs: QuerySet, scope: ResolvedTimeScope
    ) -> Dict[str, Any]:
        ctype = query.comparison.get("type") or "none"
        cmp = resolve_comparison(scope, ctype)
        if cmp is None:
            return {"type": "none"}

        previous_qs = filters_module.apply_structured_filters(base_qs, query.filters)
        previous_qs = apply_time_basis(previous_qs, query.time.get("basis") or "created_at", cmp.previous)
        prev_rows = self._aggregate(query, previous_qs)
        prev_cells = self._materialise_cells(query, prev_rows)
        prev_total = sum(v for _, _, v in prev_cells)

        cur_total = self._compute_totals(self._aggregate(query, base_qs))[
            query.metrics[0]["key"]
        ]

        delta = cur_total - prev_total
        pct_change = (delta / prev_total) if prev_total else None

        return {
            "type": ctype,
            "start": cmp.previous.start.isoformat(),
            "end": cmp.previous.end.isoformat(),
            "current_total": cur_total,
            "previous_total": prev_total,
            "delta": delta,
            "percentage_change": pct_change,
        }

    def _sort_and_cap(self, rows, query: AnalyticsQueryV2) -> List[Tuple[Tuple[object, ...], Dict[str, float]]]:
        # Sort by primary metric desc by default. Honour ``sort`` if present.
        sort = query.sort or [{"metric": query.metrics[0]["key"], "direction": "desc"}]
        primary_metric = query.metrics[0]["key"]
        reverse = bool(sort and sort[0].get("direction", "desc") == "desc")
        rows.sort(key=lambda r: r[1].get(primary_metric, 0.0), reverse=reverse)
        return rows[: query.limit]

    def _metric_value_for_drilldown(self, qs: QuerySet, spec, mode: str) -> float:
        # For split_equal the per-issue contribution is divided by the number
        # of active assignees on that issue. The simplest correct model is to
        # sum per-issue contribution via ORM arithmetic.
        if (
            spec.key in {"work_item_count", "estimate_points"}
            and mode == allocation_module.ALLOCATION_SPLIT_EQUAL
        ):
            return _split_equal_total(qs, spec, on_truncated=self._note_truncation)
        return float(metrics_module.aggregate(qs, spec, distinct=True))


# ----- helpers ------------------------------------------------------------


def _split_equal_total(
    qs: QuerySet,
    spec,
    *,
    on_truncated=None,
    consume_work=None,
    work_per_issue: int = SPLIT_EQUAL_WORK_PER_ISSUE,
) -> float:
    """Return the sum of split-equal contributions for the queryset.

    Issue-level iteration is capped (§40.1) so bucket loops cannot amplify N+1
    scans without bound. When ``consume_work`` is provided, each issue also
    debits the shared aggregate work budget.
    """
    from plane.db.models import IssueAssignee

    total = 0.0
    issue_ids = list(
        qs.distinct()
        .order_by("id")
        .values_list("id", flat=True)[: MAX_SPLIT_EQUAL_ISSUES + 1]
    )
    per_bucket_cap_hit = len(issue_ids) > MAX_SPLIT_EQUAL_ISSUES
    if per_bucket_cap_hit:
        issue_ids = issue_ids[:MAX_SPLIT_EQUAL_ISSUES]
    budget_exhausted = False
    for issue_id in issue_ids:
        if consume_work is not None and not consume_work(work_per_issue):
            budget_exhausted = True
            break
        active_assignees = IssueAssignee.objects.filter(
            issue_id=issue_id, deleted_at__isnull=True
        ).count()
        if active_assignees <= 1:
            total += float(
                metrics_module.aggregate(qs.filter(id=issue_id), spec, distinct=True)
            )
            continue
        issue_qs = qs.filter(id=issue_id)
        raw = float(metrics_module.aggregate(issue_qs, spec, distinct=True))
        total += raw / active_assignees
    if per_bucket_cap_hit and on_truncated is not None:
        on_truncated()
    elif budget_exhausted and on_truncated is not None and consume_work is None:
        on_truncated()
    return total


def _unit_for_metric(key: str) -> str:
    if key in {"estimate_points", "allocated_estimate_points"}:
        return " pts"
    if key == "work_item_count":
        return ""
    return ""


def _echo_query(query: AnalyticsQueryV2) -> Dict[str, Any]:
    return {
        "version": query.version,
        "source": query.source,
        "project_ids": list(query.project_ids),
        "metrics": list(query.metrics),
        "dimensions": list(query.dimensions),
        "filters": dict(query.filters),
        "time": dict(query.time),
        "comparison": dict(query.comparison),
        "normalization": query.normalization,
        "display": query.display,
        "allocation": query.allocation,
        "sort": list(query.sort),
        "limit": query.limit,
    }