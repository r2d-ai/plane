# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Page templates backend (WIKI-07a, spec §16; plan §10.1).

Templates are workspace-scoped snapshots of a Page's document content. All
routes are nested under the URL workspace and every row lookup is scoped to
that workspace, so a template UUID from another workspace can never be resolved
(BOLA/IDOR invariant, spec §6.2).

The document engine is reused, not duplicated: a template stores the same
``description_*`` triplet as ``Page`` and instantiation copies those fields into
a new Wiki ``Page``.
"""

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import PageTemplatePermission
from plane.app.serializers import PageTemplateSerializer, WorkspacePageSerializer
from plane.db.models import Page, PageTemplate, Workspace
from plane.utils.page_access import can_edit_page, is_workspace_admin, resolve_workspace_role
from plane.utils.page_hierarchy import PageHierarchyError, validate_page_parent

from plane.bgtasks.page_transaction_task import page_transaction

# Local imports
from ..base import BaseViewSet

DEFAULT_TEMPLATE_NAME = "Untitled"


class PageTemplateViewSet(BaseViewSet):
    """CRUD for workspace templates and page instantiation from a template."""

    serializer_class = PageTemplateSerializer
    model = PageTemplate
    permission_classes = [PageTemplatePermission]
    search_fields = ["name", "description_stripped"]

    # -- helpers ---------------------------------------------------------
    def _workspace(self, slug):
        return Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()

    def _role(self, workspace, user):
        return resolve_workspace_role(workspace.id, user.id)

    def _can_manage(self, template, workspace, role):
        """Owner (creator) or workspace admin/owner may change a template."""
        if template.created_by_id == self.request.user.id:
            return True
        return is_workspace_admin(workspace, self.request.user, workspace_role=role)

    def _get_template(self, workspace, template_id):
        return PageTemplate.objects.filter(
            id=template_id,
            workspace=workspace,
            deleted_at__isnull=True,
        ).first()

    def get_queryset(self):
        workspace = self._workspace(self.kwargs.get("slug"))
        if workspace is None:
            return PageTemplate.objects.none()
        return PageTemplate.objects.filter(workspace=workspace, deleted_at__isnull=True).order_by("-created_at")

    # -- template CRUD ---------------------------------------------------
    def list(self, request, slug):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(PageTemplateSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    def create(self, request, slug):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PageTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save(workspace=workspace)
            return Response(PageTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, slug, template_id=None):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        template = self._get_template(workspace, template_id)
        if template is None:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PageTemplateSerializer(template).data, status=status.HTTP_200_OK)

    def partial_update(self, request, slug, template_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        template = self._get_template(workspace, template_id)
        if template is None:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(template, workspace, self._role(workspace, request.user)):
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PageTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, slug, template_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        template = self._get_template(workspace, template_id)
        if template is None:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

        if not self._can_manage(template, workspace, self._role(workspace, request.user)):
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- instantiation ---------------------------------------------------
    def create_page(self, request, slug, template_id):
        """Create a new Wiki page from a template (spec §16)."""
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        template = self._get_template(workspace, template_id)
        if template is None:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

        parent_id = request.data.get("parent")
        parent = None
        if parent_id:
            parent = Page.objects.filter(
                id=parent_id,
                workspace=workspace,
                deleted_at__isnull=True,
            ).first()
            if parent is None or not can_edit_page(request.user, parent, workspace):
                return Response(
                    {"error": "Parent page does not exist.", "error_code": "PAGE_PARENT_NOT_FOUND"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                validate_page_parent(
                    Page(workspace_id=workspace.id, is_global=True),
                    parent,
                    user=request.user,
                    workspace=workspace,
                )
            except PageHierarchyError as exc:
                return Response(
                    {"error": exc.message, "error_code": exc.code},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        name = (request.data.get("name") or template.name or DEFAULT_TEMPLATE_NAME).strip() or DEFAULT_TEMPLATE_NAME

        page = Page.objects.create(
            workspace=workspace,
            name=name,
            description_json=template.description_json,
            description_binary=template.description_binary,
            description_html=template.description_html,
            logo_props=template.logo_props,
            owned_by=request.user,
            parent=parent,
            is_global=True,
            access=request.data.get("access", Page.PUBLIC_ACCESS),
        )

        page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=None,
            page_id=page.id,
        )

        return Response(WorkspacePageSerializer(page, context={"request": request}).data, status=status.HTTP_201_CREATED)
