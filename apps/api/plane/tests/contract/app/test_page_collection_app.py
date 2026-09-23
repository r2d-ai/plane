# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-05 contract tests: Collections backend (plan §8.3–§8.5, spec §5.5/§19).

Covers Collection CRUD, members, page moves/reorder, effective-ACL visibility,
atomic subtree moves, BOLA/IDOR scoping and Company Wiki open-read.
"""

import pytest
from rest_framework.test import APIClient
from unittest import mock

from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionMember,
    PageCollectionPage,
    User,
    Workspace,
    WorkspaceMember,
)


def _collections_url(slug):
    return f"/api/workspaces/{slug}/page-collections/"


def _collection_url(slug, collection_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/"


def _members_url(slug, collection_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/members/"


def _member_url(slug, collection_id, member_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/members/{member_id}/"


def _collection_pages_url(slug, collection_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/pages/"


def _collection_page_url(slug, collection_id, page_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/pages/{page_id}/"


def _reorder_url(slug):
    return f"/api/workspaces/{slug}/page-collections/reorder/"


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _page_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/"


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


def _collection(workspace, name, access=PageCollection.ACCESS_PRIVATE, created_by=None):
    return PageCollection.objects.create(workspace=workspace, name=name, access=access, created_by=created_by)


@pytest.mark.contract
class TestPageCollectionCrud:
    @pytest.mark.django_db
    def test_create_collection_first_becomes_default(self, session_client, workspace, create_user):
        response = session_client.post(_collections_url(workspace.slug), {"name": "Handbook"}, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Handbook"
        assert body["is_default"] is True
        assert body["workspace"] == str(workspace.id)
        assert PageCollection.objects.filter(workspace=workspace, is_default=True).count() == 1

    @pytest.mark.django_db
    def test_create_second_collection_is_not_default(self, session_client, workspace):
        _collection(workspace, "First", PageCollection.ACCESS_PUBLIC, created_by=None)

        response = session_client.post(_collections_url(workspace.slug), {"name": "Second"}, format="json")

        assert response.status_code == 201
        assert response.json()["is_default"] is False

    @pytest.mark.django_db
    def test_create_requires_manage_permission(self, session_client, workspace, create_user):
        guest = _member(workspace, _make_user("guest@plane.so"), role=5)
        client = _client_for(guest)

        response = client.post(_collections_url(workspace.slug), {"name": "Nope"}, format="json")
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_duplicate_name_rejected(self, session_client, workspace):
        _collection(workspace, "Dup", PageCollection.ACCESS_PUBLIC)

        response = session_client.post(_collections_url(workspace.slug), {"name": "Dup"}, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_default_collection_cannot_be_deleted(self, session_client, workspace, create_user):
        collection = _collection(workspace, "Default", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        PageCollection.objects.filter(pk=collection.pk).update(is_default=True)

        response = session_client.delete(_collection_url(workspace.slug, collection.id))
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_delete_collection_detaches_pages(self, session_client, workspace, create_user):
        collection = _collection(workspace, "Temp", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        page = _wiki_page(workspace, create_user)
        PageCollectionPage.objects.create(collection=collection, page=page)

        response = session_client.delete(_collection_url(workspace.slug, collection.id))

        assert response.status_code == 204
        assert PageCollectionPage.objects.filter(collection=collection, deleted_at__isnull=True).count() == 0
        # The page itself survives and becomes uncollected.
        assert Page.objects.filter(pk=page.pk).exists()

    @pytest.mark.django_db
    def test_reorder_collections(self, session_client, workspace, create_user):
        first = _collection(workspace, "First", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        second = _collection(workspace, "Second", PageCollection.ACCESS_PUBLIC, created_by=create_user)

        response = session_client.patch(
            _reorder_url(workspace.slug),
            {"collections": [{"id": str(second.id), "sort_order": 1}, {"id": str(first.id), "sort_order": 2}]},
            format="json",
        )

        assert response.status_code == 204
        first.refresh_from_db()
        second.refresh_from_db()
        assert second.sort_order == 1
        assert first.sort_order == 2


@pytest.mark.contract
class TestPageCollectionVisibility:
    @pytest.mark.django_db
    def test_private_collection_hidden_from_non_member(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        private = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)

        # Admin (owner) sees both.
        admin_response = session_client.get(_collections_url(workspace.slug))
        names = {item["name"] for item in admin_response.json()}
        assert {"Private", "Public"} <= names

        # Non-member sees only the public one.
        member_response = _client_for(member).get(_collections_url(workspace.slug))
        assert member_response.status_code == 200
        assert {item["name"] for item in member_response.json()} == {"Public"}

        # Retrieving the private one is a 404, not a 403 (no existence probe).
        assert _client_for(member).get(_collection_url(workspace.slug, private.id)).status_code == 404

    @pytest.mark.django_db
    def test_private_collection_visible_to_member(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        private = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        PageCollectionMember.objects.create(collection=private, member=member, role=PageCollection.ROLE_VIEW)

        response = _client_for(member).get(_collection_url(workspace.slug, private.id))
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_bola_collection_scoped_to_url_workspace(self, session_client, workspace, create_user):
        other = _make_user("owner-b@plane.so")
        workspace_b = Workspace.objects.create(name="B", owner=other, slug="workspace-b")
        collection_b = _collection(workspace_b, "B", PageCollection.ACCESS_PUBLIC, created_by=other)

        response = session_client.get(_collection_url(workspace.slug, collection_b.id))
        assert response.status_code == 404


@pytest.mark.contract
class TestPageCollectionMembers:
    @pytest.mark.django_db
    def test_add_member_requires_workspace_membership(self, session_client, workspace, create_user):
        collection = _collection(workspace, "C", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        outsider = _make_user("outsider@plane.so")

        response = session_client.post(
            _members_url(workspace.slug, collection.id),
            {"member": str(outsider.id), "role": PageCollection.ROLE_VIEW},
            format="json",
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_member_add_update_remove(self, session_client, workspace, create_user):
        collection = _collection(workspace, "C", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        member = _member(workspace, _make_user("member@plane.so"))

        add = session_client.post(
            _members_url(workspace.slug, collection.id),
            {"member": str(member.id), "role": PageCollection.ROLE_VIEW},
            format="json",
        )
        assert add.status_code == 201
        membership_id = add.json()["id"]
        assert add.json()["role"] == PageCollection.ROLE_VIEW

        update = session_client.patch(
            _member_url(workspace.slug, collection.id, membership_id),
            {"role": PageCollection.ROLE_EDIT},
            format="json",
        )
        assert update.status_code == 200
        assert update.json()["role"] == PageCollection.ROLE_EDIT

        remove = session_client.delete(_member_url(workspace.slug, collection.id, membership_id))
        assert remove.status_code == 204
        assert PageCollectionMember.objects.filter(collection=collection, deleted_at__isnull=True).count() == 0


@pytest.mark.contract
class TestCollectionPageMoves:
    @pytest.mark.django_db
    def test_move_enforces_single_collection_membership(self, session_client, workspace, create_user):
        first = _collection(workspace, "First", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        second = _collection(workspace, "Second", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        page = _wiki_page(workspace, create_user)

        assert (
            session_client.post(
                _collection_pages_url(workspace.slug, first.id), {"page": str(page.id)}, format="json"
            ).status_code
            == 201
        )
        assert (
            session_client.post(
                _collection_pages_url(workspace.slug, second.id), {"page": str(page.id)}, format="json"
            ).status_code
            == 201
        )

        live = PageCollectionPage.objects.filter(page=page, deleted_at__isnull=True)
        assert live.count() == 1
        assert live.first().collection_id == second.id

    @pytest.mark.django_db
    def test_atomic_subtree_move_hides_private_descendants(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        parent = _wiki_page(workspace, create_user, name="Parent")
        child = _wiki_page(workspace, create_user, name="Child", parent=parent)

        move = session_client.post(
            _collection_pages_url(workspace.slug, collection.id), {"page": str(parent.id)}, format="json"
        )
        assert move.status_code == 201

        # Member (not in the collection) loses the whole subtree at once.
        member_client = _client_for(member)
        listed = member_client.get(_pages_url(workspace.slug))
        listed_ids = {item["id"] for item in listed.json()}
        assert str(parent.id) not in listed_ids
        assert str(child.id) not in listed_ids
        assert member_client.get(_page_url(workspace.slug, parent.id)).status_code == 404
        assert member_client.get(_page_url(workspace.slug, child.id)).status_code == 404

        # Admin still sees both.
        admin_listed = session_client.get(_pages_url(workspace.slug))
        admin_ids = {item["id"] for item in admin_listed.json()}
        assert {str(parent.id), str(child.id)} <= admin_ids

    @pytest.mark.django_db
    def test_move_rehomes_explicit_descendant_boundary(self, session_client, workspace, create_user):
        source = _collection(workspace, "Source", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        target = _collection(workspace, "Target", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        parent = _wiki_page(workspace, create_user, name="Parent")
        child = _wiki_page(workspace, create_user, name="Child", parent=parent)
        PageCollectionPage.objects.create(collection=source, page=child)

        response = session_client.post(
            _collection_pages_url(workspace.slug, target.id), {"page": str(parent.id)}, format="json"
        )
        assert response.status_code == 201

        association = PageCollectionPage.objects.get(page=child, deleted_at__isnull=True)
        assert association.collection_id == target.id

    @pytest.mark.django_db
    def test_page_remove_restores_visibility(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        page = _wiki_page(workspace, create_user)

        session_client.post(_collection_pages_url(workspace.slug, collection.id), {"page": str(page.id)}, format="json")
        assert _client_for(member).get(_page_url(workspace.slug, page.id)).status_code == 404

        remove = session_client.delete(_collection_page_url(workspace.slug, collection.id, page.id))
        assert remove.status_code == 204
        assert _client_for(member).get(_page_url(workspace.slug, page.id)).status_code == 200

    @pytest.mark.django_db
    def test_reorder_collection_pages(self, session_client, workspace, create_user):
        collection = _collection(workspace, "C", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        first = _wiki_page(workspace, create_user, name="First")
        second = _wiki_page(workspace, create_user, name="Second")
        PageCollectionPage.objects.create(collection=collection, page=first)
        PageCollectionPage.objects.create(collection=collection, page=second)

        response = session_client.patch(
            _collection_pages_url(workspace.slug, collection.id),
            {"pages": [{"page": str(second.id), "sort_order": 7}]},
            format="json",
        )
        assert response.status_code == 204
        assert PageCollectionPage.objects.get(collection=collection, page=second).sort_order == 7


@pytest.mark.contract
class TestCompanyWikiCollections:
    @pytest.mark.django_db
    def test_open_read_allows_authenticated_non_member(self, session_client, settings, workspace, create_user):
        outsider = _make_user("outsider@plane.so")
        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

        client = _client_for(outsider)
        listing = client.get(_collections_url(workspace.slug))
        assert listing.status_code == 200
        assert {item["id"] for item in listing.json()} == {str(collection.id)}
        assert client.get(_collection_url(workspace.slug, collection.id)).status_code == 200

    @pytest.mark.django_db
    def test_open_read_never_grants_manage(self, session_client, settings, workspace):
        outsider = _make_user("outsider@plane.so")
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

        response = _client_for(outsider).post(_collections_url(workspace.slug), {"name": "Nope"}, format="json")
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_member_cannot_manage_collections(self, session_client, settings, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        client = _client_for(member)

        # Collections are an authorization boundary: members/guests never manage.
        assert client.post(_collections_url(workspace.slug), {"name": "Nope"}, format="json").status_code == 403

        # The designated Company Wiki workspace is likewise admin/owner-only.
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True
        assert client.post(_collections_url(workspace.slug), {"name": "Nope"}, format="json").status_code == 403

    @pytest.mark.django_db
    def test_open_read_members_omit_email_for_non_members(self, session_client, settings, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        PageCollectionMember.objects.create(
            collection=collection, member=member, role=PageCollection.ROLE_VIEW
        )
        outsider = _make_user("outsider@plane.so")
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

        response = _client_for(outsider).get(_members_url(workspace.slug, collection.id))
        assert response.status_code == 200
        assert response.json()
        assert "email" not in response.json()[0]["member_detail"]

        member_response = _client_for(member).get(_members_url(workspace.slug, collection.id))
        assert member_response.status_code == 200
        assert member_response.json()[0]["member_detail"]["email"] == member.email


@pytest.mark.contract
class TestCollectionPagesVisibility:
    @pytest.mark.django_db
    def test_pages_list_filters_invisible_pages(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("collection-viewer@plane.so"))
        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE, created_by=create_user)
        PageCollectionMember.objects.create(
            collection=collection, member=member, role=PageCollection.ROLE_VIEW
        )
        visible = _wiki_page(workspace, create_user, name="Visible")
        hidden = _wiki_page(workspace, create_user, name="Hidden", access=Page.PRIVATE_ACCESS)
        PageCollectionPage.objects.create(collection=collection, page=visible, workspace=workspace)
        PageCollectionPage.objects.create(collection=collection, page=hidden, workspace=workspace)

        response = _client_for(member).get(_collection_pages_url(workspace.slug, collection.id))

        assert response.status_code == 200
        page_ids = {row["page_detail"]["id"] for row in response.json()}
        assert str(visible.id) in page_ids
        assert str(hidden.id) not in page_ids

    @pytest.mark.django_db
    def test_private_page_cannot_join_public_collection(self, session_client, workspace, create_user):
        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        private_page = _wiki_page(workspace, create_user, name="Secret", access=Page.PRIVATE_ACCESS)

        response = session_client.post(
            _collection_pages_url(workspace.slug, collection.id),
            {"page": str(private_page.id)},
            format="json",
        )

        assert response.status_code == 400
        assert "Private pages cannot be added to a public collection" in response.json()["error"]

    @pytest.mark.django_db
    @mock.patch("plane.app.permissions.page_collection.can_manage_collections", return_value=True)
    def test_page_add_response_redacts_invisible_parent(self, _manage, api_client, workspace, create_user):
        member = _member(workspace, _make_user("page-add-member@plane.so"))
        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        private_parent = _wiki_page(workspace, create_user, name="Private parent", access=Page.PRIVATE_ACCESS)
        child = _wiki_page(workspace, create_user, name="Public child", parent=private_parent)

        api_client.force_authenticate(user=member)
        response = api_client.post(
            _collection_pages_url(workspace.slug, collection.id),
            {"page": str(child.id)},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["page_detail"]["parent"] is None

    @pytest.mark.django_db
    @mock.patch("plane.app.permissions.page_collection.can_manage_collections", return_value=True)
    def test_page_move_response_redacts_invisible_parent(self, _manage, api_client, workspace, create_user):
        member = _member(workspace, _make_user("page-move-member@plane.so"))
        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC, created_by=create_user)
        private_parent = _wiki_page(workspace, create_user, name="Private parent", access=Page.PRIVATE_ACCESS)
        child = _wiki_page(workspace, create_user, name="Public child", parent=private_parent)
        PageCollectionPage.objects.create(collection=collection, page=child, workspace=workspace)

        api_client.force_authenticate(user=member)
        response = api_client.post(
            _collection_page_url(workspace.slug, collection.id, child.id),
            {},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["page_detail"]["parent"] is None
