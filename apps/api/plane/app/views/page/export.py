# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Nested Workspace Wiki export endpoint (WIKI-07c, spec §17.2).

The root page is resolved in the URL workspace and Wiki scope, the caller's
VIEW capability is asserted by ``WorkspacePagePermission`` plus the centralized
access service, and the permitted subtree is returned as a ZIP. Company Wiki
reuses the same route against its designated workspace.
"""

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkspacePagePermission
from plane.db.models import Page, Workspace
from plane.utils.page_access import can_view_page
from plane.utils.page_export import (
    PageExportError,
    export_page_archive,
    safe_export_name,
)

from ..base import BaseAPIView


class WorkspacePageExportEndpoint(BaseAPIView):
    """Download a Wiki page and its permitted descendants as a ZIP."""

    permission_classes = [WorkspacePagePermission]

    def get(self, request, slug, page_id):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        root = (
            Page.objects.filter(
                id=page_id,
                workspace=workspace,
                is_global=True,
                deleted_at__isnull=True,
                archived_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )
        if root is None or not can_view_page(request.user, root, workspace):
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            archive = export_page_archive(root, request.user, workspace)
        except PageExportError as exc:
            return Response(
                {"error": exc.message, "error_code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = f"{safe_export_name(root.name)}-export.zip"
        response = HttpResponse(archive, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = str(len(archive))
        return response
