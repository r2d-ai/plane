# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Collection move / reorder primitives (WIKI-05, plan §8.5, spec §19.2).

Moving a page into or out of a private Collection changes effective access for
an entire subtree. Every operation here runs in a single transaction and
re-homes the explicit boundaries of the whole subtree, so a private descendant
can never be exposed mid-move (even transiently) and a partially moved tree is
impossible.
"""

from django.core.cache import caches
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from plane.db.models import Page, PageCollectionPage
from plane.utils.page_access import PageAccessResolver

CACHE_NAMESPACE = "page_collection"


def invalidate_page_collection_caches(workspace_id):
    """Drop cached Collection payloads for a workspace after an access change.

    Search itself is database-backed (DRF ``SearchFilter`` over ``Page`` rows),
    so there is no separate index to rebuild; this clears the optional Django
    cache layer so a cached Collection view cannot outlive a move.
    """
    try:
        cache = caches["default"]
    except Exception:
        return
    delete_pattern = getattr(cache, "delete_pattern", None)
    if delete_pattern is None:
        return
    try:
        delete_pattern(f"{CACHE_NAMESPACE}:{workspace_id}:*")
    except Exception:
        # Not every backend supports pattern deletion. Correctness does not
        # depend on the cache because visibility is recomputed from the DB.
        return


def _next_sort_order(collection_id):
    current = PageCollectionPage.objects.filter(collection_id=collection_id, deleted_at__isnull=True).aggregate(
        Max("sort_order")
    )["sort_order__max"]
    if current is None:
        return float(Page.DEFAULT_SORT_ORDER)
    return float(current) + 1.0


@transaction.atomic
def move_page_to_collection(page, collection):
    """Move ``page`` and its whole subtree into ``collection`` atomically.

    Re-homes every explicit association inside the subtree so the move is a
    single unit; descendants without an explicit boundary simply inherit the
    target Collection through the hierarchy.
    """
    resolver = PageAccessResolver(page.workspace_id)
    subtree_ids = resolver.descendants(page.pk)

    PageCollectionPage.objects.filter(page_id__in=subtree_ids, deleted_at__isnull=True).update(
        collection=collection,
        workspace_id=collection.workspace_id,
    )

    association = PageCollectionPage.objects.filter(page=page, deleted_at__isnull=True).first()
    if association is None:
        association = PageCollectionPage.objects.create(
            collection=collection,
            page=page,
            workspace_id=collection.workspace_id,
            sort_order=_next_sort_order(collection.id),
        )

    invalidate_page_collection_caches(collection.workspace_id)
    return association


@transaction.atomic
def remove_page_from_collection(page):
    """Detach ``page`` and its subtree from every Collection, atomically."""
    resolver = PageAccessResolver(page.workspace_id)
    subtree_ids = resolver.descendants(page.pk)

    PageCollectionPage.objects.filter(page_id__in=subtree_ids, deleted_at__isnull=True).update(
        deleted_at=timezone.now()
    )
    invalidate_page_collection_caches(page.workspace_id)
