# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permissions for workspace dashboards (spec §28, §44.3)."""

from django.conf import settings
from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.db.models import Workspace
from plane.utils.page_access import resolve_workspace_role

READ_ACTIONS = {
    "list",
    "retrieve",
    "data",
    "export",
    "drilldown",
    "members",
}
WRITE_ACTIONS = {
    "create",
    "update",
    "partial_update",
    "destroy",
    "duplicate",
    "layout",
    "favorite",
    "unfavorite",
    "widget_create",
    "widget_update",
    "widget_destroy",
    "member_add",
    "member_update",
    "member_remove",
}


class WorkspaceDashboardsEnabled(BasePermission):
    """When the feature flag is off, deny before any dashboard handler runs."""

    def has_permission(self, request, view):
        return bool(settings.WORKSPACE_DASHBOARDS)


class DashboardPermission(BasePermission):
    message = "You don't have the required permissions."

    def has_permission(self, request, view):
        user = request.user
        if user.is_anonymous or not user.is_active:
            return False

        slug = view.kwargs.get("slug")
        if not slug:
            return False

        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return False

        role = resolve_workspace_role(workspace.id, user.id)
        if role is None:
            return False

        action = getattr(view, "action", None)
        method = request.method

        if action in READ_ACTIONS or method in SAFE_METHODS:
            return True

        if action in WRITE_ACTIONS or method not in SAFE_METHODS:
            # Guests (role 5) may read but not mutate dashboards.
            return role >= 15

        return False
