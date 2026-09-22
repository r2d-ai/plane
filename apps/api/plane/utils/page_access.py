# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Centralized effective-access service for Wiki pages and Collections.

This is the single deterministic algorithm the plan §8.4 asks for. Every
effective capability is derived from a fixed set of sources, in a fixed order,
so two call sites can never disagree about who may read or edit a page:

    workspace role
      + page access (public/private + owner)
      + Collection access / member role
      + parent inheritance
      + (direct PageShare, added in WIKI-06)
      = effective capabilities

Precedence (open question Q8, recorded in the WIKI-05 PR description):

* A **private Collection is a mandatory boundary**: it gates the whole subtree
  resolved through the Page hierarchy and cannot be bypassed by the workspace
  role, the page owner or Company Wiki open-read. Only the designated
  workspace's admin/owner bypass it.
* Inside a boundary the effective capability is the **most restrictive** of the
  Collection role and the workspace baseline (spec §19.1).
* Company Wiki (the workspace designated by ``COMPANY_WIKI_WORKSPACE_SLUG``)
  grants authenticated active users ``VIEW`` when ``COMPANY_WIKI_OPEN_READ`` is
  true. Open-read is a read-only ceiling: it never grants COMMENT/EDIT and never
  opens a private Collection.
* No Collection membership means the page inherits its nearest ancestor's
  Collection; a page without any Collection boundary keeps the pre-existing
  Workspace Wiki behaviour.

