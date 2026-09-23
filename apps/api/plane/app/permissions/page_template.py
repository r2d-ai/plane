# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permission class for workspace-scoped page templates (spec §16; plan §10.1).

Templates are a workspace authoring surface:

* read is available to any active workspace member;
* create/use (instantiate) is available to workspace admin/member;
* update/delete is reserved for the workspace admin/owner or the template
  creator, and is additionally enforced object-side by the view.

The class only authorizes the action; every row lookup is additionally scoped
to the URL workspace by the view so a foreign template UUID cannot be probed
(BOLA/IDOR invariant, spec §6.2).
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.db.models import Workspace

from plane.utils.page_access import (
    WORKSPACE_READ_ROLES,
    WORKSPACE_WRITE_ROLES,
    resolve_workspace_role,
)

READ_ACTIONS = {"list", "retrieve"}
CREATE_ACTIONS = {"create", "create_page"}
MANAGE_ACTIONS = {"update", "partial_update", "destroy"}


class PageTemplatePermission(BasePermission):
    """Workspace-scoped permission for page templates."""

    message = "You don't have the required permissions."

    def has_permission(self, request, view):
        user = request.user
        if user.is_anonymous or not user.is_active:
            return False

        slug = view.kwargs.get("slug")
        if not slug:
            return False

        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return False

        role = resolve_workspace_role(workspace.id, user.id)
        action = getattr(view, "action", None)
        method = request.method

        if action in READ_ACTIONS or (action is None and method in SAFE_METHODS):
            return role in WORKSPACE_READ_ROLES

        if action in CREATE_ACTIONS or (action is None and method == "POST"):
            return role in WORKSPACE_WRITE_ROLES

        if action in MANAGE_ACTIONS or (action is None and method not in SAFE_METHODS):
            # Object ownership is checked in the view; here a member/admin is
            # required and the view narrows it down to owner-or-admin.
            return role in WORKSPACE_WRITE_ROLES

        return False
