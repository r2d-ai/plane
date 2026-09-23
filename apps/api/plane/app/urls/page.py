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
    WorkspacePageExportEndpoint,
    PageCollectionViewSet,
    PageCommentViewSet,
    PageAnalyticsViewSet,
    PageCollectionAnalyticsViewSet,
    PagePublishViewSet,
    PageTemplateViewSet,
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
    # Nested export: root page + permitted descendants as a ZIP (WIKI-07c, §17.2).
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/export/",
        WorkspacePageExportEndpoint.as_view(),
        name="workspace-page-export",
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
    # Page comments (WIKI-06b, spec §5.4, §14).
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/comments/",
        PageCommentViewSet.as_view({"get": "comment_list", "post": "comment_create"}),
        name="workspace-page-comments",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/comments/<uuid:comment_id>/",
        PageCommentViewSet.as_view({"patch": "comment_update", "delete": "comment_destroy"}),
        name="workspace-page-comment",
    ),
    # Comment moderation (WIKI-09b §12.5): hide/unhide, workspace admin only.
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/comments/<uuid:comment_id>/hide/",
        PageCommentViewSet.as_view({"post": "comment_hide", "delete": "comment_unhide"}),
        name="workspace-page-comment-hide",
    ),
    # Page/Collection analytics (WIKI-09b §12.3).
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/views/",
        PageAnalyticsViewSet.as_view({"post": "record_view"}),
        name="workspace-page-view-record",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/analytics/",
        PageAnalyticsViewSet.as_view({"get": "analytics"}),
        name="workspace-page-analytics",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/analytics/export/",
        PageAnalyticsViewSet.as_view({"get": "analytics_export"}),
        name="workspace-page-analytics-export",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/analytics/",
        PageCollectionAnalyticsViewSet.as_view({"get": "analytics"}),
        name="workspace-page-collection-analytics",
    ),
    path(
        "workspaces/<str:slug>/page-collections/<uuid:collection_id>/analytics/export/",
        PageCollectionAnalyticsViewSet.as_view({"get": "analytics_export"}),
        name="workspace-page-collection-analytics-export",
    ),
    # External publishing (WIKI-07b, spec §15, plan §10.2). The public
    # retrieval endpoint lives in the space app under /api/public/.
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/publish/",
        PagePublishViewSet.as_view({"get": "publish_state", "post": "publish"}),
        name="workspace-page-publish",
    ),
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/publish/<uuid:publish_id>/",
        PagePublishViewSet.as_view({"delete": "publish_revoke"}),
        name="workspace-page-publish-revoke",
    ),
    # Page templates (WIKI-07a, spec §16). Workspace-scoped snapshots reused to
    # create Wiki pages; same routes serve the designated Company Wiki workspace.
    path(
        "workspaces/<str:slug>/page-templates/",
        PageTemplateViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-page-templates",
    ),
    path(
        "workspaces/<str:slug>/page-templates/<uuid:template_id>/",
        PageTemplateViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="workspace-page-template",
    ),
    path(
        "workspaces/<str:slug>/page-templates/<uuid:template_id>/use/",
        PageTemplateViewSet.as_view({"post": "create_page"}),
        name="workspace-page-template-use",
    ),
    # Snapshot an existing Wiki page as a template.
    path(
        "workspaces/<str:slug>/pages/<uuid:page_id>/save-as-template/",
        WorkspacePageViewSet.as_view({"post": "save_as_template"}),
        name="workspace-page-save-as-template",
    ),
]
