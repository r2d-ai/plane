# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for workspace dashboards (spec §33)."""

from rest_framework import serializers

from plane.app.serializers.base import BaseSerializer
from plane.db.models import (
    Dashboard,
    DashboardFavorite,
    DashboardMemberAccess,
    DashboardProject,
    DashboardWidget,
)


class DashboardWidgetSerializer(BaseSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            "id",
            "dashboard",
            "title",
            "description",
            "widget_type",
            "widget_model",
            "query_config",
            "style_config",
            "layout_config",
            "inherit_time_scope",
            "custom_time_scope",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["dashboard"]

    def validate_query_config(self, value):
        if value is None:
            return {}
        if "schema_version" not in value:
            raise serializers.ValidationError("query_config must include schema_version.")
        return value


class DashboardMemberAccessSerializer(BaseSerializer):
    class Meta:
        model = DashboardMemberAccess
        fields = ["id", "dashboard", "member", "access", "created_at", "updated_at"]
        read_only_fields = ["dashboard"]


class DashboardSerializer(BaseSerializer):
    project_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    projects = serializers.SerializerMethodField(read_only=True)
    widgets = DashboardWidgetSerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Dashboard
        fields = [
            "id",
            "workspace",
            "name",
            "description",
            "owner",
            "visibility",
            "filters",
            "pql",
            "default_time_scope",
            "comparison",
            "project_ids",
            "projects",
            "widgets",
            "is_favorited",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["workspace", "owner"]

    def get_projects(self, obj):
        return [
            str(pid)
            for pid in DashboardProject.objects.filter(
                dashboard=obj, deleted_at__isnull=True
            ).values_list("project_id", flat=True)
        ]

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return DashboardFavorite.objects.filter(
            dashboard=obj,
            member_id=request.user.id,
            deleted_at__isnull=True,
        ).exists()

    def validate_name(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Dashboard name is required.")
        return str(value).strip()
