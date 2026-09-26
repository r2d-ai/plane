# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.dashboard.base import (
    DashboardDataEndpoint,
    DashboardDetailEndpoint,
    DashboardDuplicateEndpoint,
    DashboardFavoriteEndpoint,
    DashboardLayoutEndpoint,
    DashboardListCreateEndpoint,
    DashboardMemberDetailEndpoint,
    DashboardMemberListCreateEndpoint,
    DashboardWidgetDetailEndpoint,
    DashboardWidgetDrilldownEndpoint,
    DashboardWidgetExportEndpoint,
    DashboardWidgetListCreateEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/dashboards/",
        DashboardListCreateEndpoint.as_view(),
        name="workspace-dashboards",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/",
        DashboardDetailEndpoint.as_view(),
        name="workspace-dashboard-detail",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/duplicate/",
        DashboardDuplicateEndpoint.as_view(),
        name="workspace-dashboard-duplicate",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/",
        DashboardWidgetListCreateEndpoint.as_view(),
        name="workspace-dashboard-widgets",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/<uuid:widget_id>/",
        DashboardWidgetDetailEndpoint.as_view(),
        name="workspace-dashboard-widget-detail",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/layout/",
        DashboardLayoutEndpoint.as_view(),
        name="workspace-dashboard-layout",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/favorite/",
        DashboardFavoriteEndpoint.as_view(),
        name="workspace-dashboard-favorite",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/data/",
        DashboardDataEndpoint.as_view(),
        name="workspace-dashboard-data",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/<uuid:widget_id>/drilldown/",
        DashboardWidgetDrilldownEndpoint.as_view(),
        name="workspace-dashboard-widget-drilldown",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/widgets/<uuid:widget_id>/export/",
        DashboardWidgetExportEndpoint.as_view(),
        name="workspace-dashboard-widget-export",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/members/",
        DashboardMemberListCreateEndpoint.as_view(),
        name="workspace-dashboard-members",
    ),
    path(
        "workspaces/<str:slug>/dashboards/<uuid:dashboard_id>/members/<uuid:member_id>/",
        DashboardMemberDetailEndpoint.as_view(),
        name="workspace-dashboard-member-detail",
    ),
]
