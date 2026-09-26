# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Analytics Engine V2 endpoints (spec §32, §44.2).

The legacy ``advance-analytics`` endpoints are unchanged. V2 lives alongside
them with its own URL prefix ``/api/workspaces/{slug}/analytics/v2/``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.query import MAX_BATCH_QUERIES
from plane.analytics.v2.drilldown import DrilldownSelection
from plane.analytics.v2.serializer import serialise_response
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace


logger = logging.getLogger("plane.analytics.v2")


def _workspace_or_400(slug: str):
    try:
        return Workspace.objects.get(slug=slug)
    except Workspace.DoesNotExist:
        return None


def _bad_request(message: str, code: str = "BAD_REQUEST", exc: Exception | None = None) -> Response:
    if exc is not None:
        logger.warning("Analytics V2 bad request: %s", code, exc_info=exc)
    return Response({"error": message, "code": code}, status=status.HTTP_400_BAD_REQUEST)


class AnalyticsV2QueryEndpoint(BaseAPIView):
    """``POST /api/workspaces/{slug}/analytics/v2/query`` — execute an
    Analytics V2 query and return the aggregate response (§32.1).
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request: Request, slug: str) -> Response:
        workspace = _workspace_or_400(slug)
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "WORKSPACE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = request.data or {}
        try:
            query = AnalyticsQueryV2.from_payload(payload)
        except (ValueError, TypeError) as exc:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY", exc=exc)

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        try:
            response = engine.execute(query)
        except ValueError as exc:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY", exc=exc)

        return Response(serialise_response(response), status=status.HTTP_200_OK)


class AnalyticsV2StatsEndpoint(BaseAPIView):
    """``POST /api/workspaces/{slug}/analytics/v2/stats`` — stats-only view
    returning totals only, useful for KPI cards and dashboards' Number widgets.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request: Request, slug: str) -> Response:
        workspace = _workspace_or_400(slug)
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "WORKSPACE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = request.data or {}
        try:
            query = AnalyticsQueryV2.from_payload(payload)
        except (ValueError, TypeError) as exc:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY", exc=exc)

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        response = engine.execute(query)

        # Stats-only payload: resolved metadata + totals + warnings.
        return Response(
            {
                "query": response.query,
                "resolved": response.resolved,
                "totals": response.totals,
                "warnings": response.warnings,
            },
            status=status.HTTP_200_OK,
        )


class AnalyticsV2ChartsEndpoint(BaseAPIView):
    """``POST /api/workspaces/{slug}/analytics/v2/charts`` — chart-shaped view
    that returns ``{labels, series}`` for direct consumption by frontend
    chart libraries.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request: Request, slug: str) -> Response:
        workspace = _workspace_or_400(slug)
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "WORKSPACE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = request.data or {}
        try:
            query = AnalyticsQueryV2.from_payload(payload)
        except (ValueError, TypeError) as exc:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY", exc=exc)

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        response = engine.execute(query)

        labels = [entry["group"] for entry in response.data]
        series = [
            {
                "metric": query.metrics[0]["key"],
                "data": [entry["value"] for entry in response.data],
                "percentages": [entry.get("percentage") for entry in response.data],
            }
        ]

        return Response(
            {
                "labels": labels,
                "series": series,
                "resolved": response.resolved,
                "warnings": response.warnings,
            },
            status=status.HTTP_200_OK,
        )


class AnalyticsV2DrilldownEndpoint(BaseAPIView):
    """``POST /api/workspaces/{slug}/analytics/v2/drilldown`` — return the
    matching raw work-item set under the same ACL scope (§32.2, §25, §37).
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request: Request, slug: str) -> Response:
        workspace = _workspace_or_400(slug)
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "WORKSPACE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = request.data or {}
        query_payload = payload.get("query") or {}
        selection_payload = payload.get("selection") or {}

        try:
            query = AnalyticsQueryV2.from_payload(query_payload)
            selection = DrilldownSelection(values=selection_payload)
        except (ValueError, TypeError) as exc:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY", exc=exc)

        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 25))

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        result = engine.drilldown(
            query=query, selection=selection, page=page, page_size=page_size
        )
        return Response(result, status=status.HTTP_200_OK)


class AnalyticsV2BatchEndpoint(BaseAPIView):
    """``POST /api/workspaces/{slug}/analytics/v2/batch`` — batched widget data
    endpoint for dashboards (§32.3).

    The payload is ``{"queries": [{...}, ...]}``; each entry resolves the same
    way ``/query`` does, but failures are isolated per entry so one broken
    widget doesn't blank the rest.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request: Request, slug: str) -> Response:
        workspace = _workspace_or_400(slug)
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "WORKSPACE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = request.data or {}
        entries = payload.get("queries") or []
        if not isinstance(entries, list):
            return _bad_request("queries must be an array", code="INVALID_QUERY")
        if len(entries) > MAX_BATCH_QUERIES:
            return _bad_request("Invalid query payload.", code="INVALID_QUERY")

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        out: Dict[str, Any] = {"workspace_slug": slug, "results": []}
        for index, entry in enumerate(entries):
            key = str(entry.get("key") or index)
            try:
                query = AnalyticsQueryV2.from_payload(entry)
                response = engine.execute(query)
                out["results"].append(
                    {
                        "key": key,
                        "status": "ok",
                        "data": serialise_response(response),
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.exception("analytics_v2 batch failure: %s", exc)
                out["results"].append(
                    {
                        "key": key,
                        "status": "error",
                        "error": {"code": "INVALID_QUERY", "message": "Invalid query"},
                    }
                )
            except Exception as exc:  # pragma: no cover — defensive guard
                logger.exception("analytics_v2 unexpected failure: %s", exc)
                out["results"].append(
                    {
                        "key": key,
                        "status": "error",
                        "error": {"code": "ENGINE_FAILURE", "message": "Internal error"},
                    }
                )
        return Response(out, status=status.HTTP_200_OK)