A direct PageShare source is intentionally absent until WIKI-06 and must be
layered in here, not in a second implementation.
"""

from __future__ import annotations

from enum import IntEnum

from django.conf import settings

from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionMember,
    PageCollectionPage,
    WorkspaceMember,
)

ADMIN = 20
MEMBER = 15
GUEST = 5

WORKSPACE_READ_ROLES = {ADMIN, MEMBER, GUEST}
WORKSPACE_WRITE_ROLES = {ADMIN, MEMBER}


class Capability(IntEnum):
    """Effective capability for a (user, page) pair, ordered by strength."""

    NONE = 0
    VIEW = 1
    COMMENT = 2
    EDIT = 3


_COLLECTION_ROLE_TO_CAPABILITY = {
    PageCollection.ROLE_VIEW: Capability.VIEW,
    PageCollection.ROLE_COMMENT: Capability.COMMENT,
    PageCollection.ROLE_EDIT: Capability.EDIT,
}

_UNSET = object()


def _is_active_user(user):
    return user is not None and getattr(user, "is_authenticated", False) and getattr(user, "is_active", False)


def is_company_wiki_workspace(workspace):
    """True when ``workspace`` is the designated Company Wiki workspace."""
    if workspace is None:
        return False
    return bool(settings.COMPANY_WIKI_WORKSPACE_SLUG) and workspace.slug == settings.COMPANY_WIKI_WORKSPACE_SLUG


def company_wiki_open_read(workspace):
    """True when the designated Company Wiki workspace is open for read."""
    return bool(settings.COMPANY_WIKI_OPEN_READ) and is_company_wiki_workspace(workspace)


def resolve_workspace_role(workspace_id, user_id):
    """Return the active workspace role for ``user_id`` or ``None``."""
    if not workspace_id or not user_id:
        return None
    return (
        WorkspaceMember.objects.filter(
            workspace_id=workspace_id,
            member_id=user_id,
            is_active=True,
        )
        .values_list("role", flat=True)
        .first()
    )


def is_workspace_admin(workspace, user, *, workspace_role=_UNSET):
    """Admin role or workspace owner. This is the only private-Collection bypass."""
    if not _is_active_user(user):
        return False
    if workspace is not None and workspace.owner_id == user.id:
        return True
    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, user.id)
    return workspace_role == ADMIN


def can_manage_collections(workspace, user, *, workspace_role=_UNSET):
    """Whether ``user`` may create/update/delete Collections in ``workspace``.

    Collections are an authorization boundary, not just UI grouping (spec §19),
    so management is reserved for the workspace admin/owner. This is stricter
    than, and therefore also satisfies, the plan §8.4 Company Wiki rule
    ("manageable only by designated workspace admin/owner").
    """
    if not _is_active_user(user):
        return False
    if workspace is None:
        return False
    if workspace.owner_id == user.id:
        return True
    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, user.id)
    return workspace_role == ADMIN


def collection_member_role(collection, user):
    """Explicit Collection member role for ``user`` or ``None``."""
    if not _is_active_user(user):
        return None
    return (
        PageCollectionMember.objects.filter(
            collection=collection,
            member=user,
            deleted_at__isnull=True,
        )
        .values_list("role", flat=True)
        .first()
    )


def collection_capability(user, collection, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET):
    """Capability granted by a Collection alone (before page-level rules)."""
    if not _is_active_user(user):
        return Capability.NONE
    if workspace is None:
        workspace = collection.workspace
    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, user.id)
    if open_read is _UNSET:
        open_read = company_wiki_open_read(workspace)

    if is_workspace_admin(workspace, user, workspace_role=workspace_role):
        return Capability.EDIT

    role = collection_member_role(collection, user)
    if role in _COLLECTION_ROLE_TO_CAPABILITY:
        return _COLLECTION_ROLE_TO_CAPABILITY[role]

    if collection.access == PageCollection.ACCESS_PUBLIC:
        if workspace_role in WORKSPACE_READ_ROLES:
            return Capability.VIEW
        if open_read:
            return Capability.VIEW

    return Capability.NONE


def nearest_collection(page, *, resolver=None):
    """Resolve the nearest ancestor-or-self Collection boundary for ``page``.

    Walking stops at the first explicit membership, so a descendant inherits its
    closest ancestor's Collection. Cycles are guarded with a visited set.
    """
    if page is None:
        return None
    if resolver is not None:
        return resolver.resolve(page)
    visited = set()
    current = page
    while current is not None:
        if current.pk in visited:
            return None
        visited.add(current.pk)
        association = (
            PageCollectionPage.objects.filter(page_id=current.pk, deleted_at__isnull=True)
            .select_related("collection")
            .first()
        )
        if association is not None and association.collection.deleted_at is None:
            return association.collection
        if current.parent_id is None:
            return None
        current = Page.objects.filter(pk=current.parent_id).select_related("workspace").first()
    return None


def effective_capability(user, page, workspace, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """The single effective-capability algorithm (plan §8.4, spec §19.1)."""
    if not _is_active_user(user):
        return Capability.NONE
    if workspace is None:
        workspace = page.workspace
    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, user.id)
    if open_read is _UNSET:
        open_read = company_wiki_open_read(workspace)

    is_admin = is_workspace_admin(workspace, user, workspace_role=workspace_role)
    is_owner = page.owned_by_id == user.id

    collection = nearest_collection(page, resolver=resolver)
    collection_cap = Capability.NONE
    if collection is not None:
        collection_cap = collection_capability(
            user,
            collection,
            workspace,
            workspace_role=workspace_role,
            open_read=open_read,
        )

    # 1. Private Collection is a mandatory boundary for the whole subtree.
    if collection is not None and collection.is_private and not is_admin and collection_cap == Capability.NONE:
        return Capability.NONE

    # 2. Page-level privacy still requires ownership (direct PageShare: WIKI-06).
    if page.access == Page.PRIVATE_ACCESS and not is_owner and not is_admin:
        return Capability.NONE

    # 3. Workspace baseline.
    if is_admin:
        base = Capability.EDIT
    elif workspace_role in WORKSPACE_WRITE_ROLES:
        base = Capability.EDIT
    elif workspace_role == GUEST:
        base = Capability.VIEW
    else:
        base = Capability.NONE

    if collection is None:
        if base == Capability.NONE and open_read:
            return Capability.VIEW
        return base

    if collection.is_private:
        if collection_cap == Capability.NONE:
            return Capability.NONE
        if base == Capability.NONE:
            return collection_cap
        # Most restrictive wins inside the boundary.
        return Capability(min(int(base), int(collection_cap)))

    # Public Collection: grouping only, but an explicit role may raise COMMENTS.
    result = Capability(max(int(base), int(collection_cap)))
    if result == Capability.NONE and open_read:
        return Capability.VIEW
    return result


class PageAccessResolver:
    """Bulk Collection resolver that avoids an N+1 walk per page.

    Endpoints that render a page list build one resolver for the workspace, and
    the "no private collection" fast path in the view skips the whole thing when
    collections are not in use.
    """

    def __init__(self, workspace_id):
        self.workspace_id = workspace_id
        self._explicit = None
        self._parents = None
        self._cache = {}

    def _load(self):
        if self._explicit is not None:
            return
        collections = {
            collection.id: collection
            for collection in PageCollection.objects.filter(workspace_id=self.workspace_id, deleted_at__isnull=True)
        }
        self._explicit = {
            row["page_id"]: collections.get(row["collection"])
            for row in PageCollectionPage.objects.filter(
                workspace_id=self.workspace_id,
                deleted_at__isnull=True,
            ).values("page_id", "collection")
        }
        self._parents = dict(Page.objects.filter(workspace_id=self.workspace_id).values_list("id", "parent_id"))

    def resolve(self, page):
        self._load()
        return self._resolve_id(page.pk, set())

    def resolve_id(self, page_id):
        self._load()
        return self._resolve_id(page_id, set())

    def _resolve_id(self, page_id, seen):
        if page_id is None or page_id in seen:
            return None
        if page_id in self._cache:
            return self._cache[page_id]
        seen.add(page_id)
        collection = self._explicit.get(page_id)
        if collection is None:
            collection = self._resolve_id(self._parents.get(page_id), seen)
        self._cache[page_id] = collection
        return collection

    def descendants(self, page_id):
        """Page ids in the subtree rooted at ``page_id`` (the page included)."""
        self._load()
        children = {}
        for child_id, parent_id in self._parents.items():
            children.setdefault(parent_id, []).append(child_id)
        result = []
        stack = [page_id]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            result.append(current)
            stack.extend(children.get(current, []))
        return result


def hidden_page_ids(workspace, user, *, workspace_role=None):
    """Page ids a user must not see because of private Collection boundaries.

    Returns an empty set (and does no extra work) when the workspace has no
    private Collection, so the pre-Collections Wiki page list keeps its exact
    query plan and performance.
    """
    if not PageCollection.objects.filter(
        workspace=workspace, access=PageCollection.ACCESS_PRIVATE, deleted_at__isnull=True
    ).exists():
        return set()

    if workspace_role is None:
        workspace_role = resolve_workspace_role(workspace.id, getattr(user, "id", None))
    if is_workspace_admin(workspace, user, workspace_role=workspace_role):
        return set()

    accessible = set(
        PageCollectionMember.objects.filter(
            workspace=workspace,
            member=user,
            deleted_at__isnull=True,
        ).values_list("collection_id", flat=True)
    )

    resolver = PageAccessResolver(workspace.id)
    hidden = set()
    for page_id in Page.objects.filter(workspace=workspace, is_global=True, deleted_at__isnull=True).values_list(
        "id", flat=True
    ):
        collection = resolver.resolve_id(page_id)
        if collection is not None and collection.is_private and collection.id not in accessible:
            hidden.add(page_id)
    return hidden
