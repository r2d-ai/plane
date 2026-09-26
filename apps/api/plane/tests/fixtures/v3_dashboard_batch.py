# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Canonical v3 workspace dashboard batch payload (spec §7 + §8).

Used by contract tests (RD-480), unit card snapshots (Phase A), and perf
benchmarks. ``batch-composer.ts`` (Phase C.6) should produce the same shape:
``{"queries": [<AnalyticsQueryV2 with key>, ...]}`` with global scope merged
into each entry's ``filters`` / shared ``time`` fields — not a separate batch row.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from plane.analytics.v2.normalization import (
    DISPLAY_VALUE_AND_PCT,
    NORMALIZATION_GRAND_TOTAL,
    NORMALIZATION_GROUP_TOTAL,
)
from plane.analytics.v2.query import MAX_BATCH_QUERIES

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
    "L": {
        "metrics": [{"key": "work_item_count"}],
        "filters": {"priority": ["urgent"]},
        "time": {"preset": "none"},
    },
}

V3_CARD_IDS: Sequence[str] = tuple(SECTION_7_CARD_QUERIES.keys())


def warm_app_urlconf_for_freezegun() -> None:
    """Load URLConf before freezegun (OpenAI import uses pydantic v1 ``date``)."""
    import plane.app.urls  # noqa: F401


# Default global scope (§8): project/member/label filters merged into each card
# query. Global time range is applied per card by the composer (§8.2); defaults
# here only carry filter dimensions for the batch contract.
V3_DEFAULT_GLOBAL_SCOPE: Dict[str, Any] = {
    "filters": {},
}


def _merge_filters(
    global_filters: Mapping[str, Any], card_filters: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    merged = dict(global_filters or {})
    for key, value in (card_filters or {}).items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = sorted(set(merged[key]) | set(value))
        else:
            merged[key] = value
    return merged


def build_v3_card_query(
    card_id: str,
    *,
    global_scope: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """One batch entry for card ``card_id`` with global scope merged."""
    if card_id not in SECTION_7_CARD_QUERIES:
        raise KeyError(f"Unknown card id {card_id!r}")
    scope = dict(global_scope or V3_DEFAULT_GLOBAL_SCOPE)
    body = deepcopy(SECTION_7_CARD_QUERIES[card_id])
    global_filters = scope.get("filters") or {}
    body["filters"] = _merge_filters(global_filters, body.get("filters"))
    return {
        "key": f"card-{card_id}",
        "version": 1,
        "source": "work_items",
        **body,
    }


def build_v3_dashboard_batch_payload(
    *,
    global_scope: Optional[Mapping[str, Any]] = None,
    card_ids: Sequence[str] = V3_CARD_IDS,
    project_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Full POST body for ``POST .../analytics/v2/batch/``."""
    scope = dict(global_scope or V3_DEFAULT_GLOBAL_SCOPE)
    if project_ids:
        filters = dict(scope.get("filters") or {})
        filters["project_id"] = [str(pid) for pid in project_ids]
        scope["filters"] = filters
    queries = [build_v3_card_query(card_id, global_scope=scope) for card_id in card_ids]
    return {"queries": queries}


V3_DASHBOARD_CARD_COUNT = len(V3_CARD_IDS)

# Headroom: 12 cards + up to 8 concurrent drill-down refetches stay under the cap.
V3_MAX_DRILLDOWN_REFETCHES_UNDER_CAP = MAX_BATCH_QUERIES - V3_DASHBOARD_CARD_COUNT

assert V3_DASHBOARD_CARD_COUNT <= MAX_BATCH_QUERIES
assert V3_DASHBOARD_CARD_COUNT + V3_MAX_DRILLDOWN_REFETCHES_UNDER_CAP == MAX_BATCH_QUERIES


def v3_batch_response_contract_keys() -> Dict[str, Any]:
    """Document the response envelope for PR / frontend (batch-composer.ts)."""
    return {
        "workspace_slug": "<slug>",
        "results": [
            {
                "key": "card-A",
                "status": "ok",
                "data": {
                    "data": [],
                    "totals": {},
                    "warnings": [],
                },
            },
            {
                "key": "card-X",
                "status": "error",
                "error": {"code": "INVALID_QUERY", "message": "Invalid query"},
            },
        ],
    }
