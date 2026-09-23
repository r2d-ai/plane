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
      + direct PageShare (inherited from the nearest shared ancestor)
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
* A direct ``PageShare`` (WIKI-06) is the nearest share on the ancestor-or-self
  chain. It grants its role on the shared page and on the subtree below it, but
  it can never bypass a private Collection boundary: the boundary check runs
  first. On a private page the share role caps the granted capability (a member
  shared ``VIEW`` gets ``VIEW``, not the member baseline).
"""

from __future__ import annotations

from enum import IntEnum

from django.conf import settings
from django.db.models import Q

from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionMember,
    PageCollectionPage,
    PageShare,
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

_SHARE_ROLE_TO_CAPABILITY = {
    PageShare.ROLE_VIEW: Capability.VIEW,
    PageShare.ROLE_COMMENT: Capability.COMMENT,
    PageShare.ROLE_EDIT: Capability.EDIT,
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


def direct_share_capability(user, page):
    """Capability granted by an explicit ``PageShare`` on ``page`` itself."""
    if not _is_active_user(user) or page is None or page.pk is None:
        return Capability.NONE
    role = (
        PageShare.objects.filter(
            page_id=page.pk,
            member=user,
            deleted_at__isnull=True,
        )
        .values_list("role", flat=True)
        .first()
    )
    return _SHARE_ROLE_TO_CAPABILITY.get(role, Capability.NONE)


def nearest_page_share(page, user, *, resolver=None):
    """Capability from the nearest ancestor-or-self explicit share.

    A share is inheritable: sharing a page also shares its subtree, so the walk
    is the exact counterpart of ``nearest_collection``. The closest ancestor
    with a share wins (most specific grant), and ``NONE`` means "no share on
    the chain".
    """
    if not _is_active_user(user) or page is None:
        return Capability.NONE
    if resolver is not None:
        return resolver.resolve_share(page, user)
    visited = set()
    current = page
    while current is not None:
        if current.pk in visited:
            return Capability.NONE
        visited.add(current.pk)
        capability = direct_share_capability(user, current)
        if capability != Capability.NONE:
            return capability
        if current.parent_id is None:
            return Capability.NONE
        current = Page.objects.filter(pk=current.parent_id).only("id", "parent_id").first()
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


def get_page_capabilities(
    user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None
):
    """The single effective-capability algorithm (plan §8.4/§9.2, spec §19.1).

    Returns the strongest ``Capability`` the user holds on ``page``. Prefer the
    ``can_view_page`` / ``can_comment_page`` / ``can_edit_page`` /
    ``can_manage_page`` predicates at call sites: they name the intended action
    and keep a single policy in one place.
    """
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

    # A share only exists between an active workspace member and the page
    # (spec §5.3); the workspace-membership gate in spec §6.3 therefore applies
    # before the share source is even consulted. The page owner keeps access
    # without a share row (spec §5.3).
    if workspace_role is not None or is_owner:
        share_cap = nearest_page_share(page, user, resolver=resolver)
    else:
        share_cap = Capability.NONE

    # 1. Private Collection is a mandatory boundary for the whole subtree. A
    #    direct share can never bypass it (spec §19.1).
    if collection is not None and collection.is_private and not is_admin and collection_cap == Capability.NONE:
        return Capability.NONE

    # 2. Page-level privacy: the owner/admin always passes; otherwise an
    #    inherited direct share is the only way in, and its role caps the
    #    capability (a member shared VIEW gets VIEW, not the member baseline).
    if page.access == Page.PRIVATE_ACCESS:
        if is_owner or is_admin:
            granted = Capability.EDIT
        elif share_cap >= Capability.VIEW:
            granted = share_cap
        else:
            return Capability.NONE
        if collection is not None and collection.is_private and not is_admin:
            # Most restrictive wins inside the boundary.
            granted = Capability(min(int(granted), int(collection_cap)))
        return granted

    # 3. Workspace baseline for a public page.
    if is_admin:
        base = Capability.EDIT
    elif workspace_role in WORKSPACE_WRITE_ROLES:
        base = Capability.EDIT
    elif workspace_role == GUEST:
        base = Capability.VIEW
    else:
        base = Capability.NONE

    if collection is None:
        result = Capability(max(int(base), int(share_cap)))
        if result == Capability.NONE and open_read:
            return Capability.VIEW
        return result

    if collection.is_private:
        if collection_cap == Capability.NONE:
            return Capability.NONE
        inner = Capability(max(int(base), int(share_cap)))
        if inner == Capability.NONE:
            return collection_cap
        # Most restrictive wins inside the boundary.
        return Capability(min(int(inner), int(collection_cap)))

    # Public Collection: grouping only, but an explicit share/role may raise
    # the capability up to COMMENTS/EDIT.
    result = Capability(max(int(base), int(collection_cap), int(share_cap)))
    if result == Capability.NONE and open_read:
        return Capability.VIEW
    return result


def effective_capability(user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """Backwards-compatible alias for :func:`get_page_capabilities`."""
    return get_page_capabilities(
        user,
        page,
        workspace,
        workspace_role=workspace_role,
        open_read=open_read,
        resolver=resolver,
    )


def _capability(user, page, workspace, threshold, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    return (
        get_page_capabilities(
            user,
            page,
            workspace,
            workspace_role=workspace_role,
            open_read=open_read,
            resolver=resolver,
        )
        >= threshold
    )


def can_view_page(user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """Whether ``user`` may read ``page`` (spec §6.4)."""
    return _capability(
        user, page, workspace, Capability.VIEW, workspace_role=workspace_role, open_read=open_read, resolver=resolver
    )


def can_comment_page(user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """Whether ``user`` may comment on ``page`` (spec §6.4)."""
    return _capability(
        user,
        page,
        workspace,
        Capability.COMMENT,
        workspace_role=workspace_role,
        open_read=open_read,
        resolver=resolver,
    )


def can_edit_page(user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """Whether ``user`` may edit ``page`` content/metadata (spec §6.4)."""
    return _capability(
        user, page, workspace, Capability.EDIT, workspace_role=workspace_role, open_read=open_read, resolver=resolver
    )


def can_manage_page(user, page, workspace=None, *, workspace_role=_UNSET, open_read=_UNSET, resolver=None):
    """Whether ``user`` may manage ``page`` (share / access / lifecycle).

    Management is reserved for the page owner and the workspace admin/owner.
    A user who cannot even see the page (private Collection boundary, private
    page without a share) can never manage it, so a boundary the owner falls
    outside of stays authoritative.
    """
    if not _is_active_user(user):
        return False
    if workspace is None:
        workspace = page.workspace
    if not can_view_page(
        user, page, workspace, workspace_role=workspace_role, open_read=open_read, resolver=resolver
    ):
        return False
    if page.owned_by_id == user.id:
        return True
    return is_workspace_admin(workspace, user, workspace_role=workspace_role)


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
        self._shares = None
        self._cache = {}
        self._share_cache = {}

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

    def _load_shares(self):
        """Load every explicit share in the workspace, grouped by page+member."""
        if self._shares is not None:
            return
        shares = {}
        for row in PageShare.objects.filter(
            workspace_id=self.workspace_id, deleted_at__isnull=True
        ).values("page_id", "member_id", "role"):
            capability = _SHARE_ROLE_TO_CAPABILITY.get(row["role"])
            if capability:
                shares.setdefault(row["page_id"], {})[row["member_id"]] = capability
        self._shares = shares

    def resolve_share(self, page, user):
        """Nearest ancestor-or-self explicit-share capability for ``user``."""
        if page is None or not _is_active_user(user):
            return Capability.NONE
        cache_key = (page.pk, user.id)
        if cache_key in self._share_cache:
            return self._share_cache[cache_key]
        self._load()
        self._load_shares()
        seen = set()
        current_id = page.pk
        result = Capability.NONE
        while current_id is not None and current_id not in seen:
            seen.add(current_id)
            capability = self._shares.get(current_id, {}).get(user.id)
            if capability is not None:
                result = capability
                break
            current_id = self._parents.get(current_id)
        self._share_cache[cache_key] = result
        return result

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


def shared_page_ids(workspace, user):
    """Page ids ``user`` may discover through a direct (inherited) share.

    A share is inherited by the whole subtree, so the visible set is the union
    of every explicitly shared page's descendants. Short-circuits to an empty
    set (no extra query) when the user has no share, which keeps the common
    Wiki list path on its pre-WIKI-06 query plan.
    """
    if not _is_active_user(user) or workspace is None:
        return set()

    explicit = list(
        PageShare.objects.filter(
            workspace=workspace,
            member=user,
            deleted_at__isnull=True,
        ).values_list("page_id", flat=True)
    )
    if not explicit:
        return set()

    resolver = PageAccessResolver(workspace.id)
    ids = set()
    for page_id in explicit:
        ids.update(resolver.descendants(page_id))
    return ids


def page_visibility_q(user, workspace):
    """``Q`` selecting pages the user may view (capability >= VIEW).

    Mirrors :func:`get_page_capabilities` for the non-shared, non-Collection
    part of the algorithm: owned pages, public pages, and pages reached through
    a direct share. Callers still drop private-Collection subtrees with
    :func:`hidden_page_ids`.
    """
    q = Q(owned_by=user) | Q(access=Page.PUBLIC_ACCESS)
    shared = shared_page_ids(workspace, user)
    if shared:
        q |= Q(id__in=shared)
    return q


def filter_visible_pages(queryset, user, workspace, *, workspace_role=None):
    """Filter a ``Page`` queryset through the centralized visibility policy."""
    if workspace is None:
        return queryset.none()
    if workspace_role is None:
        workspace_role = resolve_workspace_role(workspace.id, getattr(user, "id", None))
    hidden = hidden_page_ids(workspace, user, workspace_role=workspace_role)
    queryset = queryset.filter(page_visibility_q(user, workspace))
    if hidden:
        queryset = queryset.exclude(id__in=hidden)
    return queryset


def visible_page_parent_id(page, user, workspace=None, *, workspace_role=_UNSET, resolver=None):
    """Return ``page.parent_id`` only when the parent is visible to ``user``.

    Matches the breadcrumb redaction in :mod:`plane.utils.wiki_ai`: a child the
    caller can view must not leak a private parent's id through ``parent``.
    """
    if page.parent_id is None:
        return None
    if workspace is None:
        workspace = page.workspace
    parent = page.parent
    if user is None or can_view_page(
        user, parent, workspace, workspace_role=workspace_role, resolver=resolver
    ):
        return str(page.parent_id)
    return None


def searchable_page_q(user, workspace):
    """Visibility ``Q`` for workspace Wiki search.

    Search keeps private pages out of the result set even for their owner
    (pinned by the WIKI-04a contract tests); the direct-share source adds the
    private pages an explicit share grants, so an unshared user still cannot
    discover them.
    """
    q = Q(access=Page.PUBLIC_ACCESS)
    shared = shared_page_ids(workspace, user)
    if shared:
        q |= Q(id__in=shared)
    return q
