# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.api.serializers import WorkspaceLiteSerializer
from plane.api.service_tokens import is_service_principal
from .base import BaseAPIView


class APIAuthContextEndpoint(BaseAPIView):
    def get(self, request):
        api_token = getattr(request, "api_token", None)
        if api_token is None:
            return Response({"error": "API token context is unavailable"}, status=status.HTTP_401_UNAUTHORIZED)

        is_service = is_service_principal(request)
        workspace = WorkspaceLiteSerializer(api_token.workspace).data if is_service and api_token.workspace_id else None
        return Response(
            {
                "principal_type": "service" if is_service else "user",
                "scope_level": api_token.scope_level if is_service else "user",
                "is_service": is_service,
                "workspace": workspace,
                "scopes": list(api_token.scopes or []) if is_service else None,
            }
        )
