# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Compose Analytics V2 queries from dashboard + widget config (spec §26, §32.3)."""

from __future__ import annotations

import csv
import io
from copy import deepcopy
from typing import Any, Dict, List, Optional

from plane.analytics.v2.acl import visible_project_ids
from plane.analytics.v2.query import AnalyticsQueryV2, AnalyticsResponseV2
from plane.analytics.v2.serializer import serialise_response
from plane.db.models import Dashboard, DashboardProject, DashboardWidget

VIEWER_FILTER_TOKENS = frozenset({"current_user", "@current_user"})


def _principal_id(principal) -> str:
    return str(getattr(principal, "id", principal))


def resolve_viewer_filter_placeholders(
    filters: Optional[Dict[str, Any]], principal
) -> Dict[str, Any]:
    """Replace dynamic viewer tokens in widget filters (spec §22)."""
    if not filters:
        return {}
    pid = _principal_id(principal)
    out: Dict[str, Any] = {}
    for key, raw in filters.items():
        if raw is None:
            continue
        if isinstance(raw, (list, tuple)):
            out[key] = [
                pid if token in VIEWER_FILTER_TOKENS else token for token in raw
            ]
        elif raw in VIEWER_FILTER_TOKENS:
            out[key] = pid
        else:
            out[key] = raw
    return out


def intersect_structured_filters(
    left: Optional[Dict[str, Any]],
    right: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Intersect two structured filter dicts key-wise (spec §26 / §50.13)."""
    left = left or {}
    right = right or {}
    if not left:
        return dict(right)
    if not right:
        return dict(left)

    out: Dict[str, Any] = {}
    all_keys = set(left.keys()) | set(right.keys())
    for key in all_keys:
        lv = left.get(key)
        rv = right.get(key)
        if lv is None:
            out[key] = rv
            continue
        if rv is None:
            out[key] = lv
            continue
        l_list = lv if isinstance(lv, (list, tuple)) else [lv]
        r_list = rv if isinstance(rv, (list, tuple)) else [rv]
        intersection = [v for v in l_list if v in r_list]
        if intersection:
            out[key] = intersection
    return out


def dashboard_source_project_ids(dashboard: Dashboard) -> List[str]:
    return [
        str(pid)
        for pid in DashboardProject.objects.filter(
            dashboard=dashboard,
            deleted_at__isnull=True,
        ).values_list("project_id", flat=True)
    ]


def resolve_scoped_project_ids(
    dashboard: Dashboard,
    *,
    workspace,
    principal,
) -> List[str]:
    configured = dashboard_source_project_ids(dashboard)
    return visible_project_ids(
        workspace=workspace,
        principal=principal,
        project_ids=configured or None,
    )


def _widget_query_body(widget: DashboardWidget) -> Dict[str, Any]:
    config = widget.query_config or {}
    if isinstance(config.get("query"), dict):
        return deepcopy(config["query"])
    body = deepcopy(config)
    body.pop("schema_version", None)
    return body


def compose_widget_query_payload(
    dashboard: Dashboard,
    widget: DashboardWidget,
    *,
    workspace,
    principal,
) -> Dict[str, Any]:
    """Build an Analytics V2 payload for ``widget`` under ``dashboard``."""
    payload = _widget_query_body(widget)
    payload["project_ids"] = resolve_scoped_project_ids(
        dashboard, workspace=workspace, principal=principal
    )

    widget_filters = payload.pop("filters", {}) or {}
    if isinstance(widget.query_config, dict) and widget.query_config.get("filters"):
        widget_filters = intersect_structured_filters(
            widget_filters, widget.query_config.get("filters")
        )
    widget_filters = resolve_viewer_filter_placeholders(widget_filters, principal)

    payload["filters"] = intersect_structured_filters(dashboard.filters, widget_filters)

    if widget.inherit_time_scope:
        if dashboard.default_time_scope:
            payload["time"] = deepcopy(dashboard.default_time_scope)
    elif widget.custom_time_scope:
        payload["time"] = deepcopy(widget.custom_time_scope)
    elif dashboard.default_time_scope and "time" not in payload:
        payload["time"] = deepcopy(dashboard.default_time_scope)

    if dashboard.comparison and "comparison" not in payload:
        payload["comparison"] = deepcopy(dashboard.comparison)

    return payload


def execute_widget_query(
    dashboard: Dashboard,
    widget: DashboardWidget,
    *,
    workspace,
    principal,
    engine,
) -> AnalyticsResponseV2:
    from plane.analytics.v2 import AnalyticsEngineV2

    if engine is None:
        engine = AnalyticsEngineV2(workspace=workspace, principal=principal)
    payload = compose_widget_query_payload(
        dashboard, widget, workspace=workspace, principal=principal
    )
    query = AnalyticsQueryV2.from_payload(payload)
    return engine.execute(query)


def analytics_response_to_csv(response: AnalyticsResponseV2) -> str:
    """Serialize aggregate ``data`` rows to CSV (spec §30.1)."""
    serialised = serialise_response(response)
    rows = serialised.get("data") or []
    if not rows:
        buffer = io.StringIO()
        buffer.write("group,value\n")
        return buffer.getvalue()

    has_pct = any(entry.get("percentage") is not None for entry in rows)
    fieldnames = ["group", "value"]
    if has_pct:
        fieldnames.append("percentage")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for entry in rows:
        row = {
            "group": entry.get("group"),
            "value": entry.get("value"),
        }
        if has_pct:
            row["percentage"] = entry.get("percentage")
        writer.writerow(row)
    return buffer.getvalue()
