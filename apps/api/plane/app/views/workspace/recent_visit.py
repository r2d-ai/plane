# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Q

# Third party imports
from rest_framework import status
from rest_framework.response import Response

from plane.db.models import Page, UserRecentVisit, Workspace
from plane.app.serializers import WorkspaceRecentVisitSerializer
from plane.utils.page_access import filter_visible_pages, resolve_workspace_role

# Modules imports
from ..base import BaseViewSet
from plane.app.permissions import allow_permission, ROLE


class UserRecentVisitViewSet(BaseViewSet):
    model = UserRecentVisit
    use_read_replica = True

    def get_serializer_class(self):
        return WorkspaceRecentVisitSerializer

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def list(self, request, slug):
        user_recent_visits = UserRecentVisit.objects.filter(workspace__slug=slug, user=request.user)

        entity_name = request.query_params.get("entity_name")

        if entity_name:
            user_recent_visits = user_recent_visits.filter(entity_name=entity_name)

        user_recent_visits = user_recent_visits.filter(entity_name__in=["issue", "page", "workspace_page", "project"])

        # Workspace Wiki recents must be re-authorized at read time. A recent
        # visit can outlive a direct share or a Collection membership change,
        # and the Home dashboard must not leak a title after access is revoked.
        if entity_name in (None, "workspace_page"):
            workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
            if workspace is not None:
                visible_wiki_page_ids = filter_visible_pages(
                    Page.objects.filter(
                        workspace=workspace,
                        is_global=True,
                        archived_at__isnull=True,
                        deleted_at__isnull=True,
                    ),
                    request.user,
                    workspace,
                    workspace_role=resolve_workspace_role(workspace.id, request.user.id),
                ).values_list("id", flat=True)
                user_recent_visits = user_recent_visits.filter(
                    ~Q(entity_name="workspace_page") | Q(entity_identifier__in=visible_wiki_page_ids)
                )
            else:
                user_recent_visits = user_recent_visits.exclude(entity_name="workspace_page")

        serializer = WorkspaceRecentVisitSerializer(user_recent_visits[:20], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
