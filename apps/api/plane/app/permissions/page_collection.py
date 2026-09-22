# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permission class for Wiki Collections (WIKI-05, spec §5.5 / §19).

Collections are workspace-scoped. Read is allowed to any active workspace
member (or to authenticated users when the designated Company Wiki workspace
has ``COMPANY_WIKI_OPEN_READ``). Management is reserved for workspace
admin/owner — and, for the designated Company Wiki workspace, *only*
admin/owner (plan §8.4).

The class only authorizes the action; every row lookup is additionally scoped
to the URL workspace by the view so a foreign Collection UUID cannot be probed
(BOLA/IDOR invariant, spec §6.2).
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.db.models import Workspace

from plane.utils.page_access import (
    can_manage_collections,
    company_wiki_open_read,
    resolve_workspace_role,
)

READ_ACTIONS = {"list", "retrieve", "members", "pages"}
MANAGE_ACTIONS = {
    "create",
    "update",
    "partial_update",
    "destroy",
    "reorder",
    "member_add",
    "member_update",
    "member_remove",
    "page_add",
    "page_move",
    "page_remove",
    "page_reorder",
}


class PageCollectionPermission(BasePermission):
    """Workspace-scoped permission for Collections."""

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
            if role is not None:
                return True
            return company_wiki_open_read(workspace)

        if action in MANAGE_ACTIONS or (action is None and method not in SAFE_METHODS):
            return can_manage_collections(workspace, user, workspace_role=role)

        return False
