# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permission class for Workspace Wiki pages (Company Wiki included).

Wiki pages are ordinary ``Page`` rows with ``is_global=True`` living in a real
workspace (spec §6, §29). This class never reuses ``ProjectPagePermission``:
membership is workspace-scoped and every lookup is scoped by workspace slug +
``is_global=True`` + not-deleted so a page UUID cannot be resolved outside the
URL workspace (BOLA/IDOR invariant, spec §6.2).

The action -> capability mapping is the *only* page authorization policy in the
backend: every decision delegates to :func:`get_page_capabilities` /
:func:`can_manage_page` (WIKI-06, plan §9.2), so REST, search, realtime (which
calls REST), comments and assets can never drift apart.

Company Wiki is the same Workspace Wiki on the workspace designated by
``COMPANY_WIKI_WORKSPACE_SLUG``. ``COMPANY_WIKI_OPEN_READ`` adds a read-only
override for authenticated active non-members of that workspace; it never
grants write, lock, archive or manage.
"""

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.db.models import Page, PageComment, Workspace

from plane.app.permissions import ROLE
from plane.utils.page_access import (
    Capability,
    can_manage_page,
    company_wiki_open_read,
    get_page_capabilities,
    resolve_workspace_role,
)


ADMIN = ROLE.ADMIN.value
MEMBER = ROLE.MEMBER.value
GUEST = ROLE.GUEST.value

READ_ROLES = {ADMIN, MEMBER, GUEST}
WRITE_ROLES = {ADMIN, MEMBER}

# Actions that only read data even when the HTTP method is not safe.
READ_ACTIONS = {
    "list",
    "retrieve",
    "summary",
    "versions",
    "version_detail",
    "comment_list",
}
# Actions that add discussion without changing page content/metadata.
COMMENT_ACTIONS = {
    "comment_create",
}
# Actions that change page content/metadata and therefore need EDIT.
EDIT_ACTIONS = {
    "update",
    "partial_update",
    "description_update",
    "duplicate",
    "lock",
    "unlock",
    "archive",
    "unarchive",
    "favorite_create",
    "favorite_destroy",
    "comment_update",
    "save_as_template",
}
# Access-management actions reserved for the page owner or workspace admin.
MANAGE_ACTIONS = {
    "access",
    "share_list",
    "share_add",
    "share_update",
    "share_remove",
    "comment_destroy",
}
# Destructive actions reserved for workspace admins (page owners may still
# delete their own archived page; enforced in the view).
ADMIN_ACTIONS = {"destroy"}


class WorkspacePagePermission(BasePermission):
    """Workspace-scoped permission for Wiki pages (spec §6)."""

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
        is_read = action in READ_ACTIONS or (action is None and method in SAFE_METHODS)

        if is_read:
            # Read-only override for the designated Company Wiki workspace.
            if role is None and not company_wiki_open_read(workspace):
                return False
        elif action in ADMIN_ACTIONS or (action is None and method == "DELETE"):
            # Deleting an archived Wiki page stays with workspace admins.
            if role != ADMIN:
                return False
        else:
            # Membership is required for every write; open-read never weakens
            # it. A direct EDIT share also requires the member to be in the
            # workspace, so an anonymous/non-member can never write.
            if role is None:
                return False

        page_id = view.kwargs.get("page_id")
        if not page_id:
            # No page to scope (list/create): creation stays member/admin only.
            if not is_read and role not in WRITE_ROLES:
                return False
            return True

        return self._check_page_capability(request, workspace, page_id, role, action, method)

    @staticmethod
    def _check_page_capability(request, workspace, page_id, role, action, method):
        """Resolve the page in the URL workspace and enforce the action capability.

        A page outside the workspace/Wiki scope, or below VIEW, is reported as
        not-found so a foreign UUID cannot be probed (spec §6.2, §6.5). The
        per-action capability then distinguishes read / edit / manage.
        """
        page = (
            Page.objects.filter(
                id=page_id,
                workspace=workspace,
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )
        if page is None:
            raise NotFound("Page not found")

        capability = get_page_capabilities(request.user, page, workspace, workspace_role=role)
        if capability < Capability.VIEW:
            raise NotFound("Page not found")

        if action in ADMIN_ACTIONS or (action is None and method == "DELETE"):
            return True

        # Comment authors may edit/delete their own comments even without MANAGE.
        if action in ("comment_update", "comment_destroy"):
            comment_id = (request.parser_context.get("kwargs") or {}).get("comment_id")
            if comment_id:
                is_author = PageComment.objects.filter(
                    id=comment_id,
                    page_id=page_id,
                    actor_id=request.user.id,
                    deleted_at__isnull=True,
                ).exists()
                if is_author:
                    return True

        if action in MANAGE_ACTIONS:
            return can_manage_page(request.user, page, workspace, workspace_role=role)

        if action in COMMENT_ACTIONS:
            return capability >= Capability.COMMENT

        if action in EDIT_ACTIONS or (action is None and method not in SAFE_METHODS):
            return capability >= Capability.EDIT

        return True
