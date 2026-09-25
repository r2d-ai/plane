# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import status
from rest_framework.response import Response

from plane.api.service_tokens import (
    READ_ONLY_SERVICE_SCOPES,
    SCOPE_LEVEL_INSTANCE,
    create_service_access_token,
    revoke_service_access_token,
)
from plane.app.serializers import ServiceAPITokenSerializer, ServiceTokenInputSerializer
from plane.app.views.base import BaseAPIView
from plane.db.models import APIToken
from plane.license.api.permissions import InstanceAdminPermission


class InstanceServiceTokenEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def _queryset(self):
        return APIToken.objects.filter(
            is_service=True,
            scope_level=SCOPE_LEVEL_INSTANCE,
            workspace__isnull=True,
        ).select_related("user", "created_by", "revoked_by")

    def get(self, request, pk=None):
        if pk is None:
            return Response(ServiceAPITokenSerializer(self._queryset(), many=True).data)

        api_token = self._queryset().get(pk=pk)
        return Response(ServiceAPITokenSerializer(api_token).data)

    def post(self, request):
        serializer = ServiceTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        label = data.get("label")
        if not label:
            return Response({"label": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        api_token, raw_token = create_service_access_token(
            label=label,
            description=data.get("description", ""),
            created_by=request.user,
            scope_level=SCOPE_LEVEL_INSTANCE,
            scopes=data.get("scopes", list(READ_ONLY_SERVICE_SCOPES)),
            expired_at=data.get("expired_at"),
        )
        response_data = ServiceAPITokenSerializer(api_token).data
        response_data["token"] = raw_token
        return Response(response_data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        api_token = self._queryset().get(pk=pk)
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

    def delete(self, request, pk):
        api_token = self._queryset().get(pk=pk)
        revoke_service_access_token(api_token, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
