# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Wiki importer endpoints (WIKI-10, plan §13.2/§13.3).

Both endpoints accept a multipart ZIP upload and return a mapping report. They
are workspace-scoped and require a write role (member/admin); a ``parent`` page
may be supplied to nest the imported root under an existing Wiki page, in which
case the caller must be able to see that page. The heavy lifting — safe archive
reading, parsing and page creation — lives in :mod:`plane.utils.wiki_import`.
"""

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from plane.app.permissions import WorkspacePagePermission
from plane.db.models import Page, Workspace
from plane.utils.page_access import can_edit_page
from plane.utils.page_hierarchy import PageHierarchyError, validate_page_parent
from plane.utils.wiki_import import (
    WikiImportError,
    import_confluence_xml,
    import_notion_html,
)

from ..base import BaseViewSet


class WorkspaceWikiImportEndpoint(BaseViewSet):
    """Import a Notion HTML export or a supported Confluence XML export."""

    model = Page
    serializer_class = None
    permission_classes = [WorkspacePagePermission]
    parser_classes = (MultiPartParser, FormParser)

    def _workspace(self, slug):
        return Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()

    def _parent(self, workspace, request):
        """Resolve an optional parent page inside the URL workspace's Wiki scope."""
        parent_id = request.data.get("parent")
        if not parent_id:
            return None, None
        parent = (
            Page.objects.filter(
                id=parent_id,
                workspace=workspace,
                is_global=True,
                deleted_at__isnull=True,
                archived_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )
        if parent is None or not can_edit_page(request.user, parent, workspace):
            return None, Response({"error": "Parent page not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            validate_page_parent(
                Page(workspace_id=workspace.id, is_global=True),
                parent,
                user=request.user,
                workspace=workspace,
            )
        except PageHierarchyError as exc:
            return None, Response(
                {"error": exc.message, "error_code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return parent, None

    def _run(self, request, slug, importer):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"error": "No archive uploaded", "error_code": "IMPORT_FILE_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent, error = self._parent(workspace, request)
        if error is not None:
            return error

        try:
            report = importer(upload, workspace, request.user, parent=parent)
        except WikiImportError as exc:
            return Response(
                {"error": exc.message, "error_code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"mapping_report": report}, status=status.HTTP_201_CREATED)

    def wiki_import_notion(self, request, slug):
        return self._run(request, slug, import_notion_html)

    def wiki_import_confluence(self, request, slug):
        return self._run(request, slug, import_confluence_xml)
