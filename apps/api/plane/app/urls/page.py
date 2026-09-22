# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path


from plane.app.views import (
    PageViewSet,
    PageFavoriteViewSet,
    PagesDescriptionViewSet,
    PageVersionEndpoint,
    PageDuplicateEndpoint,
    WorkspacePageViewSet,
    WorkspacePagesDescriptionViewSet,
    WorkspacePageFavoriteViewSet,
    WorkspacePageDuplicateEndpoint,
    WorkspacePageVersionEndpoint,
    PageCollectionViewSet,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages-summary/",
        PageViewSet.as_view({"get": "summary"}),
        name="project-pages-summary",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/",
        PageViewSet.as_view({"get": "list", "post": "create"}),
        name="project-pages",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/",
        PageViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-pages",
    ),
    # favorite pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/favorite-pages/<uuid:page_id>/",
        PageFavoriteViewSet.as_view({"post": "create", "delete": "destroy"}),
        name="user-favorite-pages",
    ),
    # archived pages
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/archive/",
        PageViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="project-page-archive-unarchive",
    ),
    # lock and unlock
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/lock/",
        PageViewSet.as_view({"post": "lock", "delete": "unlock"}),
        name="project-pages-lock-unlock",
    ),
    # private and public page
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/access/",
        PageViewSet.as_view({"post": "access"}),
        name="project-pages-access",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/description/",
        PagesDescriptionViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="page-description",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/versions/<uuid:pk>/",
        PageVersionEndpoint.as_view(),
        name="page-versions",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/pages/<uuid:page_id>/duplicate/",
        PageDuplicateEndpoint.as_view(),
        name="page-duplicate",
    ),
    # Workspace Wiki / Company Wiki pages. Company Wiki reuses these routes
    # against the workspace designated by COMPANY_WIKI_WORKSPACE_SLUG (spec §29.6).
    path(
        "workspaces/<str:slug>/pages/",
        WorkspacePageViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-pages",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/",
        WorkspacePageViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="workspace-page",
    ),
    # Direct named-user sharing (WIKI-06). Names are sensitive access metadata,
    # so both endpoints require the MANAGE capability (page owner / admin).
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/shares/",
        WorkspacePageViewSet.as_view({"get": "share_list", "post": "share_add"}),
        name="workspace-page-shares",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/shares/<uuid:share_id>/",
        WorkspacePageViewSet.as_view({"patch": "share_update", "delete": "share_remove"}),
        name="workspace-page-share",
    ),
    path(
        "workspaces/<str:slug>/favorite-pages/<uuid:page_id>/",
        WorkspacePageFavoriteViewSet.as_view({"post": "favorite_create", "delete": "favorite_destroy"}),
        name="workspace-favorite-pages",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/archive/",
        WorkspacePageViewSet.as_view({"post": "archive", "delete": "unarchive"}),
        name="workspace-page-archive-unarchive",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/lock/",
        WorkspacePageViewSet.as_view({"post": "lock", "delete": "unlock"}),
        name="workspace-page-lock-unlock",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/access/",
        WorkspacePageViewSet.as_view({"post": "access", "patch": "access"}),
        name="workspace-page-access",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/description/",
        WorkspacePagesDescriptionViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="workspace-page-description",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/versions/",
        WorkspacePageVersionEndpoint.as_view(),
        name="workspace-page-versions",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/versions/<uuid:pk>/",
        WorkspacePageVersionEndpoint.as_view(),
        name="workspace-page-versions",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/duplicate/",
        WorkspacePageDuplicateEndpoint.as_view(),
        name="workspace-page-duplicate",
    ),
    # Collections (WIKI-05). Same routes serve Workspace Wiki and the
    # designated Company Wiki workspace.
    path(
        "workspaces/<str:slug>/page-collections/",
        PageCollectionViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-page-collections",
    ),
    path(
        "workspaces/<str:slug>/page-collections/reorder/",
        PageCollectionViewSet.as_view({"patch": "reorder"}),
        name="workspace-page-collections-reorder",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/",
        PageCollectionViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="workspace-page-collection",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/members/",
        PageCollectionViewSet.as_view({"get": "members", "post": "member_add"}),
        name="workspace-page-collection-members",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/members/<uuid:member_id>/",
        PageCollectionViewSet.as_view({"patch": "member_update", "delete": "member_remove"}),
        name="workspace-page-collection-member",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/pages/",
        PageCollectionViewSet.as_view({"get": "pages", "post": "page_add", "patch": "page_reorder"}),
        name="workspace-page-collection-pages",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/pages/<uuid:page_id>/",
        PageCollectionViewSet.as_view({"post": "page_move", "patch": "page_move", "delete": "page_remove"}),
        name="workspace-page-collection-page",
    ),
]
