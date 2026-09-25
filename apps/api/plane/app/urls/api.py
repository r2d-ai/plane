# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path
from plane.app.views import ApiTokenEndpoint, WorkspaceServiceTokenEndpoint

urlpatterns = [
    path("users/api-tokens/", ApiTokenEndpoint.as_view(), name="api-tokens"),
    path("users/api-tokens/<uuid:pk>/", ApiTokenEndpoint.as_view(), name="api-tokens-details"),
    path(
        "workspaces/<str:slug>/service-tokens/",
        WorkspaceServiceTokenEndpoint.as_view(http_method_names=["get", "post"]),
        name="workspace-service-tokens",
    ),
    path(
        "workspaces/<str:slug>/service-tokens/<uuid:pk>/",
        WorkspaceServiceTokenEndpoint.as_view(http_method_names=["get", "patch", "delete"]),
        name="workspace-service-token-details",
    ),
]
