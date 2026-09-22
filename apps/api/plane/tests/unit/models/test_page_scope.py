# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-00 scope foundation regression tests.

Company Wiki is Workspace Wiki on a designated real workspace, so the Page
model keeps a non-null ``workspace`` and only gains two storage scopes:
project (``is_global=False``) and wiki (``is_global=True``). These tests pin
that contract before the Wiki backend is built on top of it.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.db.models import Page, PageLog, PageVersion


@pytest.mark.unit
class TestPageScopeFoundation:
    @pytest.mark.django_db
    def test_project_page_scope_helpers(self, workspace, create_user):
        page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Project page")

        assert page.is_global is False
        assert page.is_project_page is True
        assert page.is_workspace_page is False
        assert page.scope == Page.PROJECT_SCOPE

    @pytest.mark.django_db
    def test_wiki_page_exists_without_project_relation(self, workspace, create_user):
        page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Wiki page", is_global=True)

        assert page.project_pages.count() == 0
        assert page.is_project_page is False
        assert page.is_workspace_page is True
        assert page.scope == Page.WIKI_SCOPE

    @pytest.mark.django_db
    def test_page_workspace_is_required(self, create_user):
        """There is no nullable-workspace scope: every Page needs a workspace."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Page.objects.create(owned_by=create_user, name="No workspace")

    @pytest.mark.django_db
    def test_wiki_page_version_and_log_creation(self, workspace, create_user):
        page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Wiki page", is_global=True)

        version = PageVersion.objects.create(
            workspace=workspace,
            page=page,
            owned_by=create_user,
            description_html="<p>wiki version</p>",
        )
        log = PageLog.objects.create(page=page, workspace=workspace, entity_name="image")

        assert version.workspace_id == workspace.id
        assert log.workspace_id == workspace.id
