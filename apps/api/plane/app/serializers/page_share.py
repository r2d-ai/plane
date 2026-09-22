# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializer for direct page shares (WIKI-06, spec §5.3).

``workspace`` and ``page`` are read-only: the view derives them from the URL
page, so a caller can never create a share in another workspace (spec §6.2).
"""

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import PageShare


class PageShareSerializer(BaseSerializer):
    member_detail = serializers.SerializerMethodField()

    class Meta:
        model = PageShare
        fields = [
            "id",
            "workspace",
            "page",
            "member",
            "member_detail",
            "role",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["workspace", "page", "member", "created_by", "updated_by"]

    def get_member_detail(self, obj):
        member = obj.member
        return {
            "id": str(member.id),
            "email": member.email,
            "display_name": member.display_name,
            "avatar_url": member.avatar_url,
        }
