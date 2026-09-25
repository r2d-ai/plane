# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.utils import timezone
from rest_framework import serializers

from .base import BaseSerializer
from plane.api.service_tokens import normalize_service_scopes
from plane.db.models import APIToken, APIActivityLog


class APITokenSerializer(BaseSerializer):
    class Meta:
        model = APIToken
        fields = "__all__"
        read_only_fields = [
            "token",
            "token_hash",
            "token_prefix",
            "scope_level",
            "scopes",
            "revoked_at",
            "revoked_by",
            "expired_at",
            "created_at",
            "updated_at",
            "workspace",
            "user",
            "is_active",
            "last_used",
            "user_type",
            "allowed_rate_limit",
        ]


class APITokenReadSerializer(BaseSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = APIToken
        exclude = ("token", "token_hash")

    def get_is_active(self, obj: APIToken) -> bool:
        if not obj.is_active or obj.revoked_at is not None:
            return False
        if obj.expired_at is None:
            return True
        return timezone.now() < obj.expired_at


class ServiceAPITokenSerializer(BaseSerializer):
    is_active = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()

    class Meta:
        model = APIToken
        fields = (
            "id",
            "label",
            "description",
            "is_active",
            "last_used",
            "expired_at",
            "scope_level",
            "scopes",
            "token_prefix",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "revoked_at",
            "revoked_by",
        )
        read_only_fields = fields

    def get_is_active(self, obj):
        if not obj.is_active or obj.revoked_at is not None:
            return False
        return obj.expired_at is None or obj.expired_at > timezone.now()

    def get_workspace(self, obj):
        if obj.workspace is None:
            return None
        return {
            "id": str(obj.workspace.id),
            "name": obj.workspace.name,
            "slug": obj.workspace.slug,
        }


class ServiceTokenInputSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    expired_at = serializers.DateTimeField(required=False, allow_null=True)
    scopes = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
        required=False,
    )

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be empty")
        return value

    def validate_expired_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future")
        return value

    _SCOPE_VALIDATION_MESSAGES = {
        "scopes must be a list": "Scopes must be a list",
        "At least one scope is required": "At least one scope is required",
    }

    def validate_scopes(self, value):
        try:
            return normalize_service_scopes(value)
        except ValueError as exc:
            message = self._SCOPE_VALIDATION_MESSAGES.get(str(exc))
            if message is not None:
                raise serializers.ValidationError(message) from exc
            raise serializers.ValidationError("Unsupported scopes") from exc


class APIActivityLogSerializer(BaseSerializer):
    class Meta:
        model = APIActivityLog
        fields = "__all__"
