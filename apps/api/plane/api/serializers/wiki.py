# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from .base import BaseSerializer
from plane.db.models import Page
from plane.utils.content_validator import validate_html_content


class WikiPageAPISerializer(BaseSerializer):
    """Read model for Workspace/Company Wiki pages exposed to API principals."""

    class Meta:
        model = Page
        fields = (
            "id",
            "name",
            "description_html",
            "description_stripped",
            "access",
            "parent",
            "owned_by",
            "archived_at",
            "is_locked",
            "sort_order",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WikiPageWriteSerializer(serializers.Serializer):
    """Narrow content/lifecycle-safe write surface for service principals.

    Access control, publishing, sharing and destructive deletion are deliberately
    absent. Those operations require separate administrative scopes and are not
    implied by wiki.pages:write.
    """

    name = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    description_html = serializers.CharField(required=False, allow_blank=True)
    description_json = serializers.JSONField(required=False)
    parent = serializers.UUIDField(required=False, allow_null=True)
    color = serializers.CharField(required=False, allow_blank=True, max_length=255)
    sort_order = serializers.FloatField(required=False)

    def validate_description_html(self, value):
        valid, error, sanitized = validate_html_content(value)
        if not valid:
            raise serializers.ValidationError(error or "Invalid HTML content")
        return sanitized if sanitized is not None else value
