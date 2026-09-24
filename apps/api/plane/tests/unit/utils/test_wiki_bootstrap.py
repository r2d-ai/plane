# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from plane.db.models import Page, PageCollection, PageCollectionPage
from plane.tests.factories import UserFactory, WorkspaceFactory
from plane.utils.wiki_bootstrap import (
    GENERAL_COLLECTION_NAME,
    WELCOME_EXTERNAL_ID,
    WELCOME_EXTERNAL_SOURCE,
    ensure_wiki_defaults,
)


@pytest.mark.django_db
def test_wiki_bootstrap_creates_defaults_and_is_idempotent(settings):
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner, name="Engineering", slug="engineering")
    settings.COMPANY_WIKI_WORKSPACE_SLUG = "company"

    first = ensure_wiki_defaults(workspace)
    second = ensure_wiki_defaults(workspace)

    collection = PageCollection.objects.get(workspace=workspace, is_default=True)
    welcome = Page.objects.get(
        workspace=workspace,
        external_source=WELCOME_EXTERNAL_SOURCE,
        external_id=WELCOME_EXTERNAL_ID,
    )
    assert collection.name == GENERAL_COLLECTION_NAME
    assert collection.access == PageCollection.ACCESS_PUBLIC
    assert welcome.name == "Welcome to Engineering Wiki"
    assert welcome.is_global is True
    assert welcome.access == Page.PUBLIC_ACCESS
    assert PageCollectionPage.objects.filter(collection=collection, page=welcome).count() == 1
    assert PageCollection.objects.filter(workspace=workspace).count() == 1
    assert Page.objects.filter(workspace=workspace, external_source=WELCOME_EXTERNAL_SOURCE).count() == 1
    assert first["collection"].id == second["collection"].id
    assert first["welcome"].id == second["welcome"].id


@pytest.mark.django_db
def test_wiki_bootstrap_preserves_custom_default_collection():
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    custom = PageCollection.objects.create(
        workspace=workspace,
        name="Handbook",
        access=PageCollection.ACCESS_PRIVATE,
        is_default=True,
        created_by=owner,
    )

    result = ensure_wiki_defaults(workspace)

    custom.refresh_from_db()
    assert result["collection"].id == custom.id
    assert custom.access == PageCollection.ACCESS_PRIVATE
    assert not PageCollection.objects.filter(workspace=workspace, name=GENERAL_COLLECTION_NAME).exists()
    assert PageCollectionPage.objects.filter(collection=custom, page=result["welcome"]).exists()


@pytest.mark.django_db
def test_wiki_bootstrap_backfills_only_uncollected_public_root_pages():
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    public_root = Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name="Runbook",
        access=Page.PUBLIC_ACCESS,
        is_global=True,
    )
    child = Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name="Runbook child",
        access=Page.PUBLIC_ACCESS,
        is_global=True,
        parent=public_root,
    )
    private_root = Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name="Secret",
        access=Page.PRIVATE_ACCESS,
        is_global=True,
    )
    project_page = Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name="Project page",
        access=Page.PUBLIC_ACCESS,
        is_global=False,
    )

    result = ensure_wiki_defaults(workspace)
    collection = result["collection"]

    assert PageCollectionPage.objects.filter(collection=collection, page=public_root).exists()
    assert not PageCollectionPage.objects.filter(page=child).exists()
    assert not PageCollectionPage.objects.filter(page=private_root).exists()
    assert not PageCollectionPage.objects.filter(page=project_page).exists()
