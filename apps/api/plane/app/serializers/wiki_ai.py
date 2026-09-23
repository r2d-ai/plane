# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for the stable Wiki <-> AI contract (WIKI-10, plan §13.1)."""

from rest_framework import serializers

from plane.db.models import WikiEvent


class WikiAIApplySerializer(serializers.Serializer):
    """Payload for an agent-proposed page edit (plan §13.1 "edit page by agent")."""

    description_html = serializers.CharField(required=True, allow_blank=False)
    description_json = serializers.JSONField(required=False)
    if_version = serializers.CharField(required=False, allow_blank=True)

    def validate_description_html(self, value):
        from plane.utils.content_validator import validate_html_content

        is_valid, error, clean = validate_html_content(value)
        if not is_valid:
            raise serializers.ValidationError(error or "Invalid HTML content")
        return clean


class WikiAISummarizeSerializer(serializers.Serializer):
    max_sentences = serializers.IntegerField(required=False, min_value=1, max_value=20)


class WikiAISearchSerializer(serializers.Serializer):
    query = serializers.CharField(required=True, allow_blank=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)


class WikiAILabelSuggestionSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50)


class WikiEventSerializer(serializers.ModelSerializer):
    actor_id = serializers.UUIDField(read_only=True)
    page_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = WikiEvent
        fields = [
            "id",
            "event_type",
            "page_id",
            "page_name",
            "actor_id",
            "payload",
            "created_at",
        ]
        read_only_fields = fields
