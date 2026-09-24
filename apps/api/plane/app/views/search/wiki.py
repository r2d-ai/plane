# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.db.models import Page, UserFavorite, Workspace, WorkspaceMember
from plane.utils.page_access import (
    WORKSPACE_WRITE_ROLES,
    company_wiki_open_read,
    hidden_page_ids,
    page_visibility_q,
)


def authorized_workspaces(user):
    if not user.is_active:
        return [], {}
    roles = dict(
        WorkspaceMember.objects.filter(
            member=user,
            is_active=True,
            deleted_at__isnull=True,
        ).values_list("workspace_id", "role")
    )
    scope = Q(id__in=roles)
    default = Workspace.objects.filter(slug=settings.COMPANY_WIKI_WORKSPACE_SLUG).first()
    if default is not None and company_wiki_open_read(default):
        scope |= Q(id=default.id)
    workspaces = list(Workspace.objects.filter(scope, deleted_at__isnull=True))
    workspaces.sort(
        key=lambda workspace: (
            workspace.slug != settings.COMPANY_WIKI_WORKSPACE_SLUG,
            workspace.name.casefold(),
            str(workspace.id),
        )
    )
    return workspaces, roles


def visible_pages(user, workspace, roles):
    visibility = page_visibility_q(user, workspace)
    return (
        Page.objects.filter(
            visibility,
            workspace=workspace,
            is_global=True,
            archived_at__isnull=True,
            deleted_at__isnull=True,
        )
        .exclude(id__in=hidden_page_ids(workspace, user, workspace_role=roles.get(workspace.id)))
        .select_related("workspace")
        .defer("description_html", "description_binary", "description_json")
    )


def serialize_page(page):
    return {
        "page_id": str(page.id),
        "page_name": page.name,
        "workspace_slug": page.workspace.slug,
        "workspace_name": page.workspace.name,
        "logo_props": page.logo_props,
        "matched_content_summary": (page.description_stripped or "")[:160],
    }


def bounded_results(request, predicate, limit):
    workspaces, roles = authorized_workspaces(request.user)
    pages = []
    for workspace in workspaces:
        queryset = visible_pages(request.user, workspace, roles).filter(predicate)
        pages.extend(queryset.distinct().order_by("-updated_at", "id")[: min(limit, 20)])
    pages.sort(key=lambda page: (-page.updated_at.timestamp(), str(page.id)))
    return {"results": [serialize_page(page) for page in pages[:limit]]}


class UnifiedWikiScopesEndpoint(BaseAPIView):
    def get(self, request):
        workspaces, roles = authorized_workspaces(request.user)
        return Response(
            [
                {
                    "id": str(workspace.id),
                    "slug": workspace.slug,
                    "name": workspace.name,
                    "is_default": workspace.slug == settings.COMPANY_WIKI_WORKSPACE_SLUG,
                    "is_member": workspace.id in roles,
                    "can_create": roles.get(workspace.id) in WORKSPACE_WRITE_ROLES,
                }
                for workspace in workspaces
            ]
        )


class UnifiedWikiSearchEndpoint(BaseAPIView):
    def get(self, request):
        query = request.query_params.get("query", "").strip()
        if not query:
            raise ValidationError({"query": "A non-empty query is required."})
        try:
            limit = int(request.query_params.get("limit", 100))
        except (ValueError, TypeError):
            raise ValidationError({"limit": "Must be an integer between 1 and 100."})
        if not 1 <= limit <= 100:
            raise ValidationError({"limit": "Must be an integer between 1 and 100."})
        return Response(
            bounded_results(request, Q(name__icontains=query) | Q(description_stripped__icontains=query), limit)
        )


class UnifiedWikiPersonalPagesEndpoint(BaseAPIView):
    def get(self, request):
        section = request.query_params.get("section")
        if section == "favorites":
            predicate = Q(
                id__in=UserFavorite.objects.filter(
                    user=request.user,
                    entity_type="page",
                    deleted_at__isnull=True,
                ).values("entity_identifier")
            )
        elif section == "owned":
            predicate = Q(owned_by=request.user)
        elif section == "shared":
            predicate = Q(shares__member=request.user, shares__deleted_at__isnull=True)
        else:
            raise ValidationError({"section": "Must be favorites, owned, or shared."})
        return Response(bounded_results(request, predicate, 100))
