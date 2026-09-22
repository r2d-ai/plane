# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for Wiki Collections (WIKI-05, spec §5.5 / §19)."""

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import (
    PageCollection,
    PageCollectionMember,
    PageCollectionPage,
)


class PageCollectionSerializer(BaseSerializer):
    member_count = serializers.IntegerField(read_only=True, default=0)
    page_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = PageCollection
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "logo_props",
            "access",
            "sort_order",
            "is_default",
            "member_count",
            "page_count",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["workspace", "is_default", "created_by", "updated_by"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Collection name is required.")
        return value.strip()


class PageCollectionMemberSerializer(BaseSerializer):
    member_detail = serializers.SerializerMethodField()

    class Meta:
        model = PageCollectionMember
        fields = [
            "id",
            "collection",
            "member",
            "member_detail",
            "role",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "collection", "member"]

    def get_member_detail(self, obj):
        member = obj.member
        return {
            "id": str(member.id),
            "email": member.email,
            "display_name": member.display_name,
            "avatar_url": member.avatar_url,
        }


class PageCollectionPageSerializer(BaseSerializer):
    page_detail = serializers.SerializerMethodField()

    class Meta:
        model = PageCollectionPage
        fields = [
            "id",
            "collection",
            "page",
            "page_detail",
            "workspace",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "collection", "page"]

    def get_page_detail(self, obj):
        page = obj.page
        return {
            "id": str(page.id),
            "name": page.name,
            "access": page.access,
            "parent": str(page.parent_id) if page.parent_id else None,
            "sort_order": page.sort_order,
        }
