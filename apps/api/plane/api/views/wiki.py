# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import WikiPageAPISerializer
from plane.api.service_tokens import authorize_service_request, is_service_principal
from plane.db.models import Page, Workspace
from plane.utils.page_access import (
    can_view_page,
    company_wiki_open_read,
    filter_visible_pages,
    resolve_workspace_role,
)
from .base import BaseAPIView


class WikiPageListAPIEndpoint(BaseAPIView):
    """Read Workspace/Company Wiki pages through PAT, WSAT, or IAT."""

    service_scope = "wiki.pages"
    use_read_replica = True

    def _workspace(self, slug):
        return Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()

    def _visible_queryset(self, request, workspace):
        queryset = Page.objects.filter(
            workspace=workspace,
            is_global=True,
            deleted_at__isnull=True,
        ).select_related("workspace", "owned_by", "parent")

        archived = request.GET.get("archived", "false").lower() == "true"
        queryset = queryset.filter(
            archived_at__isnull=not archived,
        )

        updated_after = request.GET.get("updated_after")
        if updated_after:
            parsed = parse_datetime(updated_after)
            if parsed is None:
                return None
            queryset = queryset.filter(updated_at__gte=parsed)

        if is_service_principal(request):
            if not authorize_service_request(request, workspace.slug, self.service_scope):
                return False
            return queryset.order_by("-updated_at", "-created_at")

        role = resolve_workspace_role(workspace.id, request.user.id)
        if role is None and not company_wiki_open_read(workspace):
            return False

        return filter_visible_pages(
            queryset,
            request.user,
            workspace,
            workspace_role=role,
        ).order_by("-updated_at", "-created_at")

    def get(self, request, slug):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        queryset = self._visible_queryset(request, workspace)
        if queryset is None:
            return Response(
                {"updated_after": "Use an ISO-8601 date-time value."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if queryset is False:
            return Response(
                {"error": "You do not have access to this workspace Wiki."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return self.paginate(
            request=request,
            queryset=queryset,
            on_results=lambda pages: WikiPageAPISerializer(pages, many=True).data,
        )


class WikiPageDetailAPIEndpoint(BaseAPIView):
    """Retrieve one Workspace/Company Wiki page."""

    service_scope = "wiki.pages"
    use_read_replica = True

    def get(self, request, slug, page_id):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        if is_service_principal(request):
            if not authorize_service_request(request, slug, self.service_scope):
                return Response(
                    {"error": "Token is not authorized for this workspace Wiki."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            role = resolve_workspace_role(workspace.id, request.user.id)
            if role is None and not company_wiki_open_read(workspace):
                return Response(
                    {"error": "You do not have access to this workspace Wiki."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        page = (
            Page.objects.filter(
                id=page_id,
                workspace=workspace,
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace", "owned_by", "parent")
            .first()
        )
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        if not is_service_principal(request) and not can_view_page(
            request.user,
            page,
            workspace,
            workspace_role=role,
        ):
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(WikiPageAPISerializer(page).data, status=status.HTTP_200_OK)
