# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-01 contract tests: the Workspace Wiki backend (spec §4, §6, §29).

Covers secure Workspace Wiki CRUD, hierarchy, BOLA/IDOR scoping and the
Company Wiki open-read override. Company Wiki reuses these endpoints against
the workspace designated by ``COMPANY_WIKI_WORKSPACE_SLUG``.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import (
    Page,
    PageVersion,
    Project,
    ProjectPage,
    User,
    Workspace,
    WorkspaceMember,
)


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _page_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/"


def _archive_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/archive/"


def _lock_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/lock/"


def _description_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/description/"


def _versions_url(slug, page_id, pk=None):
    base = f"/api/workspaces/{slug}/pages/{page_id}/versions/"
    return f"{base}{pk}/" if pk else base


def _duplicate_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/duplicate/"


def _make_wiki_page(workspace, owner, name="Wiki page", access=Page.PUBLIC_ACCESS, parent=None):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=access,
        is_global=True,
        parent=parent,
    )


def _make_member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _make_user(email):
    return User.objects.create(
        email=email,
        username=email.split("@")[0],
        first_name="Other",
        last_name="User",
    )


@pytest.mark.contract
class TestWorkspacePageCrud:
    @pytest.mark.django_db
    def test_create_public_wiki_page(self, session_client, workspace, create_user):
        response = session_client.post(
            _pages_url(workspace.slug),
            {"name": "Handbook", "description_html": "<p>hello</p>"},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["is_global"] is True
        page = Page.objects.get(pk=response.json()["id"])
        assert page.workspace_id == workspace.id
        assert page.is_global is True
        assert ProjectPage.objects.filter(page=page).count() == 0

    @pytest.mark.django_db
    def test_create_private_wiki_page(self, session_client, workspace, create_user):
        response = session_client.post(
            _pages_url(workspace.slug),
            {"name": "Private", "access": Page.PRIVATE_ACCESS},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["access"] == Page.PRIVATE_ACCESS

    @pytest.mark.django_db
    def test_retrieve_own_wiki_page(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        response = session_client.get(_page_url(workspace.slug, page.id))

        assert response.status_code == 200
        assert response.json()["name"] == "Wiki page"

    @pytest.mark.django_db
    def test_patch_scoped_to_workspace(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        response = session_client.patch(_page_url(workspace.slug, page.id), {"name": "Renamed"}, format="json")

        assert response.status_code == 200
        page.refresh_from_db()
        assert page.name == "Renamed"

    @pytest.mark.django_db
    def test_deny_cross_workspace_page_uuid(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        foreign_page = _make_wiki_page(other_workspace, create_user, name="Foreign")

        response = session_client.get(_page_url(workspace.slug, foreign_page.id))

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_deny_project_page_via_workspace_api(self, session_client, workspace, create_user):
        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        project_page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Project page")
        ProjectPage.objects.create(workspace=workspace, project=project, page=project_page)

        response = session_client.get(_page_url(workspace.slug, project_page.id))

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_invalid_order_by_rejected(self, session_client, workspace, create_user):
        _make_wiki_page(workspace, create_user)

        response = session_client.get(_pages_url(workspace.slug), {"order_by": "name; DROP TABLE pages"})

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_list_excludes_project_and_archived_pages(self, session_client, workspace, create_user):
        wiki_page = _make_wiki_page(workspace, create_user, name="Wiki")
        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        project_page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Project page")
        ProjectPage.objects.create(workspace=workspace, project=project, page=project_page)
        archived = _make_wiki_page(workspace, create_user, name="Archived")
        archived.archived_at = timezone.now().date()
        archived.save()

        response = session_client.get(_pages_url(workspace.slug))

        assert response.status_code == 200
        ids = {row["id"] for row in response.json()}
        assert str(wiki_page.id) in ids
        assert str(project_page.id) not in ids
        assert str(archived.id) not in ids

    @pytest.mark.django_db
    def test_search_matches_name(self, session_client, workspace, create_user):
        _make_wiki_page(workspace, create_user, name="Onboarding guide")
        _make_wiki_page(workspace, create_user, name="Runbook")

        response = session_client.get(_pages_url(workspace.slug), {"search": "Onboarding"})

        assert response.status_code == 200
        assert {row["name"] for row in response.json()} == {"Onboarding guide"}

    @pytest.mark.django_db
    def test_favorite_endpoint_and_filter(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)
        favorite_url = f"/api/workspaces/{workspace.slug}/favorite-pages/{page.id}/"

        assert session_client.post(favorite_url).status_code == 204

        response = session_client.get(_pages_url(workspace.slug), {"favorite": "true"})
        assert response.status_code == 200
        assert {row["id"] for row in response.json()} == {str(page.id)}

        assert session_client.delete(favorite_url).status_code == 204


@pytest.mark.contract
class TestWorkspacePageLifecycle:
    @pytest.mark.django_db
    def test_description_read_write_scoped(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        response = session_client.patch(
            _description_url(workspace.slug, page.id),
            {"description_html": "<p>updated</p>"},
            format="json",
        )
        assert response.status_code == 200

        response = session_client.get(_description_url(workspace.slug, page.id))
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_archive_and_restore(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        response = session_client.post(_archive_url(workspace.slug, page.id))
        assert response.status_code == 200
        page.refresh_from_db()
        assert page.archived_at is not None

        response = session_client.delete(_archive_url(workspace.slug, page.id))
        assert response.status_code == 204
        page.refresh_from_db()
        assert page.archived_at is None

    @pytest.mark.django_db
    def test_lock_unlock_and_locked_write_denied(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        assert session_client.post(_lock_url(workspace.slug, page.id)).status_code == 204

        response = session_client.patch(
            _description_url(workspace.slug, page.id),
            {"description_html": "<p>nope</p>"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error_message"] == "PAGE_LOCKED"

        assert session_client.delete(_lock_url(workspace.slug, page.id)).status_code == 204

    @pytest.mark.django_db
    def test_duplicate_creates_independent_wiki_page(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user, name="Original")

        response = session_client.post(_duplicate_url(workspace.slug, page.id))

        assert response.status_code == 201
        assert response.json()["name"] == "Original (Copy)"
        assert response.json()["is_global"] is True
        copy_id = response.json()["id"]
        assert ProjectPage.objects.filter(page_id=copy_id).count() == 0

    @pytest.mark.django_db
    def test_version_list_and_cross_page_denied(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)
        other_page = _make_wiki_page(workspace, create_user, name="Other")
        version = PageVersion.objects.create(
            workspace=workspace,
            page=page,
            owned_by=create_user,
            description_html="<p>v1</p>",
        )
        other_version = PageVersion.objects.create(
            workspace=workspace,
            page=other_page,
            owned_by=create_user,
            description_html="<p>other</p>",
        )

        response = session_client.get(_versions_url(workspace.slug, page.id))
        assert response.status_code == 200
        assert {row["id"] for row in response.json()} == {str(version.id)}

        response = session_client.get(_versions_url(workspace.slug, page.id, other_version.id))
        assert response.status_code == 404


@pytest.mark.contract
class TestWorkspacePageHierarchy:
    @pytest.mark.django_db
    def test_self_parent_rejected(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user)

        response = session_client.patch(_page_url(workspace.slug, page.id), {"parent": str(page.id)}, format="json")

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_SELF_PARENT"

    @pytest.mark.django_db
    def test_descendant_parent_cycle_rejected(self, session_client, workspace, create_user):
        root = _make_wiki_page(workspace, create_user, name="Root")
        child = _make_wiki_page(workspace, create_user, name="Child", parent=root)

        response = session_client.patch(_page_url(workspace.slug, root.id), {"parent": str(child.id)}, format="json")

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_CYCLE"

    @pytest.mark.django_db
    def test_project_parent_rejected_for_wiki_child(self, session_client, workspace, create_user):
        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        project_page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Project page")
        ProjectPage.objects.create(workspace=workspace, project=project, page=project_page)
        wiki_page = _make_wiki_page(workspace, create_user)

        response = session_client.patch(
            _page_url(workspace.slug, wiki_page.id), {"parent": str(project_page.id)}, format="json"
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_CROSS_SCOPE"

    @pytest.mark.django_db
    def test_create_with_foreign_workspace_parent_rejected(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        foreign_parent = _make_wiki_page(other_workspace, create_user, name="Foreign parent")

        response = session_client.post(
            _pages_url(workspace.slug),
            {"name": "Child", "parent": str(foreign_parent.id)},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_NOT_FOUND"


@pytest.mark.contract
class TestWorkspacePageAccessControl:
    @pytest.mark.django_db
    def test_private_page_hidden_from_other_member(self, api_client, workspace, create_user):
        other_user = _make_member(workspace, _make_user("other@plane.so"))
        private_page = _make_wiki_page(workspace, create_user, name="Secret", access=Page.PRIVATE_ACCESS)

        api_client.force_authenticate(user=other_user)
        response = api_client.get(_page_url(workspace.slug, private_page.id))

        assert response.status_code == 404

        response = api_client.get(_pages_url(workspace.slug))
        assert response.status_code == 200
        assert str(private_page.id) not in {row["id"] for row in response.json()}

    @pytest.mark.django_db
    def test_public_page_readable_by_other_member(self, api_client, workspace, create_user):
        other_user = _make_member(workspace, _make_user("other@plane.so"))
        public_page = _make_wiki_page(workspace, create_user, name="Public")

        api_client.force_authenticate(user=other_user)
        response = api_client.get(_page_url(workspace.slug, public_page.id))

        assert response.status_code == 200

    @pytest.mark.django_db
    def test_non_member_cannot_read_or_write(self, api_client, workspace, create_user):
        outsider = _make_user("outsider@plane.so")
        page = _make_wiki_page(workspace, create_user)

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_pages_url(workspace.slug)).status_code == 403
        assert api_client.get(_page_url(workspace.slug, page.id)).status_code == 403
        assert api_client.post(_pages_url(workspace.slug), {"name": "Nope"}, format="json").status_code == 403

    @pytest.mark.django_db
    def test_other_workspace_admin_has_no_write_here(self, api_client, workspace, create_user):
        admin = _make_user("admin-other@plane.so")
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=admin)
        WorkspaceMember.objects.create(workspace=other_workspace, member=admin, role=20)

        api_client.force_authenticate(user=admin)
        response = api_client.post(_pages_url(workspace.slug), {"name": "Nope"}, format="json")

        assert response.status_code == 403


@pytest.mark.contract
class TestCompanyWikiOpenRead:
    def _enable(self, settings, workspace):
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

    @pytest.mark.django_db
    def test_open_read_non_member_can_read_not_write(self, api_client, settings, workspace, create_user):
        self._enable(settings, workspace)
        public_page = _make_wiki_page(workspace, create_user, name="Company Handbook")
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        response = api_client.get(_pages_url(workspace.slug))
        assert response.status_code == 200
        assert str(public_page.id) in {row["id"] for row in response.json()}
        assert api_client.get(_page_url(workspace.slug, public_page.id)).status_code == 200

        # Open-read never grants write.
        assert api_client.post(_pages_url(workspace.slug), {"name": "Nope"}, format="json").status_code == 403
        assert (
            api_client.patch(_page_url(workspace.slug, public_page.id), {"name": "Nope"}, format="json").status_code
            == 403
        )
        assert api_client.post(_lock_url(workspace.slug, public_page.id)).status_code == 403
        assert api_client.post(_archive_url(workspace.slug, public_page.id)).status_code == 403

    @pytest.mark.django_db
    def test_open_read_does_not_expose_private_page(self, api_client, settings, workspace, create_user):
        self._enable(settings, workspace)
        private_page = _make_wiki_page(workspace, create_user, name="Secret", access=Page.PRIVATE_ACCESS)
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_page_url(workspace.slug, private_page.id)).status_code == 404

    @pytest.mark.django_db
    def test_open_read_false_denies_non_member(self, api_client, settings, workspace, create_user):
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = False
        _make_wiki_page(workspace, create_user)
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_pages_url(workspace.slug)).status_code == 403

    @pytest.mark.django_db
    def test_open_read_does_not_leak_other_workspaces(self, api_client, settings, workspace, create_user):
        self._enable(settings, workspace)
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        _make_wiki_page(other_workspace, create_user, name="Not company wiki")
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_pages_url(other_workspace.slug)).status_code == 403

    @pytest.mark.django_db
    def test_anonymous_denied_regardless_of_flag(self, settings, workspace, create_user):
        self._enable(settings, workspace)
        page = _make_wiki_page(workspace, create_user)

        anonymous = APIClient()
        assert anonymous.get(_pages_url(workspace.slug)).status_code in (401, 403)
        assert anonymous.get(_page_url(workspace.slug, page.id)).status_code in (401, 403)
