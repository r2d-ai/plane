# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Idempotent Wiki bootstrap for a real Plane workspace.

Wiki Home is a system dashboard. Durable starter content lives in the
workspace's default Collection and an ordinary editable Workspace Wiki page.
"""

from django.conf import settings
from django.db import transaction

from plane.db.models import Page, PageCollection, PageCollectionPage, Workspace


WELCOME_EXTERNAL_SOURCE = "wiki_bootstrap"
WELCOME_EXTERNAL_ID = "welcome-v1"
GENERAL_COLLECTION_NAME = "General"
GENERAL_COLLECTION_DESCRIPTION = "Your workspace's general collection."


def _welcome_title(workspace: Workspace) -> str:
    if workspace.slug == settings.COMPANY_WIKI_WORKSPACE_SLUG:
        return "Welcome to Company's Wiki"
    return f"Welcome to {workspace.name} Wiki"


def _save_as_owner(instance, owner_id):
    """Persist a BaseModel without request-local audit data overriding owner."""

    instance.save(created_by_id=owner_id, disable_auto_set_user=True)
    return instance


@transaction.atomic
def ensure_wiki_defaults(workspace: Workspace):
    """Ensure the workspace has one default Collection and one starter page.

    The helper is deliberately idempotent and non-destructive:
    - an existing default Collection is preserved;
    - an existing General Collection is promoted only when no default exists;
    - an existing marked/legacy Welcome page is reused;
    - existing Collection membership is never moved.
    """

    workspace = Workspace.objects.select_for_update().select_related("owner").get(pk=workspace.pk)
    owner_id = workspace.owner_id

    collections = PageCollection.objects.filter(workspace=workspace, deleted_at__isnull=True)
    collection = collections.filter(is_default=True).order_by("created_at", "id").first()
    created_general = False

    if collection is None:
        collection = collections.filter(name__iexact=GENERAL_COLLECTION_NAME).order_by("created_at", "id").first()
        if collection is not None:
            collection.is_default = True
            collection.updated_by_id = owner_id
            collection.save(update_fields=["is_default", "updated_by", "updated_at"], disable_auto_set_user=True)
        else:
            collection = PageCollection(
                workspace=workspace,
                name=GENERAL_COLLECTION_NAME,
                description=GENERAL_COLLECTION_DESCRIPTION,
                access=PageCollection.ACCESS_PUBLIC,
                sort_order=0,
                is_default=True,
                created_by_id=owner_id,
                updated_by_id=owner_id,
            )
            _save_as_owner(collection, owner_id)
            created_general = True

    welcome = (
        Page.objects.filter(
            workspace=workspace,
            is_global=True,
            deleted_at__isnull=True,
            external_source=WELCOME_EXTERNAL_SOURCE,
            external_id=WELCOME_EXTERNAL_ID,
        )
        .order_by("created_at", "id")
        .first()
    )

    if welcome is None:
        assigned_page_ids = PageCollectionPage.objects.filter(
            workspace=workspace,
            deleted_at__isnull=True,
        ).values("page_id")
        legacy = list(
            Page.objects.filter(
                workspace=workspace,
                is_global=True,
                access=Page.PUBLIC_ACCESS,
                parent__isnull=True,
                archived_at__isnull=True,
                deleted_at__isnull=True,
                name__iregex=r"^Welcome to .+Wiki$",
            )
            .exclude(id__in=assigned_page_ids)
            .order_by("created_at", "id")[:2]
        )
        if len(legacy) == 1:
            welcome = legacy[0]
            welcome.external_source = WELCOME_EXTERNAL_SOURCE
            welcome.external_id = WELCOME_EXTERNAL_ID
            welcome.updated_by_id = owner_id
            welcome.save(
                update_fields=["external_source", "external_id", "updated_by", "updated_at"],
                disable_auto_set_user=True,
            )
        else:
            welcome = Page(
                workspace=workspace,
                owned_by_id=owner_id,
                name=_welcome_title(workspace),
                access=Page.PUBLIC_ACCESS,
                is_global=True,
                parent=None,
                description_json={},
                description_html="<p></p>",
                description_binary=None,
                external_source=WELCOME_EXTERNAL_SOURCE,
                external_id=WELCOME_EXTERNAL_ID,
                created_by_id=owner_id,
                updated_by_id=owner_id,
            )
            _save_as_owner(welcome, owner_id)

    current_membership = PageCollectionPage.objects.filter(
        page=welcome,
        deleted_at__isnull=True,
    ).first()
    if current_membership is None:
        membership = PageCollectionPage(
            collection=collection,
            page=welcome,
            workspace=workspace,
            sort_order=welcome.sort_order,
            created_by_id=owner_id,
            updated_by_id=owner_id,
        )
        _save_as_owner(membership, owner_id)

    migrated_roots = 0
    if created_general:
        assigned_page_ids = PageCollectionPage.objects.filter(
            workspace=workspace,
            deleted_at__isnull=True,
        ).values("page_id")
        roots = list(
            Page.objects.filter(
                workspace=workspace,
                is_global=True,
                access=Page.PUBLIC_ACCESS,
                parent__isnull=True,
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(id__in=assigned_page_ids)
            .order_by("sort_order", "created_at", "id")
        )
        for page in roots:
            membership = PageCollectionPage(
                collection=collection,
                page=page,
                workspace=workspace,
                sort_order=page.sort_order,
                created_by_id=owner_id,
                updated_by_id=owner_id,
            )
            _save_as_owner(membership, owner_id)
            migrated_roots += 1

    return {
        "collection": collection,
        "welcome": welcome,
        "created_general": created_general,
        "migrated_roots": migrated_roots,
    }
