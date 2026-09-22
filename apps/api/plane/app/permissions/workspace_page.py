# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permission class for Workspace Wiki pages (Company Wiki included).

Wiki pages are ordinary ``Page`` rows with ``is_global=True`` living in a real
workspace (spec §6, §29). This class never reuses ``ProjectPagePermission``:
membership is workspace-scoped and every lookup is scoped by workspace slug +
``is_global=True`` + not-deleted so a page UUID cannot be resolved outside the
URL workspace (BOLA/IDOR invariant, spec §6.2).

Company Wiki is the same Workspace Wiki on the workspace designated by
``COMPANY_WIKI_WORKSPACE_SLUG``. ``COMPANY_WIKI_OPEN_READ`` adds a read-only
override for authenticated active non-members of that workspace; it never
grants write, lock, archive or manage.
"""

from django.conf import settings

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, SAFE_METHODS

from plane.db.models import Page, Workspace, WorkspaceMember

from plane.app.permissions import ROLE


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
}
# Actions that mutate the page but are allowed to members as well as admins.
WRITE_ACTIONS = {
    "create",
    "update",
    "partial_update",
    "access",
    "lock",
    "unlock",
    "archive",
    "unarchive",
    "duplicate",
    "description_update",
    "favorite_create",
    "favorite_destroy",
}
# Destructive actions reserved for workspace admins (page owners may still
# delete their own archived page; enforced in the view).
ADMIN_ACTIONS = {"destroy"}


class WorkspacePagePermission(BasePermission):
    """Workspace-scoped permission for Wiki pages (spec §6)."""

    message = "You don't have the required permissions."

    def has_permission(self, request, view):
        if request.user.is_anonymous or not request.user.is_active:
            return False

        slug = view.kwargs.get("slug")
        if not slug:
            return False

        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return False

        role = (
            WorkspaceMember.objects.filter(
                workspace=workspace,
                member=request.user,
                is_active=True,
            )
            .values_list("role", flat=True)
            .first()
        )

        action = getattr(view, "action", None)
        method = request.method

        if action in READ_ACTIONS or (action is None and method in SAFE_METHODS):
            if role in READ_ROLES:
                allowed = True
            elif self._is_open_read(slug):
                # Read-only override for the designated Company Wiki workspace.
                allowed = True
            else:
                return False
        elif action in ADMIN_ACTIONS or (action is None and method == "DELETE"):
            # Deleting an archived Wiki page stays with workspace admins.
            allowed = role == ADMIN
        elif action in WRITE_ACTIONS or method not in SAFE_METHODS:
            # Membership is required for every write; open-read never weakens it.
            allowed = role in WRITE_ROLES
        else:
            allowed = False

        if not allowed:
            return False

        page_id = view.kwargs.get("page_id")
        if page_id:
            return self._check_page_scope(request, workspace, page_id)
        return True

    @staticmethod
    def _is_open_read(slug):
        return bool(settings.COMPANY_WIKI_OPEN_READ and settings.COMPANY_WIKI_WORKSPACE_SLUG) and (
            slug == settings.COMPANY_WIKI_WORKSPACE_SLUG
        )

    @staticmethod
    def _check_page_scope(request, workspace, page_id):
        """Resolve the page inside the URL workspace and apply private-page rules.

        A page that is not a Wiki page of the URL workspace is reported as
        not-found so a foreign UUID cannot be probed. A private page not owned
        by the requesting user is treated as nonexistent (spec §6.5).
        """
        page = Page.objects.filter(
            id=page_id,
            workspace=workspace,
            is_global=True,
            deleted_at__isnull=True,
        ).first()
        if page is None:
            raise NotFound("Page not found")

        if page.access == Page.PRIVATE_ACCESS and page.owned_by_id != request.user.id:
            raise NotFound("Page not found")

        return True
