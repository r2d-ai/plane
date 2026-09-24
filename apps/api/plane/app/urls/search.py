# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import GlobalSearchEndpoint, IssueSearchEndpoint, SearchEndpoint
from plane.app.views import UnifiedWikiScopesEndpoint, UnifiedWikiSearchEndpoint, UnifiedWikiPersonalPagesEndpoint


urlpatterns = [
    path("wiki/scopes/", UnifiedWikiScopesEndpoint.as_view(), name="unified-wiki-scopes"),
    path("wiki/search/", UnifiedWikiSearchEndpoint.as_view(), name="unified-wiki-search"),
    path("wiki/personal/", UnifiedWikiPersonalPagesEndpoint.as_view(), name="unified-wiki-personal"),
    path(
        "workspaces/<str:slug>/search/",
        GlobalSearchEndpoint.as_view(),
        name="global-search",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/search-issues/",
        IssueSearchEndpoint.as_view(),
        name="project-issue-search",
    ),
    path(
        "workspaces/<str:slug>/entity-search/",
        SearchEndpoint.as_view(),
        name="entity-search",
    ),
]
