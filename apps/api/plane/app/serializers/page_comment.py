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
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["workspace", "page", "actor", "comment_stripped", "created_by", "updated_by"]

    def get_actor_detail(self, obj):
        actor = obj.actor
        return {
            "id": str(actor.id),
            "email": actor.email,
            "display_name": actor.display_name,
            "avatar_url": actor.avatar_url,
        }
