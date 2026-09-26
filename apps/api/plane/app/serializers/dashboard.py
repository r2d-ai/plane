# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for workspace dashboards (spec §33)."""

from rest_framework import serializers

from plane.app.serializers.base import BaseSerializer
from plane.utils.dashboard_analytics import (
    redact_dashboard_representation_for_viewer,
    resolve_scoped_project_ids,
)
from plane.db.models import (
    Dashboard,
    DashboardFavorite,
    DashboardMemberAccess,
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
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return []
        return resolve_scoped_project_ids(
            obj, workspace=obj.workspace, principal=request.user
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return data
        return redact_dashboard_representation_for_viewer(
            data, dashboard=instance, principal=request.user
        )

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
