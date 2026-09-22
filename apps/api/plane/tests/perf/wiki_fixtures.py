# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deterministic bulk fixtures for the WIKI-04b performance suite.

These helpers generate Workspace Wiki ``Page`` rows at the scales named in the
implementation plan §7.8 (1,000 / 5,000 / deep / wide). They deliberately use
``bulk_create`` so a dataset is materialised in one statement, and they never
touch the network, so the measurement is reproducible in the standard
``docker-compose-test.yml`` stack.

The fixtures are intentionally *shaped* like real Wiki data: every page is
``is_global=True`` in a real workspace with a mix of public/private access,
a subset of favourites, and either a flat, deep or wide parent structure.
"""

from __future__ import annotations

import uuid

from django.db import connection
from django.utils import timezone

from plane.db.models import Page, UserFavorite


DEFAULT_SORT_ORDER = Page.DEFAULT_SORT_ORDER
PUBLIC = Page.PUBLIC_ACCESS
PRIVATE = Page.PRIVATE_ACCESS


def _make_row(
    *,
    workspace_id,
    owner_id,
    name,
    access,
    parent_id=None,
    description_stripped,
):
    return Page(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        owned_by_id=owner_id,
        created_by_id=owner_id,
        name=name,
        access=access,
        is_global=True,
        parent_id=parent_id,
        sort_order=DEFAULT_SORT_ORDER,
        description_html=f"<p>{description_stripped}</p>",
        description_stripped=description_stripped,
    )


def _description(index, *, kind="page"):
    return (
        f"{kind} {index:05d} performance fixture body. "
        "Sprint planning notes, architecture decisions, onboarding material and "
        "operational runbooks live in the workspace Wiki."
    )


def bulk_pages(
    workspace,
    owner,
    count,
    *,
    prefix="Wiki page",
    private_ratio=0.2,
    parent_id=None,
    include_description=True,
):
    """Create ``count`` flat/nested Wiki pages owned by ``owner`` in bulk.

    Returns the list of created page ids in insertion order. ``private_ratio``
    controls the share of private pages so the permission-filtered list path is
    measured against a realistic visibility split.
    """
    rows = []
    private_every = max(int(round(1 / private_ratio)), 1) if private_ratio else 0
    for index in range(count):
        access = PRIVATE if private_every and index % private_every == 0 else PUBLIC
        rows.append(
            _make_row(
                workspace_id=workspace.id,
                owner_id=owner.id,
                name=f"{prefix} {index:05d}",
                access=access,
                parent_id=parent_id,
                description_stripped=_description(index) if include_description else None,
            )
        )
    Page.objects.bulk_create(rows, batch_size=1000)
    return [row.id for row in rows]


def build_flat(workspace, owner, count, *, prefix="Wiki page", private_ratio=0.2):
    """Flat hierarchy: ``count`` sibling pages with no parent."""
    return bulk_pages(workspace, owner, count, prefix=prefix, private_ratio=private_ratio)


def build_project_scope_noise(workspace, owner, count, *, prefix="Project page"):
    """Create ``count`` project-scope (``is_global=False``) rows in the workspace.

    A real workspace shares the ``pages`` table between project pages and Wiki
    pages, so the Wiki list predicate ``is_global = true`` is selective. Without
    these rows the candidate index ``(workspace_id, is_global, ...)`` would look
    useless because every row already matches ``is_global``.
    """
    rows = [
        Page(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            owned_by_id=owner.id,
            created_by_id=owner.id,
            name=f"{prefix} {index:06d}",
            access=PUBLIC,
            is_global=False,
            sort_order=DEFAULT_SORT_ORDER,
            description_html=f"<p>{_description(index, kind='project')}</p>",
            description_stripped=_description(index, kind="project"),
        )
        for index in range(count)
    ]
    Page.objects.bulk_create(rows, batch_size=1000)
    return [row.id for row in rows]


def build_deep(workspace, owner, depth, *, prefix="Deep page"):
    """Deep hierarchy: a single chain of ``depth`` pages (root → leaf)."""
    rows = []
    parent_id = None
    for index in range(depth):
        page_id = uuid.uuid4()
        rows.append(
            Page(
                id=page_id,
                workspace_id=workspace.id,
                owned_by_id=owner.id,
                created_by_id=owner.id,
                name=f"{prefix} {index:04d}",
                access=PUBLIC,
                is_global=True,
                parent_id=parent_id,
                sort_order=DEFAULT_SORT_ORDER,
                description_html=f"<p>{_description(index, kind='deep')}</p>",
                description_stripped=_description(index, kind="deep"),
            )
        )
        parent_id = page_id
    Page.objects.bulk_create(rows, batch_size=1000)
    return {"root": rows[0].id, "leaf": rows[-1].id, "ids": [row.id for row in rows]}


def build_wide(workspace, owner, width, *, prefix="Wide child"):
    """Wide hierarchy: one root page with ``width`` direct children."""
    root_id = uuid.uuid4()
    root = Page(
        id=root_id,
        workspace_id=workspace.id,
        owned_by_id=owner.id,
        created_by_id=owner.id,
        name=f"{prefix[:-5] if prefix.endswith('child') else prefix} root",
        access=PUBLIC,
        is_global=True,
        description_html="<p>wide root</p>",
        description_stripped="wide root",
    )
    children = [
        _make_row(
            workspace_id=workspace.id,
            owner_id=owner.id,
            name=f"{prefix} {index:04d}",
            access=PUBLIC,
            parent_id=root_id,
            description_stripped=_description(index, kind="wide"),
        )
        for index in range(width)
    ]
    Page.objects.bulk_create([root, *children], batch_size=1000)
    return {"root": root_id, "children": [child.id for child in children]}


def build_favorites(workspace, user, page_ids):
    """Mark ``page_ids`` as favourites of ``user`` (exercises the Exists subquery)."""
    UserFavorite.objects.bulk_create(
        [
            UserFavorite(
                workspace_id=workspace.id,
                user_id=user.id,
                entity_type="page",
                entity_identifier=page_id,
            )
            for page_id in page_ids
        ],
        ignore_conflicts=True,
    )


def stagger_created_at(table="pages"):
    """Spread ``created_at`` over the past year so ordering is non-degenerate.

    ``auto_now_add`` collapses every bulk-created row to the same timestamp,
    which would let the planner skip the sort. Real Wiki pages are created over
    time, so randomise the timestamps with one set-based UPDATE.
    """
    now = timezone.now()
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {table} SET created_at = %s - (random() * interval '365 days'), "  # noqa: S608
            f"updated_at = %s - (random() * interval '30 days')",
            [now, now],
        )


def analyze_table(table="pages"):
    """Refresh planner statistics after a bulk load (required for honest plans)."""
    with connection.cursor() as cursor:
        cursor.execute(f"ANALYZE {table}")  # noqa: S608
