# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Compose Analytics V2 queries from dashboard + widget config (spec §26, §32.3)."""

from __future__ import annotations

import csv
import io
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from plane.analytics.v2.acl import visible_project_ids
from plane.analytics.v2.query import AnalyticsQueryV2, AnalyticsResponseV2
from plane.analytics.v2.serializer import serialise_response
from plane.db.models import Dashboard, DashboardProject, DashboardWidget

VIEWER_FILTER_TOKENS = frozenset({"current_user", "@current_user"})
PROJECT_SCOPE_KEYS = frozenset({"project_id", "project_ids", "project"})


def _is_uuid_string(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _viewer_accessible_project_id_set(*, workspace, principal) -> Set[str]:
    return set(visible_project_ids(workspace=workspace, principal=principal))


def _inaccessible_workspace_project_ids(*, workspace, principal) -> Set[str]:
    from plane.db.models import Project

    all_ids = {
        str(pid)
        for pid in Project.objects.filter(
            workspace_id=workspace.id, deleted_at__isnull=True
        ).values_list("id", flat=True)
    }
    return all_ids - _viewer_accessible_project_id_set(
        workspace=workspace, principal=principal
    )


def filter_project_scope_value(value: Any, accessible: Set[str]) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item) in accessible]
    if isinstance(value, str):
        return value if value in accessible else None
    return value


def redact_json_metadata(
    value: Any,
    *,
    accessible: Set[str],
    hidden: Set[str],
) -> Any:
    """Drop project identifiers the viewer cannot access (spec §28.3)."""
    if value is None:
        return None
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, raw in value.items():
            if key in PROJECT_SCOPE_KEYS:
                filtered = filter_project_scope_value(raw, accessible)
                if filtered not in (None, [], {}):
                    out[key] = filtered
                continue
            child = redact_json_metadata(raw, accessible=accessible, hidden=hidden)
            if child not in (None, [], {}):
                out[key] = child
        return out
    if isinstance(value, list):
        if value and all(_is_uuid_string(item) for item in value):
            return [str(item) for item in value if str(item) in accessible]
        return [
            redact_json_metadata(item, accessible=accessible, hidden=hidden)
            for item in value
        ]
    if isinstance(value, str) and value in hidden:
        return None
    return value


def redact_pql_for_viewer(pql: Optional[str], hidden: Set[str]) -> Optional[str]:
    if not pql:
        return pql
    for project_id in hidden:
        if project_id in pql:
            return None
    return pql


def viewer_dashboard_project_scope(
    dashboard: Dashboard,
    *,
    principal,
) -> Tuple[Set[str], Set[str]]:
    accessible = set(
        resolve_scoped_project_ids(
            dashboard, workspace=dashboard.workspace, principal=principal
        )
    )
    hidden = _inaccessible_workspace_project_ids(
        workspace=dashboard.workspace, principal=principal
    )
    return accessible, hidden


def _redact_query_body_for_viewer(
    body: Dict[str, Any],
    *,
    accessible: Set[str],
    hidden: Set[str],
    scoped_project_ids: List[str],
) -> None:
    """Apply read-side ACL to a widget query body (flat or nested under query_config.query)."""
    body["project_ids"] = scoped_project_ids
    if not hidden:
        return
    if "filters" in body:
        body["filters"] = (
            redact_json_metadata(
                body.get("filters"), accessible=accessible, hidden=hidden
            )
            or {}
        )
    if body.get("pql"):
        body["pql"] = redact_pql_for_viewer(body.get("pql"), hidden)


def redact_widget_query_config_for_viewer(
    query_config: Optional[Dict[str, Any]],
    *,
    dashboard: Dashboard,
    workspace,
    principal,
) -> Dict[str, Any]:
    config = deepcopy(query_config or {})
    accessible, hidden = viewer_dashboard_project_scope(dashboard, principal=principal)
    scoped_project_ids = resolve_scoped_project_ids(
        dashboard, workspace=workspace, principal=principal
    )
    _redact_query_body_for_viewer(
        config,
        accessible=accessible,
        hidden=hidden,
        scoped_project_ids=scoped_project_ids,
    )
    nested = config.get("query")
    if isinstance(nested, dict):
        _redact_query_body_for_viewer(
            nested,
            accessible=accessible,
            hidden=hidden,
            scoped_project_ids=scoped_project_ids,
        )
    return config


def redact_dashboard_representation_for_viewer(
    representation: Dict[str, Any],
    *,
    dashboard: Dashboard,
    principal,
) -> Dict[str, Any]:
    """Read-side ACL on dashboard metadata (spec §28.3)."""
    accessible, hidden = viewer_dashboard_project_scope(dashboard, principal=principal)
    representation["projects"] = sorted(accessible)
    if not hidden:
        return representation

    representation["filters"] = (
        redact_json_metadata(
            representation.get("filters"), accessible=accessible, hidden=hidden
        )
        or {}
    )
    representation["pql"] = redact_pql_for_viewer(representation.get("pql"), hidden)
    representation["default_time_scope"] = (
        redact_json_metadata(
            representation.get("default_time_scope"),
            accessible=accessible,
            hidden=hidden,
        )
        or {}
    )
    representation["comparison"] = (
        redact_json_metadata(
            representation.get("comparison"), accessible=accessible, hidden=hidden
        )
        or {}
    )
    for widget in representation.get("widgets") or []:
        widget["query_config"] = redact_widget_query_config_for_viewer(
            widget.get("query_config"),
            dashboard=dashboard,
            workspace=dashboard.workspace,
            principal=principal,
        )
    return representation


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

    scoped_ids = payload["project_ids"]
    accessible = set(scoped_ids)
    hidden = _inaccessible_workspace_project_ids(workspace=workspace, principal=principal)
    payload["filters"] = intersect_structured_filters(dashboard.filters, widget_filters)
    payload["filters"] = (
        redact_json_metadata(payload["filters"], accessible=accessible, hidden=hidden)
        or {}
    )
    if payload.get("pql"):
        payload["pql"] = redact_pql_for_viewer(payload.get("pql"), hidden)

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
