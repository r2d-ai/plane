# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Page/Collection analytics (WIKI-09b, plan §12.3).

Two endpoints surfaces:

* ``POST .../pages/<page_id>/views/`` records a counted view. A background
  preload is short-circuited before insert, so it can never inflate counts.
* ``GET  .../pages/<page_id>/analytics/`` and
  ``GET  .../page-collections/<collection_id>/analytics/`` return aggregates
  (totals, unique viewers, per-day timeline) and a CSV export.

The privacy policy is explicit and read from settings:

* ``PAGE_ANALYTICS_ENABLED`` — when false, recording is a no-op.
* ``PAGE_ANALYTICS_IDENTIFY_VIEWERS`` — when false, views are anonymous and
  viewer identities are never persisted nor returned.

Analytics data is visitor data, so every read/export is gated: page analytics by
MANAGE (page owner / admin), collection analytics by collection management
(workspace admin/owner).
"""

import csv

from datetime import date, datetime, timedelta

from django.conf import settings
from django.db.models import Count, Max, Min
from django.db.models.functions import TruncDate
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import PageCollectionPermission, WorkspacePagePermission
from plane.app.serializers import PageViewRecordSerializer
from plane.db.models import Page, PageCollection, PageView, Workspace
from plane.utils.page_access import nearest_collection

from ..base import BaseViewSet

CSV_COLUMNS = ["viewed_at", "page_id", "page_name", "collection_id", "viewer_id", "viewer_email", "viewer_name"]
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 366


def _identify_viewers():
    return bool(getattr(settings, "PAGE_ANALYTICS_IDENTIFY_VIEWERS", False))


def _analytics_enabled():
    return bool(getattr(settings, "PAGE_ANALYTICS_ENABLED", True))


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return parse_date(str(value))


def _resolve_window(params):
    """Return ``(start_date, end_date)`` clamping the requested window."""
    end = _parse_date(params.get("end")) or timezone.now().date()
    start = _parse_date(params.get("start"))
    if start is None:
        try:
            days = int(params.get("days", DEFAULT_WINDOW_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_WINDOW_DAYS
        days = max(1, min(days, MAX_WINDOW_DAYS))
        start = end - timedelta(days=days - 1)
    if start > end:
        start, end = end, start
    return start, end


def _window_queryset(queryset, start, end):
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), datetime.min.time()))
    return queryset.filter(viewed_at__gte=start_dt, viewed_at__lt=end_dt)


def _aggregate(queryset, page_id, collection_id, *, start, end):
    totals = queryset.aggregate(
        total_views=Count("id"),
        unique_viewers=Count("viewer", distinct=True),
        first_viewed_at=Min("viewed_at"),
        last_viewed_at=Max("viewed_at"),
    )
    timeline = list(
        queryset.annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(views=Count("id"))
        .order_by("day")
    )
    identify = _identify_viewers()
    viewers = []
    if identify:
        viewers = list(
            queryset.filter(viewer__isnull=False)
            .values("viewer_id", "viewer__email", "viewer__display_name")
            .annotate(views=Count("id"), last_viewed_at=Max("viewed_at"))
            .order_by("-views")
        )
    return {
        "page": str(page_id) if page_id else None,
        "collection": str(collection_id) if collection_id else None,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_views": totals["total_views"] or 0,
        "unique_viewers": (totals["unique_viewers"] or 0) if identify else None,
        "first_viewed_at": totals["first_viewed_at"],
        "last_viewed_at": totals["last_viewed_at"],
        "identify_viewers": identify,
        "timeline": [
            {"date": row["day"].isoformat() if row["day"] else None, "views": row["views"]} for row in timeline
        ],
        "viewers": [
            {
                "viewer": str(row["viewer_id"]),
                "email": row["viewer__email"],
                "display_name": row["viewer__display_name"],
                "views": row["views"],
                "last_viewed_at": row["last_viewed_at"],
            }
            for row in viewers
        ],
    }


class _AnalyticsViewMixin:
    """Shared aggregation + CSV export helpers."""

    def _record_disabled(self):
        return not _analytics_enabled()

    def _csv_response(self, queryset, filename):
        identify = _identify_viewers()

        class _Echo:
            def write(self, value):
                return value

        writer = csv.writer(_Echo())
        include_viewer = identify
        columns = [c for c in CSV_COLUMNS if include_viewer or not c.startswith("viewer_")]

        def rows():
            yield writer.writerow(columns)
            for view in queryset.select_related("page", "viewer").iterator(chunk_size=500):
                yield writer.writerow(
                    [
                        view.viewed_at.isoformat() if view.viewed_at else "",
                        str(view.page_id),
                        view.page.name if view.page_id else "",
                        str(view.collection_id) if view.collection_id else "",
                        str(view.viewer_id) if (include_viewer and view.viewer_id) else "",
                        (view.viewer.email if (include_viewer and view.viewer_id) else ""),
                        (view.viewer.display_name if (include_viewer and view.viewer_id) else ""),
                    ]
                )

        response = StreamingHttpResponse(rows(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PageAnalyticsViewSet(_AnalyticsViewMixin, BaseViewSet):
    """Record views and read/export per-page analytics."""

    permission_classes = [WorkspacePagePermission]
    serializer_class = PageViewRecordSerializer

    def _get_page(self, slug, page_id):
        return (
            Page.objects.filter(
                id=page_id,
                workspace__slug=slug,
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )

    def record_view(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PageViewRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # A background preload is not a view; recording is also disabled when the
        # deployment opts out. Both acknowledge without writing a row.
        if serializer.validated_data.get("preload") or self._record_disabled():
            return Response(status=status.HTTP_204_NO_CONTENT)

        viewer = None
        if _identify_viewers() and getattr(request.user, "is_authenticated", False):
            viewer = request.user

        view = PageView.objects.create(
            workspace_id=page.workspace_id,
            page_id=page.id,
            collection=nearest_collection(page),
            viewer=viewer,
            viewed_at=timezone.now(),
        )
        return Response({"id": str(view.id)}, status=status.HTTP_201_CREATED)

    def analytics(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        start, end = _resolve_window(request.query_params)
        queryset = _window_queryset(
            PageView.objects.filter(page_id=page.id, workspace_id=page.workspace_id),
            start,
            end,
        )
        collection = nearest_collection(page)
        return Response(
            _aggregate(queryset, page.id, collection.id if collection else None, start=start, end=end),
            status=status.HTTP_200_OK,
        )

    def analytics_export(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        start, end = _resolve_window(request.query_params)
        queryset = _window_queryset(
            PageView.objects.filter(page_id=page.id, workspace_id=page.workspace_id).order_by("viewed_at"),
            start,
            end,
        )
        return self._csv_response(queryset, f"page-{page.id}-analytics.csv")


class PageCollectionAnalyticsViewSet(_AnalyticsViewMixin, BaseViewSet):
    """Read/export analytics rolled up over a Collection's viewed pages."""

    permission_classes = [PageCollectionPermission]
    serializer_class = PageViewRecordSerializer

    def _get_collection(self, slug, collection_id):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return None, None
        collection = PageCollection.objects.filter(
            id=collection_id,
            workspace=workspace,
            deleted_at__isnull=True,
        ).first()
        return workspace, collection

    def analytics(self, request, slug, collection_id):
        workspace, collection = self._get_collection(slug, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        start, end = _resolve_window(request.query_params)
        queryset = _window_queryset(
            PageView.objects.filter(collection_id=collection.id, workspace_id=workspace.id),
            start,
            end,
        )
        payload = _aggregate(queryset, None, collection.id, start=start, end=end)
        payload["collection_name"] = collection.name
        return Response(payload, status=status.HTTP_200_OK)

    def analytics_export(self, request, slug, collection_id):
        workspace, collection = self._get_collection(slug, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        start, end = _resolve_window(request.query_params)
        queryset = _window_queryset(
            PageView.objects.filter(collection_id=collection.id, workspace_id=workspace.id).order_by("viewed_at"),
            start,
            end,
        )
        return self._csv_response(queryset, f"collection-{collection.id}-analytics.csv")
