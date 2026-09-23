# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-07c contract tests: nested Wiki page export (spec §17.2, plan §10.3).

Covers the ZIP download, stable hierarchy ordering, per-page access filtering,
BOLA/IDOR scoping, archived/private roots, structured limit errors and the
Company Wiki open-read override.
"""

import io
import zipfile

import pytest
from rest_framework.test import APIClient

from plane.db.models import Page, User, Workspace, WorkspaceMember


def _export_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/export/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="Page", access=Page.PUBLIC_ACCESS, parent=None, sort_order=65535):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=access,
        is_global=True,
        parent=parent,
        sort_order=sort_order,
    )


def _names(response):
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return archive.namelist()


@pytest.mark.contract
class TestWorkspacePageExport:
    @pytest.mark.django_db
    def test_owner_exports_tree_in_stable_order(self, session_client, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Handbook", sort_order=1)
        first = _wiki_page(workspace, create_user, name="Getting Started", parent=root, sort_order=1)
        _wiki_page(workspace, create_user, name="Install", parent=first, sort_order=1)
        _wiki_page(workspace, create_user, name="FAQ", parent=root, sort_order=2)

        response = session_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        assert "attachment" in response["Content-Disposition"]
        assert _names(response) == [
            "handbook/index.md",
            "handbook/01-getting-started/index.md",
            "handbook/01-getting-started/01-install.md",
            "handbook/02-faq.md",
        ]

    @pytest.mark.django_db
    def test_private_descendant_is_not_leaked(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        root = _wiki_page(workspace, create_user, name="Root", sort_order=1)
        _wiki_page(workspace, create_user, name="Public", parent=root, sort_order=1)
        _wiki_page(
            workspace,
            create_user,
            name="Secret",
            access=Page.PRIVATE_ACCESS,
            parent=root,
            sort_order=2,
        )

        api_client.force_authenticate(user=member)
        response = api_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 200
        names = _names(response)
        assert "root/index.md" in names
        assert "root/01-public.md" in names
        assert "root/02-secret.md" not in names

    @pytest.mark.django_db
    def test_page_from_other_workspace_not_found(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        foreign = _wiki_page(other, create_user, name="Foreign")

        response = session_client.get(_export_url(workspace.slug, foreign.id))

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_archived_root_not_found(self, session_client, workspace, create_user):
        from django.utils import timezone

        page = _wiki_page(workspace, create_user, name="Archived")
        page.archived_at = timezone.now().date()
        page.save(update_fields=["archived_at"])

        assert session_client.get(_export_url(workspace.slug, page.id)).status_code == 404

    @pytest.mark.django_db
    def test_private_root_without_access_not_found(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("member2@plane.so"))
        page = _wiki_page(workspace, create_user, name="Private root", access=Page.PRIVATE_ACCESS)

        api_client.force_authenticate(user=member)
        assert api_client.get(_export_url(workspace.slug, page.id)).status_code == 404

    @pytest.mark.django_db
    def test_project_page_is_not_exportable(self, session_client, workspace, create_user):
        project_page = Page.objects.create(
            workspace=workspace, owned_by=create_user, name="Project page", is_global=False
        )

        assert session_client.get(_export_url(workspace.slug, project_page.id)).status_code == 404

    @pytest.mark.django_db
    def test_depth_limit_returns_structured_error(self, settings, session_client, workspace, create_user):
        settings.PAGE_EXPORT_MAX_DEPTH = 1
        root = _wiki_page(workspace, create_user, name="Root")
        child = _wiki_page(workspace, create_user, name="Child", parent=root)
        _wiki_page(workspace, create_user, name="Grandchild", parent=child)

        response = session_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_EXPORT_DEPTH_LIMIT"

    @pytest.mark.django_db
    def test_page_limit_returns_structured_error(self, settings, session_client, workspace, create_user):
        settings.PAGE_EXPORT_MAX_PAGES = 2
        root = _wiki_page(workspace, create_user, name="Root")
        _wiki_page(workspace, create_user, name="Child 1", parent=root, sort_order=1)
        _wiki_page(workspace, create_user, name="Child 2", parent=root, sort_order=2)

        response = session_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_EXPORT_PAGE_LIMIT"

    @pytest.mark.django_db
    def test_size_limit_returns_structured_error(self, settings, session_client, workspace, create_user):
        settings.PAGE_EXPORT_MAX_BYTES = 1
        root = _wiki_page(workspace, create_user, name="Root")

        response = session_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_EXPORT_SIZE_LIMIT"

    @pytest.mark.django_db
    def test_anonymous_denied(self, workspace, create_user):
        page = _wiki_page(workspace, create_user, name="Root")

        anonymous = APIClient()
        assert anonymous.get(_export_url(workspace.slug, page.id)).status_code in (401, 403)


@pytest.mark.contract
class TestCompanyWikiExportOpenRead:
    @pytest.mark.django_db
    def test_open_read_non_member_can_export_public_tree(self, settings, api_client, workspace, create_user):
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True
        root = _wiki_page(workspace, create_user, name="Company Handbook")
        _wiki_page(workspace, create_user, name="Chapter", parent=root)
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        response = api_client.get(_export_url(workspace.slug, root.id))

        assert response.status_code == 200
        assert _names(response) == ["company-handbook/index.md", "company-handbook/01-chapter.md"]

    @pytest.mark.django_db
    def test_open_read_does_not_expose_private_root(self, settings, api_client, workspace, create_user):
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True
        page = _wiki_page(workspace, create_user, name="Secret", access=Page.PRIVATE_ACCESS)
        outsider = _make_user("outsider2@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_export_url(workspace.slug, page.id)).status_code == 404
