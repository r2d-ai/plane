# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace dashboard CRUD and data endpoints (spec §33, §32.3, §30.1).

FROZEN — do not extend: legacy dashboard *builder* API scheduled for deletion in
Phase E (RD-475). Do not add endpoints, models, or behaviour here; pin changes in
Analytics V2 tests and the fixed workspace dashboard instead.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from plane.analytics.v2 import AnalyticsEngineV2, AnalyticsQueryV2
from plane.analytics.v2.query import MAX_BATCH_QUERIES
from plane.analytics.v2.drilldown import DrilldownSelection
from plane.analytics.v2.serializer import serialise_response
from plane.app.permissions.dashboard import DashboardPermission
from plane.app.serializers.dashboard import (
    DashboardMemberAccessSerializer,
    DashboardSerializer,
    DashboardWidgetSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.db.models import (
    Dashboard,
    DashboardFavorite,
    DashboardMemberAccess,
    DashboardProject,
    DashboardWidget,
    Project,
    Workspace,
)
from plane.utils.dashboard_analytics import (
    analytics_response_to_csv,
    compose_widget_query_payload,
    execute_widget_query,
)
from plane.utils.page_access import resolve_workspace_role

logger = logging.getLogger("plane.dashboards")


def _workspace(slug: str) -> Optional[Workspace]:
    return Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()


def _role(workspace: Workspace, user) -> Optional[int]:
    return resolve_workspace_role(workspace.id, user.id)


def _visible_dashboards(workspace: Workspace, user) -> Dashboard:
    role = _role(workspace, user)
    if role is None:
        return Dashboard.objects.none()

    qs = Dashboard.objects.filter(workspace=workspace, deleted_at__isnull=True)
    if role >= 20:
        return qs

    return qs.filter(
        Q(owner_id=user.id)
        | Q(visibility=Dashboard.VISIBILITY_WORKSPACE)
        | Q(
            member_access__member_id=user.id,
            member_access__deleted_at__isnull=True,
        )
    ).distinct()


def _get_dashboard(
    workspace: Workspace,
    dashboard_id,
    user,
    *,
    require_view: bool = True,
) -> Optional[Dashboard]:
    dashboard = Dashboard.objects.filter(
        id=dashboard_id,
        workspace=workspace,
        deleted_at__isnull=True,
    ).first()
    if dashboard is None:
        return None
    if require_view and not dashboard.can_view(user, workspace_role=_role(workspace, user)):
        return None
    return dashboard


def _sync_projects(dashboard: Dashboard, project_ids: List[str], workspace: Workspace):
    DashboardProject.objects.filter(dashboard=dashboard, deleted_at__isnull=True).exclude(
        project_id__in=project_ids
    ).update(deleted_at=timezone.now())

    existing = set(
        str(pid)
        for pid in DashboardProject.objects.filter(
            dashboard=dashboard, deleted_at__isnull=True
        ).values_list("project_id", flat=True)
    )
    valid = set(
        str(pid)
        for pid in Project.objects.filter(
            workspace=workspace, id__in=project_ids, deleted_at__isnull=True
        ).values_list("id", flat=True)
    )
    for pid in valid:
        if pid in existing:
            continue
        prior = DashboardProject.all_objects.filter(
            dashboard=dashboard, project_id=pid
        ).first()
        if prior is not None and prior.deleted_at is not None:
            prior.deleted_at = None
            prior.save(update_fields=["deleted_at"])
        elif prior is None:
            DashboardProject.objects.create(dashboard=dashboard, project_id=pid)


class DashboardMixin:
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    permission_classes = [DashboardPermission]

    def initial(self, request, *args, **kwargs):
        if not settings.WORKSPACE_DASHBOARDS:
            raise NotFound()
        return super().initial(request, *args, **kwargs)

    def _not_found(self):
        return Response(status=status.HTTP_404_NOT_FOUND)


class DashboardListCreateEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "list"

    def get(self, request: Request, slug: str) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboards = _visible_dashboards(workspace, request.user).order_by("-created_at")
        data = DashboardSerializer(
            dashboards, many=True, context={"request": request}
        ).data
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request: Request, slug: str) -> Response:
        self.action = "create"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()

        serializer = DashboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_ids = serializer.validated_data.pop("project_ids", [])

        with transaction.atomic():
            dashboard = Dashboard.objects.create(
                workspace=workspace,
                owner=request.user,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                visibility=serializer.validated_data.get(
                    "visibility", Dashboard.VISIBILITY_PRIVATE
                ),
                filters=serializer.validated_data.get("filters") or {},
                pql=serializer.validated_data.get("pql"),
                default_time_scope=serializer.validated_data.get("default_time_scope") or {},
                comparison=serializer.validated_data.get("comparison") or {},
            )
            if project_ids:
                _sync_projects(dashboard, [str(p) for p in project_ids], workspace)

        return Response(
            DashboardSerializer(dashboard, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardDetailEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def get(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "retrieve"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        return Response(
            DashboardSerializer(dashboard, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "partial_update"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        role = _role(workspace, request.user)
        if not dashboard.can_edit(request.user, workspace_role=role):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = DashboardSerializer(dashboard, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        project_ids = serializer.validated_data.pop("project_ids", None)

        if "visibility" in serializer.validated_data and not dashboard.can_manage(
            request.user
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        for field, value in serializer.validated_data.items():
            setattr(dashboard, field, value)
        dashboard.save()

        if project_ids is not None:
            _sync_projects(dashboard, [str(p) for p in project_ids], workspace)

        return Response(
            DashboardSerializer(dashboard, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "destroy"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_manage(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        dashboard.delete(soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardDuplicateEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "duplicate"

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        source = _get_dashboard(workspace, dashboard_id, request.user)
        if source is None:
            return self._not_found()

        with transaction.atomic():
            clone = Dashboard.objects.create(
                workspace=workspace,
                owner=request.user,
                name=f"{source.name} (Copy)",
                description=source.description,
                visibility=Dashboard.VISIBILITY_PRIVATE,
                filters=deepcopy(source.filters),
                pql=source.pql,
                default_time_scope=deepcopy(source.default_time_scope),
                comparison=deepcopy(source.comparison),
            )
            for dp in DashboardProject.objects.filter(
                dashboard=source, deleted_at__isnull=True
            ):
                DashboardProject.objects.create(dashboard=clone, project_id=dp.project_id)
            for widget in DashboardWidget.objects.filter(
                dashboard=source, deleted_at__isnull=True
            ):
                DashboardWidget.objects.create(
                    dashboard=clone,
                    title=widget.title,
                    description=widget.description,
                    widget_type=widget.widget_type,
                    widget_model=widget.widget_model,
                    query_config=deepcopy(widget.query_config),
                    style_config=deepcopy(widget.style_config),
                    layout_config=deepcopy(widget.layout_config),
                    inherit_time_scope=widget.inherit_time_scope,
                    custom_time_scope=deepcopy(widget.custom_time_scope)
                    if widget.custom_time_scope
                    else None,
                    sort_order=widget.sort_order,
                )

        return Response(
            DashboardSerializer(clone, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardWidgetListCreateEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "widget_create"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_edit(request.user, workspace_role=_role(workspace, request.user)):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = DashboardWidgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        widget = DashboardWidget.objects.create(
            dashboard=dashboard, **serializer.validated_data
        )
        return Response(
            DashboardWidgetSerializer(widget, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardWidgetDetailEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def _widget(self, dashboard, widget_id):
        return DashboardWidget.objects.filter(
            id=widget_id,
            dashboard=dashboard,
            deleted_at__isnull=True,
        ).first()

    def patch(self, request: Request, slug: str, dashboard_id, widget_id) -> Response:
        self.action = "widget_update"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_edit(request.user, workspace_role=_role(workspace, request.user)):
            return Response(status=status.HTTP_403_FORBIDDEN)
        widget = self._widget(dashboard, widget_id)
        if widget is None:
            return self._not_found()

        serializer = DashboardWidgetSerializer(widget, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(widget, field, value)
        widget.save()
        return Response(
            DashboardWidgetSerializer(widget, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, slug: str, dashboard_id, widget_id) -> Response:
        self.action = "widget_destroy"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_edit(request.user, workspace_role=_role(workspace, request.user)):
            return Response(status=status.HTTP_403_FORBIDDEN)
        widget = self._widget(dashboard, widget_id)
        if widget is None:
            return self._not_found()
        widget.delete(soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardLayoutEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "layout"

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_edit(request.user, workspace_role=_role(workspace, request.user)):
            return Response(status=status.HTTP_403_FORBIDDEN)

        entries = request.data.get("widgets") or []
        if not isinstance(entries, list):
            return Response(
                {"error": "widgets must be an array"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for entry in entries:
                widget_id = entry.get("id")
                widget = DashboardWidget.objects.filter(
                    id=widget_id,
                    dashboard=dashboard,
                    deleted_at__isnull=True,
                ).first()
                if widget is None:
                    continue
                if "layout_config" in entry:
                    widget.layout_config = entry["layout_config"]
                if "sort_order" in entry:
                    widget.sort_order = entry["sort_order"]
                widget.save()

        widgets = DashboardWidget.objects.filter(
            dashboard=dashboard, deleted_at__isnull=True
        ).order_by("sort_order")
        return Response(
            DashboardWidgetSerializer(
                widgets, many=True, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )


class DashboardFavoriteEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "favorite"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()

        fav = DashboardFavorite.all_objects.filter(
            dashboard=dashboard, member=request.user
        ).first()
        if fav is None:
            DashboardFavorite.objects.create(dashboard=dashboard, member=request.user)
        elif fav.deleted_at is not None:
            fav.deleted_at = None
            fav.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "unfavorite"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()

        DashboardFavorite.objects.filter(
            dashboard=dashboard,
            member=request.user,
            deleted_at__isnull=True,
        ).update(deleted_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardMemberListCreateEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def get(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "members"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_manage(request.user) and dashboard.owner_id != request.user.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        rows = DashboardMemberAccess.objects.filter(
            dashboard=dashboard, deleted_at__isnull=True
        )
        return Response(
            DashboardMemberAccessSerializer(rows, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        self.action = "member_add"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        if not dashboard.can_manage(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = DashboardMemberAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.validated_data["member"]
        member_id = member.id if hasattr(member, "id") else member
        row = DashboardMemberAccess.objects.create(
            dashboard=dashboard,
            member_id=member_id,
            access=serializer.validated_data.get(
                "access", DashboardMemberAccess.ACCESS_VIEW
            ),
        )
        return Response(
            DashboardMemberAccessSerializer(row).data, status=status.HTTP_201_CREATED
        )


class DashboardMemberDetailEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    def patch(self, request: Request, slug: str, dashboard_id, member_id) -> Response:
        self.action = "member_update"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None or not dashboard.can_manage(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        row = DashboardMemberAccess.objects.filter(
            id=member_id, dashboard=dashboard, deleted_at__isnull=True
        ).first()
        if row is None:
            return self._not_found()

        serializer = DashboardMemberAccessSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row.access = serializer.validated_data.get("access", row.access)
        row.save()
        return Response(DashboardMemberAccessSerializer(row).data, status=status.HTTP_200_OK)

    def delete(self, request: Request, slug: str, dashboard_id, member_id) -> Response:
        self.action = "member_remove"
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None or not dashboard.can_manage(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)

        row = DashboardMemberAccess.objects.filter(
            id=member_id, dashboard=dashboard, deleted_at__isnull=True
        ).first()
        if row is None:
            return self._not_found()
        row.delete(soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardDataEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "data"

    def post(self, request: Request, slug: str, dashboard_id) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()

        widget_count = DashboardWidget.objects.filter(
            dashboard=dashboard, deleted_at__isnull=True
        ).count()
        if widget_count > MAX_BATCH_QUERIES:
            return Response(
                {"error": "Invalid query", "code": "INVALID_QUERY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        widgets = DashboardWidget.objects.filter(
            dashboard=dashboard, deleted_at__isnull=True
        ).order_by("sort_order")

        resolved_time = dashboard.default_time_scope or {}
        out_widgets: Dict[str, Any] = {}

        for widget in widgets:
            key = str(widget.id)
            try:
                response = execute_widget_query(
                    dashboard,
                    widget,
                    workspace=workspace,
                    principal=request.user,
                    engine=engine,
                )
                out_widgets[key] = {
                    "status": "ok",
                    "data": serialise_response(response),
                }
            except (ValueError, TypeError) as exc:
                logger.warning("dashboard widget query failed: %s", exc)
                out_widgets[key] = {
                    "status": "error",
                    "error": {"code": "INVALID_QUERY", "message": "Invalid query"},
                }
            except Exception as exc:  # pragma: no cover
                logger.exception("dashboard widget unexpected failure: %s", exc)
                out_widgets[key] = {
                    "status": "error",
                    "error": {"code": "ENGINE_FAILURE", "message": "Internal error"},
                }

        return Response(
            {
                "dashboard_id": str(dashboard.id),
                "resolved_time": resolved_time,
                "widgets": out_widgets,
            },
            status=status.HTTP_200_OK,
        )


class DashboardWidgetDrilldownEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "drilldown"

    def post(self, request: Request, slug: str, dashboard_id, widget_id) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        widget = DashboardWidget.objects.filter(
            id=widget_id, dashboard=dashboard, deleted_at__isnull=True
        ).first()
        if widget is None:
            return self._not_found()

        payload = request.data or {}
        selection_payload = payload.get("selection") or {}
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 25))

        query_payload = compose_widget_query_payload(
            dashboard, widget, workspace=workspace, principal=request.user
        )
        try:
            query = AnalyticsQueryV2.from_payload(query_payload)
            selection = DrilldownSelection(values=selection_payload)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid query", "code": "INVALID_QUERY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engine = AnalyticsEngineV2(workspace=workspace, principal=request.user)
        result = engine.drilldown(
            query=query, selection=selection, page=page, page_size=page_size
        )
        return Response(result, status=status.HTTP_200_OK)


class DashboardWidgetExportEndpoint(DashboardMixin, BaseAPIView):
    """FROZEN — do not extend (legacy dashboard builder; Phase E deletion)."""

    action = "export"

    def get(self, request: Request, slug: str, dashboard_id, widget_id) -> Response:
        workspace = _workspace(slug)
        if workspace is None:
            return self._not_found()
        dashboard = _get_dashboard(workspace, dashboard_id, request.user)
        if dashboard is None:
            return self._not_found()
        widget = DashboardWidget.objects.filter(
            id=widget_id, dashboard=dashboard, deleted_at__isnull=True
        ).first()
        if widget is None:
            return self._not_found()

        try:
            response = execute_widget_query(
                dashboard,
                widget,
                workspace=workspace,
                principal=request.user,
                engine=None,
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid query", "code": "INVALID_QUERY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        csv_body = analytics_response_to_csv(response)
        http_response = HttpResponse(csv_body, content_type="text/csv")
        http_response["Content-Disposition"] = (
            f'attachment; filename="{widget.title or "widget"}-export.csv"'
        )
        return http_response
