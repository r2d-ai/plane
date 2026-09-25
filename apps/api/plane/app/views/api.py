# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from typing import Optional
from uuid import uuid4

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from .base import BaseAPIView
from plane.api.service_tokens import (
    READ_ONLY_SERVICE_SCOPES,
    SCOPE_LEVEL_WORKSPACE,
    create_service_access_token,
    revoke_service_access_token,
)
from plane.app.permissions import WorkspaceOwnerPermission
from plane.app.serializers import (
    APITokenSerializer,
    APITokenReadSerializer,
    ServiceAPITokenSerializer,
    ServiceTokenInputSerializer,
)
from plane.db.models import APIToken, Workspace


class ApiTokenEndpoint(BaseAPIView):
    def post(self, request: Request) -> Response:
        label = request.data.get("label", str(uuid4().hex))
        description = request.data.get("description", "")
        expired_at = request.data.get("expired_at", None)
        user_type = 1 if request.user.is_bot else 0

        api_token = APIToken.objects.create(
            label=label,
            description=description,
            user=request.user,
            user_type=user_type,
            expired_at=expired_at,
        )
        return Response(APITokenSerializer(api_token).data, status=status.HTTP_201_CREATED)

    def get(self, request: Request, pk: Optional[str] = None) -> Response:
        if pk is None:
            api_tokens = APIToken.objects.filter(user=request.user, is_service=False)
            return Response(APITokenReadSerializer(api_tokens, many=True).data, status=status.HTTP_200_OK)

        api_token = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
        return Response(APITokenReadSerializer(api_token).data, status=status.HTTP_200_OK)

    def delete(self, request: Request, pk: str) -> Response:
        api_token = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
        api_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request: Request, pk: str) -> Response:
        api_token = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
        serializer = APITokenSerializer(api_token, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WorkspaceServiceTokenEndpoint(BaseAPIView):
    permission_classes = [WorkspaceOwnerPermission]

    def _queryset(self, slug):
        return APIToken.objects.filter(
            is_service=True,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            workspace__slug=slug,
        ).select_related("workspace", "user", "created_by", "revoked_by")

    def get(self, request, slug, pk=None):
        if pk is None:
            return Response(ServiceAPITokenSerializer(self._queryset(slug), many=True).data)

        api_token = self._queryset(slug).get(pk=pk)
        return Response(ServiceAPITokenSerializer(api_token).data)

    def post(self, request, slug):
        serializer = ServiceTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        label = data.get("label")
        if not label:
            return Response({"label": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        workspace = Workspace.objects.get(slug=slug, deleted_at__isnull=True)
        api_token, raw_token = create_service_access_token(
            label=label,
            description=data.get("description", ""),
            created_by=request.user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=data.get("scopes", list(READ_ONLY_SERVICE_SCOPES)),
            workspace=workspace,
            expired_at=data.get("expired_at"),
        )
        response_data = ServiceAPITokenSerializer(api_token).data
        response_data["token"] = raw_token
        return Response(response_data, status=status.HTTP_201_CREATED)

    def patch(self, request, slug, pk):
        api_token = self._queryset(slug).get(pk=pk)
        serializer = ServiceTokenInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_fields = []
        for field in ("label", "description", "expired_at", "scopes"):
            if field in serializer.validated_data:
                setattr(api_token, field, serializer.validated_data[field])
                update_fields.append(field)

        if update_fields:
            api_token.save(update_fields=[*update_fields, "updated_at"])

        if "label" in serializer.validated_data and api_token.user.is_bot:
            api_token.user.display_name = serializer.validated_data["label"]
            api_token.user.save(update_fields=["display_name"])

        return Response(ServiceAPITokenSerializer(api_token).data)

    def delete(self, request, slug, pk):
        api_token = self._queryset(slug).get(pk=pk)
        revoke_service_access_token(api_token, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
