# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-06a contract tests: direct page sharing (plan §9.1–§9.2, spec §5.3).

Covers the PageShare API, the effective-permission extension (View/Comment/Edit
roles, inheritance, private-page confidentiality), the single permission path
used by REST/search/assets, and BOLA/IDOR scoping.
"""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    FileAsset,
    Page,
    PageCollection,
    PageCollectionPage,
    PageLog,
    PageShare,
    User,
    Workspace,
    WorkspaceMember,
)

S3_STORAGE_PATH = "plane.app.views.asset.v2.S3Storage"


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _page_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/"


def _shares_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/shares/"


def _share_url(slug, page_id, share_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/shares/{share_id}/"


def _search_url(slug):
    return f"/api/workspaces/{slug}/entity-search/"


def _asset_url(slug, asset_id):
    return f"/api/assets/v2/workspaces/{slug}/{asset_id}/"


def _asset_download_url(slug, asset_id):
    return f"/api/assets/v2/workspaces/{slug}/download/{asset_id}/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="P", access=Page.PUBLIC_ACCESS, parent=None):
    return Page.objects.create(
        workspace=workspace, owned_by=owner, name=name, access=access, is_global=True, parent=parent
    )


def _share(workspace, page, member, role=PageShare.ROLE_VIEW):
    return PageShare.objects.create(workspace=workspace, page=page, member=member, role=role)


@pytest.mark.contract
class TestPageShareCrud:
    @pytest.mark.django_db
    def test_owner_adds_lists_updates_and_removes_share(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("shared@plane.so"))
        page = _wiki_page(workspace, create_user)

        response = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(member.id), "role": PageShare.ROLE_VIEW},
            format="json",
        )
        assert response.status_code == 201
        share_id = response.json()["id"]
        assert response.json()["role"] == PageShare.ROLE_VIEW
        assert response.json()["member_detail"]["email"] == "shared@plane.so"

        response = session_client.get(_shares_url(workspace.slug, page.id))
        assert response.status_code == 200
        assert {row["id"] for row in response.json()} == {share_id}

        response = session_client.patch(
            _share_url(workspace.slug, page.id, share_id),
            {"role": PageShare.ROLE_EDIT},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["role"] == PageShare.ROLE_EDIT

        response = session_client.delete(_share_url(workspace.slug, page.id, share_id))
        assert response.status_code == 204
        assert PageShare.objects.filter(page=page, deleted_at__isnull=True).count() == 0

    @pytest.mark.django_db
    def test_re_adding_reactivates_the_same_row(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("again@plane.so"))
        page = _wiki_page(workspace, create_user)

        first = session_client.post(
            _shares_url(workspace.slug, page.id), {"member": str(member.id)}, format="json"
        )
        assert first.status_code == 201
        session_client.delete(_share_url(workspace.slug, page.id, first.json()["id"]))

        second = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(member.id), "role": PageShare.ROLE_COMMENT},
            format="json",
        )
        assert second.status_code == 201
        assert PageShare.all_objects.filter(page=page, member=member).count() == 1
        assert PageShare.objects.get(page=page, member=member).role == PageShare.ROLE_COMMENT

    @pytest.mark.django_db
    def test_invalid_role_rejected(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("badrole@plane.so"))
        page = _wiki_page(workspace, create_user)

        response = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(member.id), "role": 999},
            format="json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_non_workspace_member_cannot_be_shared_with(self, session_client, workspace, create_user):
        outsider = _make_user("outsider@plane.so")
        page = _wiki_page(workspace, create_user)

        response = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(outsider.id)},
            format="json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_share_change_is_audited(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("audited@plane.so"))
        page = _wiki_page(workspace, create_user)

        share_id = session_client.post(
            _shares_url(workspace.slug, page.id), {"member": str(member.id)}, format="json"
        ).json()["id"]
        session_client.delete(_share_url(workspace.slug, page.id, share_id))

        logs = PageLog.objects.filter(page=page, entity_name="share")
        assert {log.entity_type for log in logs} == {"created", "removed"}

    @pytest.mark.django_db
    def test_share_requires_manage_capability(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("plain-member@plane.so"))
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        _share(workspace, page, member, PageShare.ROLE_EDIT)

        # A user with only EDIT-share rights can read but never manage shares.
        api_client.force_authenticate(user=member)
        assert api_client.get(_shares_url(workspace.slug, page.id)).status_code == 403

    @pytest.mark.django_db
    def test_non_member_cannot_list_shares(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        outsider = _make_user("no-access@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_shares_url(workspace.slug, page.id)).status_code == 403


@pytest.mark.contract
class TestPrivatePageSharing:
    @pytest.mark.django_db
    def test_shared_user_sees_private_page_and_unshared_cannot(self, api_client, workspace, create_user):
        shared = _member(workspace, _make_user("shared@plane.so"))
        unshared = _member(workspace, _make_user("unshared@plane.so"))
        page = _wiki_page(workspace, create_user, name="Secret", access=Page.PRIVATE_ACCESS)
        _share(workspace, page, shared, PageShare.ROLE_VIEW)

        api_client.force_authenticate(user=shared)
        assert api_client.get(_page_url(workspace.slug, page.id)).status_code == 200
        assert str(page.id) in {row["id"] for row in api_client.get(_pages_url(workspace.slug)).json()}

        api_client.force_authenticate(user=unshared)
        assert api_client.get(_page_url(workspace.slug, page.id)).status_code == 404
        assert str(page.id) not in {row["id"] for row in api_client.get(_pages_url(workspace.slug)).json()}

    @pytest.mark.django_db
    def test_view_share_cannot_edit_but_edit_share_can(self, api_client, workspace, create_user):
        viewer = _member(workspace, _make_user("viewer@plane.so"))
        commenter = _member(workspace, _make_user("commenter@plane.so"))
        editor = _member(workspace, _make_user("editor@plane.so"))
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        _share(workspace, page, viewer, PageShare.ROLE_VIEW)
        _share(workspace, page, commenter, PageShare.ROLE_COMMENT)
        _share(workspace, page, editor, PageShare.ROLE_EDIT)

        for user in (viewer, commenter):
            api_client.force_authenticate(user=user)
            assert api_client.get(_page_url(workspace.slug, page.id)).status_code == 200
            assert (
                api_client.patch(_page_url(workspace.slug, page.id), {"name": "Nope"}, format="json").status_code
                == 403
            )

        api_client.force_authenticate(user=editor)
        assert (
            api_client.patch(_page_url(workspace.slug, page.id), {"name": "Edited"}, format="json").status_code == 200
        )
        page.refresh_from_db()
        assert page.name == "Edited"

    @pytest.mark.django_db
    def test_share_removal_revokes_access(self, session_client, workspace, create_user):
        shared = _member(workspace, _make_user("revoked@plane.so"))
        shared_client = _client_for(shared)
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        share_id = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(shared.id)},
            format="json",
        ).json()["id"]

        assert shared_client.get(_page_url(workspace.slug, page.id)).status_code == 200

        assert session_client.delete(_share_url(workspace.slug, page.id, share_id)).status_code == 204
        assert shared_client.get(_page_url(workspace.slug, page.id)).status_code == 404
        assert (
            shared_client.patch(_page_url(workspace.slug, page.id), {"name": "Nope"}, format="json").status_code == 404
        )

    @pytest.mark.django_db
    def test_share_is_inherited_by_the_subtree(self, session_client, api_client, workspace, create_user):
        shared = _member(workspace, _make_user("subtree@plane.so"))
        parent = _wiki_page(workspace, create_user, name="Parent", access=Page.PRIVATE_ACCESS)
        child = _wiki_page(workspace, create_user, name="Child", access=Page.PRIVATE_ACCESS, parent=parent)
        session_client.post(_shares_url(workspace.slug, parent.id), {"member": str(shared.id)}, format="json")

        api_client.force_authenticate(user=shared)
        assert api_client.get(_page_url(workspace.slug, child.id)).status_code == 200
        assert str(child.id) in {row["id"] for row in api_client.get(_pages_url(workspace.slug)).json()}


@pytest.mark.contract
class TestPageShareScope:
    @pytest.mark.django_db
    def test_cross_workspace_page_uuid_denied(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other", slug="other-share", owner=create_user)
        foreign_page = _wiki_page(other_workspace, create_user, name="Foreign")

        assert session_client.get(_shares_url(workspace.slug, foreign_page.id)).status_code == 404

    @pytest.mark.django_db
    def test_share_id_from_another_page_denied(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("scoped@plane.so"))
        page_one = _wiki_page(workspace, create_user, name="One")
        page_two = _wiki_page(workspace, create_user, name="Two")
        share_id = session_client.post(
            _shares_url(workspace.slug, page_one.id), {"member": str(member.id)}, format="json"
        ).json()["id"]

        response = session_client.patch(
            _share_url(workspace.slug, page_two.id, share_id),
            {"role": PageShare.ROLE_EDIT},
            format="json",
        )
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_project_page_cannot_be_shared(self, session_client, workspace, create_user):
        from plane.db.models import Project, ProjectPage

        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        project_page = Page.objects.create(workspace=workspace, owned_by=create_user, name="Project page")
        ProjectPage.objects.create(workspace=workspace, project=project, page=project_page)

        assert session_client.get(_shares_url(workspace.slug, project_page.id)).status_code == 404


@pytest.mark.contract
class TestSharedPrivatePageDiscovery:
    """Search is a discovery surface: shared private pages appear, unshared do not."""

    @pytest.mark.django_db
    def test_search_returns_shared_private_page_only_to_shared_user(self, api_client, workspace, create_user):
        shared = _member(workspace, _make_user("search-shared@plane.so"))
        unshared = _member(workspace, _make_user("search-unshared@plane.so"))
        page = _wiki_page(workspace, create_user, name="Quarterly Secret", access=Page.PRIVATE_ACCESS)
        _share(workspace, page, shared, PageShare.ROLE_VIEW)

        def _ids(user):
            api_client.force_authenticate(user=user)
            response = api_client.get(_search_url(workspace.slug), {"query": "Quarterly", "query_type": "page"})
            assert response.status_code == 200
            return {row["id"] for row in response.json().get("page", [])}

        assert str(page.id) in _ids(shared)
        assert str(page.id) not in _ids(unshared)

    @pytest.mark.django_db
    def test_search_excludes_private_collection_subtree(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("coll-search@plane.so"))
        collection = PageCollection.objects.create(
            workspace=workspace, name="Private", access=PageCollection.ACCESS_PRIVATE
        )
        page = _wiki_page(workspace, create_user, name="Hidden Handbook")
        PageCollectionPage.objects.create(collection=collection, page=page, workspace=workspace)

        api_client.force_authenticate(user=member)
        response = api_client.get(_search_url(workspace.slug), {"query": "Hidden", "query_type": "page"})
        assert response.status_code == 200
        assert str(page.id) not in {row["id"] for row in response.json().get("page", [])}


@pytest.mark.contract
class TestWikiPageAssetAccess:
    """Page-bound Wiki assets inherit the page's effective access (spec §22.3)."""

    @staticmethod
    def _page_asset(workspace, page, create_user):
        return FileAsset.objects.create(
            attributes={"name": "private.png", "type": "image/png", "size": 128},
            asset=f"{workspace.id}/private.png",
            size=128,
            workspace=workspace,
            page=page,
            created_by=create_user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            is_uploaded=True,
            storage_metadata={"size": 128},
        )

    @pytest.mark.django_db
    def test_unshared_member_cannot_download_private_page_asset(self, api_client, workspace, create_user):
        unshared = _member(workspace, _make_user("asset-unshared@plane.so"))
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        asset = self._page_asset(workspace, page, create_user)

        api_client.force_authenticate(user=unshared)
        for url in (_asset_url(workspace.slug, asset.id), _asset_download_url(workspace.slug, asset.id)):
            with mock.patch(S3_STORAGE_PATH) as mock_storage:
                response = api_client.get(url)
            assert response.status_code in (403, 404), response.status_code
            mock_storage.return_value.generate_presigned_url.assert_not_called()

    @pytest.mark.django_db
    def test_owner_and_shared_user_can_download_private_page_asset(self, api_client, workspace, create_user):
        shared = _member(workspace, _make_user("asset-shared@plane.so"))
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        asset = self._page_asset(workspace, page, create_user)
        _share(workspace, page, shared, PageShare.ROLE_VIEW)

        for user in (create_user, shared):
            api_client.force_authenticate(user=user)
            with mock.patch(S3_STORAGE_PATH) as mock_storage:
                mock_storage.return_value.generate_presigned_url.return_value = "https://signed.example/x"
                response = api_client.get(_asset_url(workspace.slug, asset.id))
            assert response.status_code == 302, response.status_code
            mock_storage.return_value.generate_presigned_url.assert_called_once()
