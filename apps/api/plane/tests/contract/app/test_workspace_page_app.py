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
    Label,
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


def _favorite_url(slug, page_id):
    return f"/api/workspaces/{slug}/favorite-pages/{page_id}/"


def _entity_search_url(slug):
    return f"/api/workspaces/{slug}/entity-search/"


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

    @pytest.mark.django_db
    def test_private_parent_hidden_from_non_owner(self, api_client, workspace, create_user):
        member = _make_member(workspace, _make_user("hierarchy-member@plane.so"))
        private_parent = _make_wiki_page(
            workspace, create_user, name="Private parent", access=Page.PRIVATE_ACCESS
        )
        child = _make_wiki_page(workspace, create_user, name="Public child")

        api_client.force_authenticate(user=member)
        response = api_client.patch(
            _page_url(workspace.slug, child.id), {"parent": str(private_parent.id)}, format="json"
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_NOT_FOUND"

    @pytest.mark.django_db
    def test_create_with_inaccessible_parent_matches_not_found(self, api_client, workspace, create_user):
        member = _make_member(workspace, _make_user("create-member@plane.so"))
        private_parent = _make_wiki_page(
            workspace, create_user, name="Private parent", access=Page.PRIVATE_ACCESS
        )

        api_client.force_authenticate(user=member)
        response = api_client.post(
            _pages_url(workspace.slug),
            {"name": "Child", "parent": str(private_parent.id)},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_NOT_FOUND"


@pytest.mark.contract
class TestWorkspacePageParentRedaction:
    @pytest.mark.django_db
    def test_retrieve_redacts_invisible_parent(self, api_client, workspace, create_user):
        member = _make_member(workspace, _make_user("parent-redact@plane.so"))
        private_parent = _make_wiki_page(
            workspace, create_user, name="Private parent", access=Page.PRIVATE_ACCESS
        )
        child = _make_wiki_page(workspace, create_user, name="Public child", parent=private_parent)

        api_client.force_authenticate(user=member)
        body = api_client.get(_page_url(workspace.slug, child.id)).json()

        assert body["parent"] is None

    @pytest.mark.django_db
    def test_labels_reject_foreign_workspace_ids(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        foreign_label = Label.objects.create(workspace=other_workspace, name="Foreign")
        page = _make_wiki_page(workspace, create_user, name="Label target")

        response = session_client.patch(
            _page_url(workspace.slug, page.id),
            {"labels": [str(foreign_label.id)]},
            format="json",
        )

        assert response.status_code == 400


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
class TestWorkspacePageCoreSecurityGate:
    """WIKI-04c §7.9: cross-user, cross-workspace and cross-scope regression gate."""

    @staticmethod
    def _ids(response):
        return {row["id"] for row in response.json()}

    @pytest.fixture
    def security_matrix(self, workspace, create_user):
        user_a = create_user
        user_b = _make_member(workspace, _make_user("wiki-user-b@plane.so"), role=15)
        guest = _make_member(workspace, _make_user("wiki-guest@plane.so"), role=5)
        user_c = _make_user("wiki-user-c@plane.so")
        other_workspace = Workspace.objects.create(name="Workspace 2", slug="workspace-2", owner=user_c)
        WorkspaceMember.objects.create(workspace=other_workspace, member=user_c, role=20)

        public_page = _make_wiki_page(workspace, user_a, name="Public W1")
        private_page = _make_wiki_page(workspace, user_a, name="Private W1", access=Page.PRIVATE_ACCESS)
        private_child = _make_wiki_page(
            workspace,
            user_a,
            name="Nested private child",
            access=Page.PRIVATE_ACCESS,
            parent=private_page,
        )
        archived_page = _make_wiki_page(workspace, user_a, name="Archived W1")
        archived_page.archived_at = timezone.now()
        archived_page.save(update_fields=["archived_at"])
        locked_page = _make_wiki_page(workspace, user_a, name="Locked W1")
        locked_page.is_locked = True
        locked_page.save(update_fields=["is_locked"])
        foreign_page = _make_wiki_page(other_workspace, user_c, name="Workspace 2 foreign")

        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        project_page = Page.objects.create(workspace=workspace, owned_by=user_a, name="Project Page")
        ProjectPage.objects.create(workspace=workspace, project=project, page=project_page)

        version = PageVersion.objects.create(
            workspace=workspace,
            page=public_page,
            owned_by=user_a,
            description_html="<p>public version</p>",
        )
        private_version = PageVersion.objects.create(
            workspace=workspace,
            page=private_page,
            owned_by=user_a,
            description_html="<p>private version</p>",
        )
        foreign_version = PageVersion.objects.create(
            workspace=other_workspace,
            page=foreign_page,
            owned_by=user_c,
            description_html="<p>foreign version</p>",
        )

        return {
            "user_a": user_a,
            "user_b": user_b,
            "guest": guest,
            "user_c": user_c,
            "workspace": workspace,
            "other_workspace": other_workspace,
            "public_page": public_page,
            "private_page": private_page,
            "private_child": private_child,
            "archived_page": archived_page,
            "locked_page": locked_page,
            "foreign_page": foreign_page,
            "project_page": project_page,
            "version": version,
            "private_version": private_version,
            "foreign_version": foreign_version,
        }

    @pytest.mark.django_db
    def test_private_and_nested_private_denied_across_metadata_description_versions_and_mutations(
        self, api_client, security_matrix
    ):
        matrix = security_matrix
        api_client.force_authenticate(user=matrix["user_b"])

        for page in (matrix["private_page"], matrix["private_child"]):
            assert api_client.get(_page_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert (
                api_client.patch(
                    _page_url(matrix["workspace"].slug, page.id), {"name": "Leak"}, format="json"
                ).status_code
                == 404
            )
            assert api_client.get(_description_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert (
                api_client.patch(
                    _description_url(matrix["workspace"].slug, page.id),
                    {"description_html": "<p>leak</p>"},
                    format="json",
                ).status_code
                == 404
            )
            assert api_client.get(_versions_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_archive_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_lock_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_duplicate_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_favorite_url(matrix["workspace"].slug, page.id)).status_code == 404

        assert (
            api_client.get(
                _versions_url(matrix["workspace"].slug, matrix["public_page"].id, matrix["private_version"].id)
            ).status_code
            == 404
        )

        response = api_client.get(_pages_url(matrix["workspace"].slug))
        assert response.status_code == 200
        ids = self._ids(response)
        assert str(matrix["private_page"].id) not in ids
        assert str(matrix["private_child"].id) not in ids

    @pytest.mark.django_db
    def test_cross_workspace_and_project_scope_ids_denied_across_wiki_routes(self, api_client, security_matrix):
        matrix = security_matrix
        api_client.force_authenticate(user=matrix["user_a"])

        wrong_scope_pages = (matrix["foreign_page"], matrix["project_page"])
        for page in wrong_scope_pages:
            assert api_client.get(_page_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.get(_description_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.get(_versions_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_archive_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_lock_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_duplicate_url(matrix["workspace"].slug, page.id)).status_code == 404
            assert api_client.post(_favorite_url(matrix["workspace"].slug, page.id)).status_code == 404

        assert (
            api_client.get(
                _versions_url(matrix["workspace"].slug, matrix["public_page"].id, matrix["foreign_version"].id)
            ).status_code
            == 404
        )

    @pytest.mark.django_db
    def test_guest_can_read_public_metadata_but_cannot_write_or_favorite(self, api_client, security_matrix):
        matrix = security_matrix
        api_client.force_authenticate(user=matrix["guest"])

        assert api_client.get(_page_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 200
        assert api_client.get(_description_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 200
        assert api_client.get(_versions_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 200
        assert (
            api_client.get(
                _versions_url(matrix["workspace"].slug, matrix["public_page"].id, matrix["version"].id)
            ).status_code
            == 200
        )

        assert (
            api_client.post(
                _pages_url(matrix["workspace"].slug), {"name": "Guest write"}, format="json"
            ).status_code
            == 403
        )
        assert (
            api_client.patch(
                _description_url(matrix["workspace"].slug, matrix["public_page"].id),
                {"description_html": "<p>guest</p>"},
                format="json",
            ).status_code
            == 403
        )
        assert api_client.post(_archive_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 403
        assert api_client.post(_lock_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 403
        assert api_client.post(_duplicate_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 403
        assert api_client.post(_favorite_url(matrix["workspace"].slug, matrix["public_page"].id)).status_code == 403

    @pytest.mark.django_db
    def test_archived_and_locked_pages_do_not_expand_access(self, api_client, security_matrix):
        matrix = security_matrix
        api_client.force_authenticate(user=matrix["user_b"])

        response = api_client.get(_pages_url(matrix["workspace"].slug))
        assert response.status_code == 200
        assert str(matrix["archived_page"].id) not in self._ids(response)

        assert (
            api_client.patch(
                _description_url(matrix["workspace"].slug, matrix["locked_page"].id),
                {"description_html": "<p>locked</p>"},
                format="json",
            ).status_code
            == 400
        )

        api_client.force_authenticate(user=matrix["user_a"])
        response = api_client.get(_pages_url(matrix["workspace"].slug), {"archived": "true"})
        assert response.status_code == 200
        assert str(matrix["archived_page"].id) in self._ids(response)
        assert (
            api_client.patch(
                _description_url(matrix["workspace"].slug, matrix["archived_page"].id),
                {"description_html": "<p>archived</p>"},
                format="json",
            ).status_code
            == 400
        )

    @pytest.mark.django_db
    def test_search_never_leaks_private_archived_or_cross_workspace_pages(self, api_client, security_matrix):
        matrix = security_matrix
        api_client.force_authenticate(user=matrix["user_b"])

        response = api_client.get(
            _entity_search_url(matrix["workspace"].slug),
            {"query": "W1", "query_type": "page", "count": 20},
        )

        assert response.status_code == 200
        ids = {row["id"] for row in response.json().get("page", [])}
        assert str(matrix["public_page"].id) in ids
        assert str(matrix["locked_page"].id) in ids
        assert str(matrix["private_page"].id) not in ids
        assert str(matrix["private_child"].id) not in ids
        assert str(matrix["archived_page"].id) not in ids
        assert str(matrix["foreign_page"].id) not in ids


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


@pytest.mark.contract
class TestWorkspaceEntitySearch:
    """WIKI-04a §7.7: Wiki pages are searchable by title and content.

    The workspace entity-search endpoint is member-gated; within a workspace it
    must return public Wiki pages (which have no ProjectPage link) and must
    never expose private pages or pages from another workspace.
    """

    def _search(self, client, slug, query):
        return client.get(
            _entity_search_url(slug),
            {"query": query, "query_type": "page", "count": 20},
        )

    @staticmethod
    def _ids(response):
        return {row["id"] for row in response.json().get("page", [])}

    @pytest.mark.django_db
    def test_search_returns_wiki_page_by_name(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user, name="Onboarding Guide")

        response = self._search(session_client, workspace.slug, "Onboarding")

        assert response.status_code == 200
        assert str(page.id) in self._ids(response)

    @pytest.mark.django_db
    def test_search_matches_content_without_html(self, session_client, workspace, create_user):
        page = _make_wiki_page(workspace, create_user, name="Handbook")
        page.description_html = "<p>The quarterly pipeline keyword</p>"
        page.save()

        response = self._search(session_client, workspace.slug, "quarterly")

        rows = {row["id"]: row for row in response.json().get("page", [])}
        assert str(page.id) in rows
        assert "quarterly" in rows[str(page.id)]["description_stripped"]
        assert "<p>" not in rows[str(page.id)]["description_stripped"]

    @pytest.mark.django_db
    def test_search_excludes_private_pages(self, session_client, workspace, create_user):
        private_page = _make_wiki_page(workspace, create_user, name="Secret Notes", access=Page.PRIVATE_ACCESS)

        response = self._search(session_client, workspace.slug, "Secret")

        assert str(private_page.id) not in self._ids(response)

    @pytest.mark.django_db
    def test_search_scoped_to_workspace(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-search", owner=create_user)
        other_page = _make_wiki_page(other_workspace, create_user, name="Onboarding Elsewhere")

        response = self._search(session_client, workspace.slug, "Onboarding")

        assert str(other_page.id) not in self._ids(response)

    @pytest.mark.django_db
    def test_search_denied_for_non_member(self, api_client, workspace, create_user):
        _make_wiki_page(workspace, create_user, name="Onboarding Guide")
        outsider = _make_user("search-outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        response = self._search(api_client, workspace.slug, "Onboarding")

        assert response.status_code in (403, 404)
