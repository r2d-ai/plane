# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import WorkspaceLiteSerializer
from plane.api.service_tokens import (
    SCOPE_LEVEL_INSTANCE,
    SCOPE_LEVEL_WORKSPACE,
    get_api_token,
    is_service_principal,
)
from plane.db.models import Workspace
from .base import BaseAPIView


class WorkspaceDiscoveryAPIEndpoint(BaseAPIView):
    def get(self, request):
        if is_service_principal(request):
            api_token = get_api_token(request)
            if "workspaces:read" not in set(api_token.scopes or []):
                return Response(
                    {"error": "Token is missing required scope: workspaces:read"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if api_token.scope_level == SCOPE_LEVEL_WORKSPACE:
                workspaces = Workspace.objects.filter(pk=api_token.workspace_id, deleted_at__isnull=True)
            elif api_token.scope_level == SCOPE_LEVEL_INSTANCE:
                workspaces = Workspace.objects.filter(deleted_at__isnull=True)
            else:
                workspaces = Workspace.objects.none()
        else:
            workspaces = Workspace.objects.filter(
                workspace_member__member=request.user,
                workspace_member__is_active=True,
                workspace_member__deleted_at__isnull=True,
                deleted_at__isnull=True,
            ).distinct()

        return Response(WorkspaceLiteSerializer(workspaces.order_by("name", "id"), many=True).data)
