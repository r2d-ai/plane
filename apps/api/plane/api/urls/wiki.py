# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import WikiPageDetailAPIEndpoint, WikiPageListAPIEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/wiki/pages/",
        WikiPageListAPIEndpoint.as_view(http_method_names=["get"]),
        name="api-wiki-pages",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/",
        WikiPageDetailAPIEndpoint.as_view(http_method_names=["get"]),
        name="api-wiki-page-detail",
    ),
]
