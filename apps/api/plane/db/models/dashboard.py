# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""P0 dashboard data model (RD-452).

Implements the storage layer for the workspace dashboards & analytics v2 spec
(see ``docs/workspace-dashboards-analytics-v2-spec.md`` §27). P0 covers the
data model only: API endpoints, serializers, the analytics query engine, and
the public-publishing surface are intentionally out of scope here.

All five tables are additive — nothing on the legacy ``Issue``/``Cycle``/
``Module``/``Estimate`` tables is touched. Soft-delete semantics follow the
``AuditModel`` contract used elsewhere in the codebase so analytics queries
can rely on the ``objects`` manager to hide tombstones.
"""

# Django imports
from django.conf import settings
from django.db import models


# Module imports
from .base import BaseModel


class Dashboard(BaseModel):
    """A workspace dashboard.

    Spec §27.1: holds the dashboard definition. Project scope lives on the
    ``DashboardProject`` join table; sharing state on ``DashboardMemberAccess``;
    per-user favorites on ``DashboardFavorite``.
    """

    VISIBILITY_WORKSPACE = "workspace"
    VISIBILITY_PRIVATE = "private"

    VISIBILITY_CHOICES = (
        (VISIBILITY_WORKSPACE, "Workspace"),
        (VISIBILITY_PRIVATE, "Private"),
    )

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="dashboards",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_dashboards",
    )
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PRIVATE,
    )
    filters = models.JSONField(default=dict, blank=True)
    pql = models.TextField(blank=True, null=True)
    default_time_scope = models.JSONField(default=dict, blank=True)
    comparison = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        db_table = "dashboards"
        ordering = ("-created_at",)
        indexes = [
            # §40.3 dashboard scope lookup: most "list dashboards" queries
            # ask for non-deleted dashboards owned by a given workspace, often
            # filtered further by visibility.
            models.Index(
                fields=["workspace", "deleted_at"],
                name="dashboard_ws_scope_idx",
            ),
            models.Index(
                fields=["workspace", "visibility", "deleted_at"],
                name="dashboard_ws_visibility_idx",
            ),
            models.Index(
                fields=["owner", "deleted_at"],
                name="dashboard_owner_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} <{self.workspace.name}>"

    # ------------------------------------------------------------------
    # Spec §28 permission helpers (model layer only).
    #
    # The engine-level ACL resolution that decides which underlying work-item
    # data a viewer can see lives in the analytics query layer (RD-451). At
    # the dashboard-model layer we only encode dashboard-level access so the
    # future API/views can call these helpers without re-deriving the rules.
    # ------------------------------------------------------------------

    def is_workspace_visible(self) -> bool:
        return self.visibility == self.VISIBILITY_WORKSPACE

    def is_private(self) -> bool:
        return self.visibility == self.VISIBILITY_PRIVATE

    def can_view(self, user, *, workspace_role: int | None = None) -> bool:
        """Dashboard-level read access per spec §28.

        Workspace-visible dashboards: any active workspace member can read.
        Private dashboards: the owner, members with explicit access, and
        workspace admins/owners can read.
        """
        if user is None:
            return False

        if self.owner_id == user.id:
            return True

        if self.is_workspace_visible():
            # Active workspace members can see workspace-visible dashboards.
            # The view layer is responsible for confirming workspace membership;
            # we conservatively return True here when the caller already
            # asserts the viewer is a workspace member.
            return True

        if workspace_role is not None and workspace_role >= 20:
            return True

        return DashboardMemberAccess.objects.filter(
            dashboard=self,
            member_id=user.id,
        ).exists()

    def can_edit(self, user, *, workspace_role: int | None = None) -> bool:
        """Dashboard-level write access per spec §28.1 / §28.2."""
        if user is None:
            return False

        if self.owner_id == user.id:
            return True

        if self.is_workspace_visible() and workspace_role is not None and workspace_role >= 20:
            return True

        return DashboardMemberAccess.objects.filter(
            dashboard=self,
            member_id=user.id,
            access=DashboardMemberAccess.ACCESS_EDIT,
        ).exists()

    def can_manage(self, user) -> bool:
        """Spec §28.2: only the owner may delete, change visibility, manage
        sharing, or publish/unpublish.
        """
        if user is None:
            return False
        return self.owner_id == user.id


class DashboardProject(BaseModel):
    """Project scope join table for a dashboard (spec §27.2).

    Uses an explicit join rather than a JSON array so analytics queries can
    resolve the configured projects via SQL without table-scanning JSON.
    """

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name="dashboard_projects",
    )
    project = models.ForeignKey(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="dashboard_projects",
    )

    class Meta:
        verbose_name = "Dashboard Project"
        verbose_name_plural = "Dashboard Projects"
        db_table = "dashboard_projects"
        ordering = ("-created_at",)
        unique_together = ["dashboard", "project", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dashboard", "project"],
                condition=models.Q(deleted_at__isnull=True),
                name="dashboard_project_unique_dashboard_project_when_active",
            ),
        ]
        indexes = [
            # §40.3: project-scope join. Analytics queries pivot from project
            # to dashboard via this join, so a (project, deleted_at) lookup
            # is the dominant read path.
            models.Index(
                fields=["project", "deleted_at"],
                name="dashboard_project_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.dashboard_id}->{self.project_id}"


class DashboardWidget(BaseModel):
    """A widget rendered on a dashboard (spec §27.3).

    ``query_config`` MUST include a ``schema_version`` key; the analytics
    engine in RD-451 reads it to migrate persisted widget queries forward
    when the query shape changes.
    """

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    widget_type = models.CharField(max_length=64)
    widget_model = models.CharField(max_length=64, blank=True, default="")
    query_config = models.JSONField(default=dict)
    style_config = models.JSONField(default=dict)
    layout_config = models.JSONField(default=dict)
    inherit_time_scope = models.BooleanField(default=True)
    custom_time_scope = models.JSONField(null=True, blank=True)
    sort_order = models.FloatField(default=65535)

    class Meta:
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        db_table = "dashboard_widgets"
        ordering = ("sort_order", "-created_at")
        indexes = [
            # §40.3: widget lookup by dashboard. The batch dashboard-data
            # endpoint (spec §32.3) loads all widgets for a dashboard in one
            # query; sort_order matters for stable client rendering.
            models.Index(
                fields=["dashboard", "deleted_at", "sort_order"],
                name="dashboard_widget_lookup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} <{self.dashboard_id}>"


class DashboardMemberAccess(BaseModel):
    """Sharing row: dashboard × member × access level (spec §27.4 / §28).

    Used only for private dashboards. Workspace-visible dashboards ignore this
    table for reads (any active workspace member can see them) but the rows
    still help convey explicit Edit grants when a workspace admin/owner wants
    to mark someone with elevated write rights.
    """

    ACCESS_VIEW = "view"
    ACCESS_EDIT = "edit"

    ACCESS_CHOICES = (
        (ACCESS_VIEW, "View"),
        (ACCESS_EDIT, "Edit"),
    )

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name="member_access",
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_member_access",
    )
    access = models.CharField(
        max_length=8,
        choices=ACCESS_CHOICES,
        default=ACCESS_VIEW,
    )

    class Meta:
        verbose_name = "Dashboard Member Access"
        verbose_name_plural = "Dashboard Member Access"
        db_table = "dashboard_member_access"
        ordering = ("-created_at",)
        unique_together = ["dashboard", "member", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dashboard", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="dashboard_member_access_unique_dashboard_member_when_active",
            ),
        ]
        indexes = [
            # §40.3: lookup by member so the favorite/list endpoint can
            # filter "what does this user have access to".
            models.Index(
                fields=["member", "deleted_at"],
                name="dash_member_access_member_idx",
            ),
        ]

    def __str__(self):
        return f"{self.dashboard_id}:{self.member_id}:{self.access}"


class DashboardFavorite(BaseModel):
    """Per-user favorite row (spec §27.5 / §31).

    A user can favorite a dashboard at most once while it is active; soft
    deletion is honored so a re-favorite after an unfavorite is allowed.
    """

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_favorites",
    )

    class Meta:
        verbose_name = "Dashboard Favorite"
        verbose_name_plural = "Dashboard Favorites"
        db_table = "dashboard_favorites"
        ordering = ("-created_at",)
        unique_together = ["dashboard", "member", "deleted_at"]
        constraints = [
            # §27.5: per-user relation; enforced as a partial unique index
            # that ignores soft-deleted rows so the soft-delete cycle does
            # not collide on the constraint.
            models.UniqueConstraint(
                fields=["dashboard", "member"],
                condition=models.Q(deleted_at__isnull=True),
                name="dashboard_favorite_unique_dashboard_member_when_active",
            ),
        ]
        indexes = [
            # §40.3: favorite lookup by user. The favorites panel and any
            # "is this dashboard favorited by me?" hydration join this index.
            models.Index(
                fields=["member", "deleted_at"],
                name="dash_favorite_member_idx",
            ),
        ]

    def __str__(self):
        return f"{self.dashboard_id}:{self.member_id}"