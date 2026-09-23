# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace Wiki backend (WIKI-01).

Workspace Wiki pages are ordinary ``Page`` rows with ``is_global=True`` in a
real workspace and no ``ProjectPage`` link. Company Wiki reuses these endpoints
against the workspace designated by ``COMPANY_WIKI_WORKSPACE_SLUG`` (spec §29.6)
so there is no separate instance API, permission class or service.
"""

# Python imports
import json
import uuid
from datetime import datetime

from django.core.serializers.json import DjangoJSONEncoder

# Django imports
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    Exists,
    OuterRef,
    Q,
    Value,
    UUIDField,
)
from django.db.models.functions import Coalesce
from django.http import StreamingHttpResponse

# Third party imports
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkspacePagePermission
from plane.app.serializers import (
    PageBinaryUpdateSerializer,
    PageShareSerializer,
    PageTemplateSerializer,
    WorkspacePageSerializer,
)
from plane.db.models import (
    Page,
    PageLog,
    PageShare,
    PageTemplate,
    UserFavorite,
    WikiEvent,
    Workspace,
    WorkspaceMember,
)
from plane.utils.error_codes import ERROR_CODES
from plane.utils.page_access import (
    can_view_page,
    filter_visible_pages,
    resolve_workspace_role,
)
from plane.utils.page_hierarchy import PageHierarchyError, validate_page_parent
from plane.utils.wiki_ai import emit_wiki_event

from plane.bgtasks.page_transaction_task import page_transaction
from plane.bgtasks.page_version_task import track_page_version
from plane.bgtasks.recent_visited_task import recent_visited_task

# Local imports
from ..base import BaseAPIView, BaseViewSet
from .base import unarchive_archive_page_and_descendants


ORDER_BY_ALLOWLIST = {
    "name",
    "-name",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
    "sort_order",
    "-sort_order",
}

VALID_SHARE_ROLES = {PageShare.VIEW, PageShare.COMMENT, PageShare.EDIT}


def _hierarchy_error_response(exc):
    return Response(
        {"error": exc.message, "error_code": exc.code},
        status=status.HTTP_400_BAD_REQUEST,
    )


class WorkspacePageViewSet(BaseViewSet):
    """CRUD and lifecycle endpoints for Workspace Wiki / Company Wiki pages."""

    serializer_class = WorkspacePageSerializer
    model = Page
    permission_classes = [WorkspacePagePermission]
    search_fields = ["name", "description_stripped"]

    def get_queryset(self):
        user = self.request.user
        subquery = UserFavorite.objects.filter(
            user=user,
            entity_type="page",
            entity_identifier=OuterRef("pk"),
            workspace__slug=self.kwargs.get("slug"),
        )
        queryset = (
            Page.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .select_related("owned_by")
            .prefetch_related("labels")
            .annotate(is_favorite=Exists(subquery))
            .annotate(
                label_ids=Coalesce(
                    ArrayAgg(
                        "page_labels__label_id",
                        distinct=True,
                        filter=~Q(page_labels__label_id__isnull=True),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
                project_ids=Value([], output_field=ArrayField(UUIDField())),
            )
        )

        order_by = self.request.GET.get("order_by", "-created_at")
        if order_by not in ORDER_BY_ALLOWLIST:
            raise ValidationError({"error": "Invalid order_by value", "error_code": "INVALID_ORDER_BY"})

        # Single visibility path (plan §9.2): owned + public + direct-share
        # pages, minus whole subtrees behind a private Collection boundary. Both
        # helpers are no-ops (zero extra queries) when the workspace has no
        # private Collection and the user has no share, so the pre-WIKI-06 list
        # path keeps its query plan.
        workspace = Workspace.objects.filter(slug=self.kwargs.get("slug"), deleted_at__isnull=True).first()
        queryset = filter_visible_pages(
            queryset,
            user,
            workspace,
            workspace_role=resolve_workspace_role(workspace.id, user.id) if workspace is not None else None,
        )

        queryset = queryset.order_by("-is_favorite", order_by)

        parent = self.request.GET.get("parent")
        if parent is not None:
            if parent in ("", "null", "None"):
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent)

        access = self.request.GET.get("access")
        if access in ("public", "0"):
            queryset = queryset.filter(access=Page.PUBLIC_ACCESS)
        elif access in ("private", "1"):
            queryset = queryset.filter(access=Page.PRIVATE_ACCESS)

        archived = self.request.GET.get("archived", "false").lower() == "true"
        if archived:
            queryset = queryset.filter(archived_at__isnull=False)
        else:
            queryset = queryset.filter(archived_at__isnull=True)

        owner = self.request.GET.get("owner")
        if owner:
            queryset = queryset.filter(owned_by_id=owner)

        if self.request.GET.get("favorite", "false").lower() == "true":
            queryset = queryset.filter(is_favorite=True)

        return self.filter_queryset(queryset).distinct()

    def _resolve_parent(self, slug, parent_id):
        """Resolve a candidate parent inside the URL workspace.

        Scope (project vs Wiki) is deliberately not filtered here so the shared
        hierarchy guard can reject project-vs-Wiki nesting with a stable error
        code instead of silently reporting the parent as missing.
        """
        return (
            Page.objects.filter(
                id=parent_id,
                workspace__slug=slug,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )

    def _get_page(self, slug, page_id, *, include_archived=False):
        """Resolve a page inside the URL workspace's Wiki scope.

        The permission class has already asserted the caller's capability for
        the action; this pins the lookup to the workspace + Wiki scope and
        applies the centralized VIEW check so a private page reached without an
        explicit share stays invisible (spec §6.5).
        """
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
        if page is None:
            return None
        if not include_archived and page.archived_at is not None:
            return None
        if not can_view_page(self.request.user, page, page.workspace):
            return None
        return page

    def create(self, request, slug):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        parent_id = request.data.get("parent")
        parent = None
        if parent_id:
            parent = self._resolve_parent(slug, parent_id)
            if parent is None:
                return _hierarchy_error_response(
                    PageHierarchyError("PAGE_PARENT_NOT_FOUND", "Parent page does not exist.")
                )
            try:
                validate_page_parent(Page(workspace_id=workspace.id, is_global=True), parent)
            except PageHierarchyError as exc:
                return _hierarchy_error_response(exc)

        serializer = WorkspacePageSerializer(
            data=request.data,
            context={
                "workspace_id": workspace.id,
                "owned_by_id": request.user.id,
                "description_json": request.data.get("description_json", {}),
                "description_binary": request.data.get("description_binary", None),
                "description_html": request.data.get("description_html", "<p></p>"),
            },
        )
        if serializer.is_valid():
            serializer.save()
            page_transaction.delay(
                new_description_html=request.data.get("description_html", "<p></p>"),
                old_description_html=None,
                page_id=serializer.data["id"],
            )
            page = self.get_queryset().filter(pk=serializer.data["id"]).first()
            emit_wiki_event(
                page,
                WikiEvent.PAGE_CREATED,
                actor=request.user,
                payload={
                    "parent_page_id": str(page.parent_id) if page.parent_id else None,
                    "access": page.access,
                },
            )
            return Response(WorkspacePageSerializer(page).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request, slug):
        queryset = self.get_queryset()
        pages = WorkspacePageSerializer(queryset, many=True).data
        return Response(pages, status=status.HTTP_200_OK)

    def retrieve(self, request, slug, page_id=None):
        page = self._get_page(slug, page_id, include_archived=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        data = WorkspacePageSerializer(page).data
        data["issue_ids"] = list(
            PageLog.objects.filter(page_id=page_id, entity_name="issue").values_list("entity_identifier", flat=True)
        )

        track_visit = request.query_params.get("track_visit", "true").lower() == "true"
        if track_visit:
            recent_visited_task.delay(
                slug=slug,
                entity_name="page",
                entity_identifier=page_id,
                user_id=request.user.id,
                project_id=None,
            )
        return Response(data, status=status.HTTP_200_OK)

    def partial_update(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        if page.is_locked:
            return Response({"error": "Page is locked"}, status=status.HTTP_400_BAD_REQUEST)

        if "parent" in request.data:
            parent_id = request.data.get("parent")
            if parent_id:
                parent = self._resolve_parent(slug, parent_id)
                if parent is None:
                    return _hierarchy_error_response(
                        PageHierarchyError("PAGE_PARENT_NOT_FOUND", "Parent page does not exist.")
                    )
                try:
                    validate_page_parent(page, parent)
                except PageHierarchyError as exc:
                    return _hierarchy_error_response(exc)

        if page.access != request.data.get("access", page.access) and page.owned_by_id != request.user.id:
            return Response(
                {"error": "Access cannot be updated since this page is owned by someone else"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WorkspacePageSerializer(page, data=request.data, partial=True)
        page_description = page.description_html
        old_parent_id = page.parent_id
        old_access = page.access
        if serializer.is_valid():
            serializer.save()
            if request.data.get("description_html"):
                page_transaction.delay(
                    new_description_html=request.data.get("description_html", "<p></p>"),
                    old_description_html=page_description,
                    page_id=page_id,
                )
            emit_wiki_event(page, WikiEvent.PAGE_UPDATED, actor=request.user)
            if page.parent_id != old_parent_id:
                emit_wiki_event(
                    page,
                    WikiEvent.PAGE_MOVED,
                    actor=request.user,
                    payload={"old_parent_page_id": str(old_parent_id) if old_parent_id else None},
                )
            if page.access != old_access:
                emit_wiki_event(
                    page,
                    WikiEvent.PAGE_ACCESS_CHANGED,
                    actor=request.user,
                    payload={"old_access": old_access, "access": page.access},
                )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def archive(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        UserFavorite.objects.filter(
            entity_type="page",
            entity_identifier=page_id,
            workspace__slug=slug,
        ).delete()

        unarchive_archive_page_and_descendants(page_id, datetime.now())
        emit_wiki_event(page, WikiEvent.PAGE_ARCHIVED, actor=request.user)
        return Response({"archived_at": str(datetime.now())}, status=status.HTTP_200_OK)

    def unarchive(self, request, slug, page_id):
        page = self._get_page(slug, page_id, include_archived=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        # If the parent is archived, detach the page so the restored tree stays valid.
        if page.parent_id and page.parent.archived_at:
            page.parent = None
            page.save(update_fields=["parent"])

        unarchive_archive_page_and_descendants(page_id, None)
        emit_wiki_event(page, WikiEvent.PAGE_RESTORED, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def lock(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        page.is_locked = True
        page.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def unlock(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        page.is_locked = False
        page.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def access(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        # The permission class already required MANAGE (owner/admin).
        access = request.data.get("access", Page.PUBLIC_ACCESS)
        if access not in (Page.PUBLIC_ACCESS, Page.PRIVATE_ACCESS):
            return Response({"error": "Invalid access value"}, status=status.HTTP_400_BAD_REQUEST)

        page.access = access
        page.save(update_fields=["access"])
        emit_wiki_event(
            page,
            WikiEvent.PAGE_ACCESS_CHANGED,
            actor=request.user,
            payload={"access": access},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- direct sharing (WIKI-06, plan §9.1) -----------------------------
    @staticmethod
    def _log_share_activity(page, actor, action, share):
        """Record a share change on the Page-adjacent audit log (spec §20).

        ``PageLog`` is Plane's Page audit primitive, so share changes reuse it
        instead of introducing a second event store.
        """
        PageLog.objects.create(
            transaction=uuid.uuid4(),
            page=page,
            entity_name="share",
            entity_type=action,
            entity_identifier=share.member_id,
            workspace=page.workspace,
            created_by=actor,
            updated_by=actor,
        )

    def share_list(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        shares = PageShare.objects.filter(page=page, deleted_at__isnull=True).select_related("member")
        return Response(PageShareSerializer(shares, many=True).data, status=status.HTTP_200_OK)

    def share_add(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        workspace = page.workspace
        member_id = request.data.get("member")
        role = request.data.get("role", PageShare.VIEW)
        if role not in VALID_SHARE_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        # Same-workspace validation (spec §5.3): only active members of the
        # page's workspace can be shared with.
        if (
            not member_id
            or not WorkspaceMember.objects.filter(workspace=workspace, member_id=member_id, is_active=True).exists()
        ):
            return Response(
                {"error": "Member must be an active member of this workspace"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = PageShare.all_objects.filter(page=page, member_id=member_id).first()
        if existing is not None:
            existing.deleted_at = None
            existing.workspace = workspace
            existing.role = role
            existing.save()
            share = existing
        else:
            share = PageShare.objects.create(
                page=page,
                member_id=member_id,
                workspace=workspace,
                role=role,
            )
        self._log_share_activity(page, request.user, "created", share)
        return Response(PageShareSerializer(share).data, status=status.HTTP_201_CREATED)

    def share_update(self, request, slug, page_id, share_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        share = PageShare.objects.filter(id=share_id, page=page, deleted_at__isnull=True).first()
        if share is None:
            return Response({"error": "Share not found"}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role", share.role)
        if role not in VALID_SHARE_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        share.role = role
        share.save()
        self._log_share_activity(page, request.user, "updated", share)
        return Response(PageShareSerializer(share).data, status=status.HTTP_200_OK)

    def share_remove(self, request, slug, page_id, share_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        share = PageShare.objects.filter(id=share_id, page=page, deleted_at__isnull=True).first()
        if share is None:
            return Response({"error": "Share not found"}, status=status.HTTP_404_NOT_FOUND)

        share.delete()
        self._log_share_activity(page, request.user, "removed", share)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, slug, page_id):
        page = self._get_page(slug, page_id, include_archived=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        if page.archived_at is None:
            return Response(
                {"error": "The page should be archived before deleting"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Detach children so no Wiki branch is orphaned into a deleted subtree.
        Page.objects.filter(parent_id=page_id, workspace__slug=slug, is_global=True).update(parent=None)

        emit_wiki_event(page, WikiEvent.PAGE_DELETED, actor=request.user)
        page.delete()
        UserFavorite.objects.filter(
            workspace__slug=slug,
            entity_identifier=page_id,
            entity_type="page",
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def save_as_template(self, request, slug, page_id):
        """Snapshot a Wiki page's document content as a workspace template.

        Templates reuse the Page document fields verbatim (spec §16); the
        permission class already required EDIT on the page, which also scopes
        the lookup to the URL workspace (BOLA/IDOR invariant).
        """
        page = self._get_page(slug, page_id, include_archived=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        name = (request.data.get("name") or page.name or "Untitled").strip() or "Untitled"
        template = PageTemplate.objects.create(
            workspace=page.workspace,
            name=name,
            description_json=page.description_json,
            description_binary=page.description_binary,
            description_html=page.description_html,
            logo_props=page.logo_props,
            created_by=request.user,
        )
        return Response(PageTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class WorkspacePagesDescriptionViewSet(BaseViewSet):
    serializer_class = PageBinaryUpdateSerializer
    model = Page
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
        if page is None or not can_view_page(self.request.user, page, page.workspace):
            return None
        return page

    def retrieve(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        binary_data = page.description_binary

        def stream_data():
            if binary_data:
                yield binary_data
            else:
                yield b""

        response = StreamingHttpResponse(stream_data(), content_type="application/octet-stream")
        response["Content-Disposition"] = 'attachment; filename="page_description.bin"'
        return response

    def partial_update(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        if page.is_locked:
            return Response(
                {"error_code": ERROR_CODES["PAGE_LOCKED"], "error_message": "PAGE_LOCKED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page.archived_at:
            return Response(
                {"error_code": ERROR_CODES["PAGE_ARCHIVED"], "error_message": "PAGE_ARCHIVED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_description_html = page.description_html
        existing_instance = json.dumps({"description_html": old_description_html}, cls=DjangoJSONEncoder)

        serializer = PageBinaryUpdateSerializer(page, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if request.data.get("description_html"):
                page_transaction.delay(
                    new_description_html=request.data.get("description_html", "<p></p>"),
                    old_description_html=old_description_html,
                    page_id=page_id,
                )
            track_page_version.delay(
                page_id=page_id,
                existing_instance=existing_instance,
                user_id=request.user.id,
            )
            return Response({"message": "Updated successfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkspacePageFavoriteViewSet(BaseViewSet):
    model = UserFavorite
    permission_classes = [WorkspacePagePermission]

    def favorite_create(self, request, slug, page_id):
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        UserFavorite.objects.get_or_create(
            workspace=workspace,
            entity_identifier=page_id,
            entity_type="page",
            user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def favorite_destroy(self, request, slug, page_id):
        UserFavorite.objects.filter(
            workspace__slug=slug,
            user=request.user,
            entity_identifier=page_id,
            entity_type="page",
        ).delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspacePageDuplicateEndpoint(BaseAPIView):
    permission_classes = [WorkspacePagePermission]

    def post(self, request, slug, page_id):
        page = Page.objects.filter(
            id=page_id,
            workspace__slug=slug,
            is_global=True,
            deleted_at__isnull=True,
        ).first()
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        # Authorization is the permission class's job (EDIT on the page); a
        # private page reached without a share was already reported as missing.

        page.pk = None
        page.name = f"{page.name} (Copy)"
        page.description_binary = None
        page.owned_by = request.user
        page.created_by = request.user
        page.updated_by = request.user
        page.save()

        page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=None,
            page_id=page.id,
        )

        page = (
            Page.objects.filter(pk=page.id)
            .annotate(
                label_ids=Coalesce(
                    ArrayAgg(
                        "page_labels__label_id",
                        distinct=True,
                        filter=~Q(page_labels__label_id__isnull=True),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
                project_ids=Value([], output_field=ArrayField(UUIDField())),
            )
            .first()
        )
        return Response(WorkspacePageSerializer(page).data, status=status.HTTP_201_CREATED)
