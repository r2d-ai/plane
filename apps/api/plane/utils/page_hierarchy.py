# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Server-side Page hierarchy validation shared across Page scopes.

Project Pages (``is_global=False``) and Wiki pages (``is_global=True``, with or
without a ``ProjectPage`` link) share one ``Page`` table and one ``parent``
self-relation. The guard below keeps the tree consistent no matter which scope
creates or reparents a page:

- a page cannot be its own parent;
- the parent must exist and not be soft-deleted;
- project and Wiki pages cannot be nested together;
- the parent must belong to the same workspace;
- the parent cannot be the page itself or one of its descendants (no cycles).

It is intentionally scope-agnostic: callers resolve the candidate parent within
their own scope (project, workspace Wiki, ...) and then hand the resolved
instance to :func:`validate_page_parent`.
"""

from plane.db.models import Page
from plane.utils.page_access import can_edit_page


class PageHierarchyError(Exception):
    """Raised when a parent assignment would break a hierarchy invariant."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _is_self_or_descendant(candidate_parent, page):
    """Return True when ``candidate_parent`` is ``page`` or a descendant of it.

    Walks the existing ancestor chain of ``candidate_parent`` upwards with a
    visited set so a malformed legacy cycle cannot loop forever. A repeated node
    means the existing tree is already corrupt; treat it as a rejection rather
    than attaching another page to it.
    """
    if page.pk is None:
        return False

    current = candidate_parent
    seen = set()
    while current is not None:
        if current.pk == page.pk:
            return True
        if current.pk in seen:
            return True
        seen.add(current.pk)
        if current.parent_id is None:
            return False
        try:
            current = current.parent
        except Page.DoesNotExist:
            return False
    return False


def validate_page_parent(page, parent, *, user=None, workspace=None):
    """Validate assigning ``parent`` as ``page.parent``.

    ``page`` may be unsaved (creation) or an existing instance; ``parent`` is a
    resolved ``Page`` instance or ``None`` to detach the page from the tree.
    Raises :class:`PageHierarchyError` with a stable ``code`` on failure.

    When ``user`` is supplied, the caller must hold edit capability on
    ``parent``; failure is reported as ``PAGE_PARENT_NOT_FOUND`` so a parent the
    actor cannot edit is indistinguishable from a missing parent (spec §6.5).
    """
    if parent is None:
        return

    if user is not None:
        ws = workspace
        if ws is None:
            ws = getattr(page, "workspace", None) or parent.workspace
        if not can_edit_page(user, parent, ws):
            raise PageHierarchyError("PAGE_PARENT_NOT_FOUND", "Parent page does not exist.")

    if page.pk is not None and parent.pk == page.pk:
        raise PageHierarchyError("PAGE_SELF_PARENT", "A page cannot be its own parent.")

    if parent.deleted_at is not None:
        raise PageHierarchyError("PAGE_PARENT_DELETED", "Parent page does not exist.")

    if page.workspace_id is not None and parent.workspace_id != page.workspace_id:
        raise PageHierarchyError(
            "PAGE_PARENT_CROSS_WORKSPACE",
            "Parent page must belong to the same workspace.",
        )

    if bool(parent.is_global) != bool(page.is_global):
        raise PageHierarchyError(
            "PAGE_PARENT_CROSS_SCOPE",
            "Project pages and Wiki pages cannot be nested together.",
        )

    if _is_self_or_descendant(parent, page):
        raise PageHierarchyError(
            "PAGE_PARENT_CYCLE",
            "Parent page cannot be the page itself or one of its descendants.",
        )
