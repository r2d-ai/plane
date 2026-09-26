# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""P0 dashboard data model migration (RD-452).

Implements the storage layer described in
``docs/workspace-dashboards-analytics-v2-spec.md`` §27. Five tables are
added; nothing on the legacy work-item tables is touched (spec §44.1).

The migration is fully additive: no backfill, no NOT NULL constraints on
existing rows, no functional changes elsewhere. It reverses cleanly via
``migrate db 0133_digest_delivery_and_preferences`` because all five new
models are owned by this migration.
"""

import django.db.models.deletion

import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0133_digest_delivery_and_preferences"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dashboard",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "visibility",
                    models.CharField(
                        choices=[("workspace", "Workspace"), ("private", "Private")],
                        default="private",
                        max_length=16,
                    ),
                ),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("pql", models.TextField(blank=True, null=True)),
                ("default_time_scope", models.JSONField(blank=True, default=dict)),
                ("comparison", models.JSONField(blank=True, default=dict)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_dashboards",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboards",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dashboard",
                "verbose_name_plural": "Dashboards",
                "db_table": "dashboards",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="dashboard",
            index=models.Index(
                fields=["workspace", "deleted_at"], name="dashboard_ws_scope_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="dashboard",
            index=models.Index(
                fields=["workspace", "visibility", "deleted_at"],
                name="dashboard_ws_visibility_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="dashboard",
            index=models.Index(fields=["owner", "deleted_at"], name="dashboard_owner_idx"),
        ),
        migrations.CreateModel(
            name="DashboardProject",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_projects",
                        to="db.dashboard",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_projects",
                        to="db.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dashboard Project",
                "verbose_name_plural": "Dashboard Projects",
                "db_table": "dashboard_projects",
                "ordering": ("-created_at",),
                "unique_together": {("dashboard", "project", "deleted_at")},
            },
        ),
        migrations.AddIndex(
            model_name="dashboardproject",
            index=models.Index(
                fields=["project", "deleted_at"],
                name="dashboard_project_lookup_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="dashboardproject",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("dashboard", "project"),
                name="dashboard_project_unique_dashboard_project_when_active",
            ),
        ),
        migrations.CreateModel(
            name="DashboardWidget",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("widget_type", models.CharField(max_length=64)),
                ("widget_model", models.CharField(blank=True, default="", max_length=64)),
                ("query_config", models.JSONField(default=dict)),
                ("style_config", models.JSONField(default=dict)),
                ("layout_config", models.JSONField(default=dict)),
                ("inherit_time_scope", models.BooleanField(default=True)),
                ("custom_time_scope", models.JSONField(blank=True, null=True)),
                ("sort_order", models.FloatField(default=65535)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="widgets",
                        to="db.dashboard",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dashboard Widget",
                "verbose_name_plural": "Dashboard Widgets",
                "db_table": "dashboard_widgets",
                "ordering": ("sort_order", "-created_at"),
            },
        ),
        migrations.AddIndex(
            model_name="dashboardwidget",
            index=models.Index(
                fields=["dashboard", "deleted_at", "sort_order"],
                name="dashboard_widget_lookup_idx",
            ),
        ),
        migrations.CreateModel(
            name="DashboardMemberAccess",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "access",
                    models.CharField(
                        choices=[("view", "View"), ("edit", "Edit")],
                        default="view",
                        max_length=8,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_access",
                        to="db.dashboard",
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_member_access",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Dashboard Member Access",
                "verbose_name_plural": "Dashboard Member Access",
                "db_table": "dashboard_member_access",
                "ordering": ("-created_at",),
                "unique_together": {("dashboard", "member", "deleted_at")},
            },
        ),
        migrations.AddIndex(
            model_name="dashboardmemberaccess",
            index=models.Index(
                fields=["member", "deleted_at"],
                name="dash_member_access_member_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="dashboardmemberaccess",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("dashboard", "member"),
                name="dashboard_member_access_unique_dashboard_member_when_active",
            ),
        ),
        migrations.CreateModel(
            name="DashboardFavorite",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Deleted At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to="db.dashboard",
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_favorites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Dashboard Favorite",
                "verbose_name_plural": "Dashboard Favorites",
                "db_table": "dashboard_favorites",
                "ordering": ("-created_at",),
                "unique_together": {("dashboard", "member", "deleted_at")},
            },
        ),
        migrations.AddIndex(
            model_name="dashboardfavorite",
            index=models.Index(
                fields=["member", "deleted_at"],
                name="dash_favorite_member_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="dashboardfavorite",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("dashboard", "member"),
                name="dashboard_favorite_unique_dashboard_member_when_active",
            ),
        ),
    ]