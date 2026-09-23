# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Page comment endpoints for Workspace/Company Wiki pages (WIKI-06b).

CRUD for page-level comments. Permissions derive from effective page access:
- VIEW: can list/retrieve comments
- COMMENT: can create comments
- EDIT: can edit/delete own comments
- MANAGE: can delete any comment on the page
"""

from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkspacePagePermission
from plane.app.serializers import PageCommentSerializer
from plane.db.models import Page, PageComment, Workspace

from ..base import BaseViewSet


class PageCommentViewSet(BaseViewSet):
    """CRUD for page-level comments on Workspace Wiki pages."""

    serializer_class = PageCommentSerializer
    model = PageComment
    permission_classes = [WorkspacePagePermission]

    def _get_page(self, slug, page_id):
        page = (
            Page.objects.filter(
                id=page_id,
                workspace__slug=slug,
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )
        return page

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        page_id = self.kwargs.get("page_id")
        return (
            PageComment.objects.filter(
                page_id=page_id,
                page__workspace__slug=slug,
                deleted_at__isnull=True,
            )
            .select_related("actor")
            .order_by("-created_at")
        )

    def comment_list(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        comments = self.get_queryset()
        return Response(PageCommentSerializer(comments, many=True).data, status=status.HTTP_200_OK)

    def comment_create(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        parent_id = request.data.get("parent")
        if parent_id:
            parent_exists = PageComment.objects.filter(
                id=parent_id,
                page_id=page_id,
                deleted_at__isnull=True,
            ).exists()
            if not parent_exists:
                return Response({"error": "Parent comment not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PageCommentSerializer(
            data=request.data,
            context={
                "workspace_id": workspace.id,
                "page_id": page_id,
                "actor_id": request.user.id,
            },
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def comment_update(self, request, slug, page_id, comment_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        comment = PageComment.objects.filter(
            id=comment_id,
            page_id=page_id,
            deleted_at__isnull=True,
        ).first()
        if comment is None:
            return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only the comment author may edit their own comment.
        if comment.actor_id != request.user.id:
            return Response(
                {"error": "You can only edit your own comments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PageCommentSerializer(comment, data=request.data, partial=True)
        if serializer.is_valid():
            comment.edited_at = timezone.now()
            comment.save(update_fields=["edited_at"])
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def comment_destroy(self, request, slug, page_id, comment_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        comment = PageComment.objects.filter(
            id=comment_id,
            page_id=page_id,
            deleted_at__isnull=True,
        ).first()
        if comment is None:
            return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        # Authors may delete their own comments; page managers may delete any.
        from plane.utils.page_access import can_manage_page, resolve_workspace_role

        workspace = page.workspace
        role = resolve_workspace_role(workspace.id, request.user.id)
        is_author = comment.actor_id == request.user.id
        is_manager = can_manage_page(request.user, page, workspace, workspace_role=role)

        if not is_author and not is_manager:
            return Response(
                {"error": "You do not have permission to delete this comment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
