# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views import (
    WikiPageDetailAPIEndpoint,
    WikiPageLifecycleAPIEndpoint,
    WikiPageListAPIEndpoint,
)


urlpatterns = [
    path(
        "workspaces/<str:slug>/wiki/pages/",
        WikiPageListAPIEndpoint.as_view(http_method_names=["get", "post"]),
        name="api-wiki-pages",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/",
        WikiPageDetailAPIEndpoint.as_view(http_method_names=["get", "patch"]),
        name="api-wiki-page-detail",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/archive/",
        WikiPageLifecycleAPIEndpoint.as_view(http_method_names=["post"]),
        {"action": "archive"},
        name="api-wiki-page-archive",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/unarchive/",
        WikiPageLifecycleAPIEndpoint.as_view(http_method_names=["post"]),
        {"action": "unarchive"},
        name="api-wiki-page-unarchive",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/lock/",
        WikiPageLifecycleAPIEndpoint.as_view(http_method_names=["post"]),
        {"action": "lock"},
        name="api-wiki-page-lock",
    ),
    path(
        "workspaces/<str:slug>/wiki/pages/<uuid:page_id>/unlock/",
        WikiPageLifecycleAPIEndpoint.as_view(http_method_names=["post"]),
        {"action": "unlock"},
        name="api-wiki-page-unlock",
    ),
]
