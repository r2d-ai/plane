# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for Wiki Collections (WIKI-05, spec §5.5 / §19)."""

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.utils.page_access import visible_page_parent_id
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
        detail = {
            "id": str(member.id),
            "display_name": member.display_name,
            "avatar_url": member.avatar_url,
        }
        if self.context.get("include_member_email", True):
            detail["email"] = member.email
        return detail


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
        request = self.context.get("request")
        workspace = self.context.get("workspace") or page.workspace
        parent = None
        if request is not None:
            parent = visible_page_parent_id(page, request.user, workspace)
        elif page.parent_id is not None:
            parent = str(page.parent_id)
        owner = page.owned_by
        return {
            "id": str(page.id),
            "name": page.name,
            "access": page.access,
            "parent": parent,
            "sort_order": page.sort_order,
            "logo_props": page.logo_props,
            "updated_at": page.updated_at,
            "owned_by": str(page.owned_by_id),
            "owner_detail": {
                "id": str(owner.id),
                "display_name": owner.display_name,
                "avatar_url": owner.avatar_url,
            },
        }
