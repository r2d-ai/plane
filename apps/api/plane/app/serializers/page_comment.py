# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializer for page comments (WIKI-06b, spec §5.4, §14)."""

from rest_framework import serializers

from .base import BaseSerializer
from plane.db.models import PageComment


class PageCommentSerializer(BaseSerializer):
    actor_detail = serializers.SerializerMethodField()

    class Meta:
        model = PageComment
        fields = [
            "id",
            "workspace",
            "page",
            "actor",
            "actor_detail",
            "comment_html",
            "comment_json",
            "comment_stripped",
            "parent",
            "edited_at",
            "is_hidden",
            "hidden_reason",
            "hidden_at",
            "hidden_by",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "workspace",
            "page",
            "actor",
            "comment_stripped",
            "is_hidden",
            "hidden_reason",
            "hidden_at",
            "hidden_by",
            "created_by",
            "updated_by",
        ]

    def get_actor_detail(self, obj):
        actor = obj.actor
        return {
            "id": str(actor.id),
            "email": actor.email,
            "display_name": actor.display_name,
            "avatar_url": actor.avatar_url,
        }

    def create(self, validated_data):
        # workspace/page/actor are read-only on the wire and supplied by the
        # view through the serializer context, so they must be bound here.
        return PageComment.objects.create(
            workspace_id=self.context["workspace_id"],
            page_id=self.context["page_id"],
            actor_id=self.context["actor_id"],
            **validated_data,
        )
