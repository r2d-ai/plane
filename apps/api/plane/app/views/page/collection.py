# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Collections backend (WIKI-05, plan §8.3).

Collections group Workspace Wiki / Company Wiki pages and act as an
authorization boundary (spec §19). All routes are nested under the URL
workspace and every row lookup is scoped to that workspace, so a Collection or
page UUID from another workspace can never be resolved through these endpoints
(BOLA/IDOR invariant, spec §6.2).
"""

# Django imports
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

# Module imports
from plane.app.permissions import PageCollectionPermission
from plane.app.serializers import (
    PageCollectionMemberSerializer,
    PageCollectionPageSerializer,
    PageCollectionSerializer,
)
from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionMember,
    PageCollectionPage,
    Workspace,
    WorkspaceMember,
)
from plane.utils.page_access import (
    Capability,
    collection_member_role,
    effective_capability,
    filter_visible_pages,
    is_workspace_admin,
    resolve_workspace_role,
)
from plane.utils.page_collection import (
    invalidate_page_collection_caches,
    move_page_to_collection,
    remove_page_from_collection,
)

# Local imports
from ..base import BaseViewSet

VALID_MEMBER_ROLES = {PageCollection.ROLE_VIEW, PageCollection.ROLE_COMMENT, PageCollection.ROLE_EDIT}


class PageCollectionViewSet(BaseViewSet):
    """Collection CRUD, members, page moves and reordering."""

    serializer_class = PageCollectionSerializer
    model = PageCollection
    permission_classes = [PageCollectionPermission]
    search_fields = ["name", "description"]

    # -- helpers ---------------------------------------------------------
    def _workspace(self, slug):
        return Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()

    def _role(self, workspace, user):
        return resolve_workspace_role(workspace.id, user.id)

    def _annotated(self, queryset):
        return queryset.annotate(
            member_count=Count(
                "members",
                filter=Q(members__deleted_at__isnull=True),
                distinct=True,
            ),
            page_count=Count(
                "collection_pages",
                filter=Q(collection_pages__deleted_at__isnull=True),
                distinct=True,
            ),
        )

    def get_queryset(self):
        workspace = self._workspace(self.kwargs.get("slug"))
        if workspace is None:
            return PageCollection.objects.none()

        user = self.request.user
        queryset = PageCollection.objects.filter(workspace=workspace, deleted_at__isnull=True)

        role = self._role(workspace, user)
        if not is_workspace_admin(workspace, user, workspace_role=role):
            # A private Collection is invisible outside its ACL.
            queryset = queryset.filter(
                Q(access=PageCollection.ACCESS_PUBLIC) | Q(members__member=user, members__deleted_at__isnull=True)
            )

        return self._annotated(queryset).distinct()

    def _get_collection(self, workspace, collection_id, *, require_visible=False):
        queryset = PageCollection.objects.filter(
            id=collection_id,
            workspace=workspace,
            deleted_at__isnull=True,
        )
        collection = queryset.first()
        if collection is None:
            return None
        if require_visible and not self._can_see_collection(collection, workspace):
            return None
        return collection

    def _can_see_collection(self, collection, workspace):
        user = self.request.user
        if is_workspace_admin(workspace, user, workspace_role=self._role(workspace, user)):
            return True
        if collection.access == PageCollection.ACCESS_PUBLIC:
            return True
        return collection_member_role(collection, user) is not None

    def _resolve_page(self, workspace, page_id, *, require_edit=False):
        page = Page.objects.filter(
            id=page_id,
            workspace=workspace,
            is_global=True,
            deleted_at__isnull=True,
        ).first()
        if page is None:
            return None, None
        capability = effective_capability(self.request.user, page, workspace)
        if require_edit and capability < Capability.EDIT:
            return None, None
        if not require_edit and capability < Capability.VIEW:
            return None, None
        return page, capability

    def _reject_private_page_in_public_collection(self, page, collection):
        if collection.access == PageCollection.ACCESS_PUBLIC and page.access == Page.PRIVATE_ACCESS:
            return Response(
                {"error": "Private pages cannot be added to a public collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    # -- collection CRUD -------------------------------------------------
    def list(self, request, slug):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.order_by("sort_order", "-created_at")
        return Response(PageCollectionSerializer(queryset, many=True).data, status=status.HTTP_200_OK)

    def create(self, request, slug):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "Collection name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if PageCollection.objects.filter(workspace=workspace, name=name, deleted_at__isnull=True).exists():
            return Response(
                {"error": "A collection with this name already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The first collection in a workspace becomes its default (Q8).
        is_default = not PageCollection.objects.filter(workspace=workspace, deleted_at__isnull=True).exists()

        serializer = PageCollectionSerializer(data=request.data)
        if serializer.is_valid():
            collection = serializer.save(workspace=workspace, is_default=is_default)
            collection = self._annotated(PageCollection.objects.filter(pk=collection.pk)).first()
            return Response(PageCollectionSerializer(collection).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, slug, collection_id=None):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id, require_visible=True)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._annotated(PageCollection.objects.filter(pk=collection.pk)).first()
        return Response(PageCollectionSerializer(collection).data, status=status.HTTP_200_OK)

    def partial_update(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        if "is_default" in request.data or "workspace" in request.data:
            return Response(
                {"error": "is_default and workspace cannot be changed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_name = request.data.get("name")
        if new_name is not None:
            new_name = new_name.strip()
            if not new_name:
                return Response({"error": "Collection name is required"}, status=status.HTTP_400_BAD_REQUEST)
            if (
                PageCollection.objects.filter(workspace=workspace, name=new_name, deleted_at__isnull=True)
                .exclude(pk=collection.pk)
                .exists()
            ):
                return Response(
                    {"error": "A collection with this name already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = PageCollectionSerializer(collection, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            collection = self._annotated(PageCollection.objects.filter(pk=collection.pk)).first()
            return Response(PageCollectionSerializer(collection).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        if collection.is_default:
            return Response(
                {"error": "The default collection cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            now = timezone.now()
            PageCollectionPage.objects.filter(collection=collection, deleted_at__isnull=True).update(deleted_at=now)
            PageCollectionMember.objects.filter(collection=collection, deleted_at__isnull=True).update(deleted_at=now)
            collection.delete()
        invalidate_page_collection_caches(workspace.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def reorder(self, request, slug):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        items = request.data.get("collections")
        if not isinstance(items, list) or not items:
            return Response(
                {"error": "collections must be a non-empty list of {id, sort_order}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = [item.get("id") for item in items if isinstance(item, dict)]
        valid_ids = set(
            str(pk)
            for pk in PageCollection.objects.filter(
                id__in=ids, workspace=workspace, deleted_at__isnull=True
            ).values_list("id", flat=True)
        )
        if len(valid_ids) != len(ids):
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            for item in items:
                PageCollection.objects.filter(id=item["id"], workspace=workspace, deleted_at__isnull=True).update(
                    sort_order=item.get("sort_order", PageCollection.DEFAULT_SORT_ORDER)
                )
        invalidate_page_collection_caches(workspace.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- members ---------------------------------------------------------
    def members(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id, require_visible=True)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        members = PageCollectionMember.objects.filter(collection=collection, deleted_at__isnull=True).select_related(
            "member"
        )
        include_member_email = resolve_workspace_role(workspace.id, request.user.id) is not None
        return Response(
            PageCollectionMemberSerializer(
                members,
                many=True,
                context={"include_member_email": include_member_email},
            ).data,
            status=status.HTTP_200_OK,
        )

    def member_add(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        member_id = request.data.get("member")
        role = request.data.get("role", PageCollection.ROLE_VIEW)
        if role not in VALID_MEMBER_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        # Same-workspace validation: only active members of the collection's
        # workspace can be added (never the designated Company Wiki workspace
        # mixed with another, spec §5.5).
        if not WorkspaceMember.objects.filter(workspace=workspace, member_id=member_id, is_active=True).exists():
            return Response(
                {"error": "Member must be an active member of this workspace"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = PageCollectionMember.all_objects.filter(collection=collection, member_id=member_id).first()
        if existing is not None:
            existing.deleted_at = None
            existing.role = role
            existing.workspace = workspace
            existing.save()
            membership = existing
        else:
            membership = PageCollectionMember.objects.create(
                collection=collection,
                member_id=member_id,
                workspace=workspace,
                role=role,
            )
        invalidate_page_collection_caches(workspace.id)
        return Response(
            PageCollectionMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    def member_update(self, request, slug, collection_id, member_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        membership = PageCollectionMember.objects.filter(
            id=member_id, collection=collection, deleted_at__isnull=True
        ).first()
        if membership is None:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role", membership.role)
        if role not in VALID_MEMBER_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = role
        membership.save()
        invalidate_page_collection_caches(workspace.id)
        return Response(PageCollectionMemberSerializer(membership).data, status=status.HTTP_200_OK)

    def member_remove(self, request, slug, collection_id, member_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        membership = PageCollectionMember.objects.filter(
            id=member_id, collection=collection, deleted_at__isnull=True
        ).first()
        if membership is None:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        membership.delete()
        invalidate_page_collection_caches(workspace.id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- pages -----------------------------------------------------------
    def pages(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id, require_visible=True)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        associations = PageCollectionPage.objects.filter(collection=collection, deleted_at__isnull=True).select_related(
            "page", "page__parent", "page__workspace", "page__owned_by"
        )
        visible_ids = filter_visible_pages(
            Page.objects.filter(
                id__in=associations.values_list("page_id", flat=True),
                workspace=workspace,
            ),
            request.user,
            workspace,
        ).values_list("id", flat=True)
        associations = associations.filter(page_id__in=visible_ids)
        return Response(
            PageCollectionPageSerializer(
                associations,
                many=True,
                context={"request": request, "workspace": workspace},
            ).data,
            status=status.HTTP_200_OK,
        )

    def page_add(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        page, _ = self._resolve_page(workspace, request.data.get("page"), require_edit=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        rejected = self._reject_private_page_in_public_collection(page, collection)
        if rejected is not None:
            return rejected

        association = move_page_to_collection(page, collection)
        return Response(
            PageCollectionPageSerializer(
                association,
                context={"request": request, "workspace": workspace},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def page_move(self, request, slug, collection_id, page_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        page, _ = self._resolve_page(workspace, page_id, require_edit=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        rejected = self._reject_private_page_in_public_collection(page, collection)
        if rejected is not None:
            return rejected

        association = move_page_to_collection(page, collection)
        return Response(
            PageCollectionPageSerializer(
                association,
                context={"request": request, "workspace": workspace},
            ).data,
            status=status.HTTP_200_OK,
        )

    def page_remove(self, request, slug, collection_id, page_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        page, _ = self._resolve_page(workspace, page_id, require_edit=True)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        remove_page_from_collection(page)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def page_reorder(self, request, slug, collection_id):
        workspace = self._workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        collection = self._get_collection(workspace, collection_id)
        if collection is None:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)

        items = request.data.get("pages")
        if not isinstance(items, list) or not items:
            raise ValidationError({"error": "pages must be a non-empty list of {page, sort_order}"})

        page_ids = [item.get("page") for item in items if isinstance(item, dict)]
        valid_ids = set(
            str(pk)
            for pk in PageCollectionPage.objects.filter(
                collection=collection, page_id__in=page_ids, deleted_at__isnull=True
            ).values_list("page_id", flat=True)
        )
        if len(valid_ids) != len(page_ids):
            return Response({"error": "Page is not in this collection"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            for item in items:
                PageCollectionPage.objects.filter(
                    collection=collection, page_id=item["page"], deleted_at__isnull=True
                ).update(sort_order=item.get("sort_order", Page.DEFAULT_SORT_ORDER))
        invalidate_page_collection_caches(workspace.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
