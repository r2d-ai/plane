# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .workspace import (
    WorkSpaceBasePermission,
    WorkspaceOwnerPermission,
    WorkSpaceAdminPermission,
    WorkspaceEntityPermission,
    WorkspaceViewerPermission,
    WorkspaceUserPermission,
    WorkspaceMemberPermission,
)
from .project import (
    ProjectBasePermission,
    ProjectEntityPermission,
    ProjectMemberPermission,
    ProjectLitePermission,
    ProjectAdminPermission,
)
from .base import allow_permission, ROLE
from .page import ProjectPagePermission
from .workspace_page import WorkspacePagePermission
from .page_collection import PageCollectionPermission
from .page_template import PageTemplatePermission
from .dashboard import DashboardPermission, WorkspaceDashboardsEnabled
