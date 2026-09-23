# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-07b contract tests: external Wiki page publishing (spec §15, plan §10.2).

Covers the publish/revoke API, the anonymous public retrieval endpoint, safe
asset resolution (only the published page's own assets, no descendant
traversal), sanitized output, rate limiting and workspace BOLA scoping, while
proving the existing project publish path is untouched.
"""

from datetime import date
from unittest import mock

import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    DeployBoard,
    FileAsset,
    Page,
    User,
    Workspace,
    WorkspaceMember,
)

PUBLIC_S3_STORAGE_PATH = "plane.space.views.asset.S3Storage"


def _publish_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/publish/"


def _publish_revoke_url(slug, page_id, publish_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/publish/{publish_id}/"


def _public_page_url(anchor):
    return f"/api/public/anchor/{anchor}/page/"


def _public_asset_url(anchor, asset_id):
    return f"/api/public/assets/v2/anchor/{anchor}/{asset_id}/"


def _project_settings_url(anchor):
    return f"/api/public/anchor/{anchor}/settings/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="P", access=Page.PUBLIC_ACCESS, parent=None, description_html="<p>hi</p>"):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=access,
        is_global=True,
        parent=parent,
        description_html=description_html,
    )


def _page_asset(workspace, page, create_user, name="doc.png"):
    return FileAsset.objects.create(
        attributes={"name": name, "type": "image/png", "size": 128},
        asset=f"{workspace.id}/{name}",
        size=128,
        workspace=workspace,
        page=page,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        is_uploaded=True,
        storage_metadata={"size": 128},
    )


@pytest.mark.contract
class TestPagePublishApi:
    @pytest.mark.django_db
    def test_owner_publishes_page_and_state_round_trips(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        assert session_client.get(_publish_url(workspace.slug, page.id)).json()["anchor"] is None

        response = session_client.post(_publish_url(workspace.slug, page.id))
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["page"] == str(page.id)
        assert body["anchor"]
        assert body["is_disabled"] is False

        state = session_client.get(_publish_url(workspace.slug, page.id))
        assert state.status_code == 200
        assert state.json()["anchor"] == body["anchor"]

    @pytest.mark.django_db
    def test_publish_is_idempotent(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        first = session_client.post(_publish_url(workspace.slug, page.id))
        second = session_client.post(_publish_url(workspace.slug, page.id))
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["anchor"] == second.json()["anchor"]
        assert DeployBoard.objects.filter(entity_name="page", entity_identifier=page.id).count() == 1

    @pytest.mark.django_db
    def test_revoke_disables_and_republish_rotates_token(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        publish_id = session_client.post(_publish_url(workspace.slug, page.id)).json()["id"]
        old_anchor = session_client.get(_publish_url(workspace.slug, page.id)).json()["anchor"]

        revoke = session_client.delete(_publish_revoke_url(workspace.slug, page.id, publish_id))
        assert revoke.status_code == 204
        publish = DeployBoard.objects.get(id=publish_id)
        assert publish.is_disabled is True
        assert publish.anchor != old_anchor
        assert session_client.get(_publish_url(workspace.slug, page.id)).json()["anchor"] is None

        api_client = APIClient()
        assert api_client.get(_public_page_url(old_anchor)).status_code == 404

        republished = session_client.post(_publish_url(workspace.slug, page.id))
        assert republished.status_code == 200
        assert republished.json()["anchor"] != old_anchor
        assert APIClient().get(_public_page_url(republished.json()["anchor"])).status_code == 200

    @pytest.mark.django_db
    def test_non_manager_cannot_publish(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        member = _member(workspace, _make_user("publish-member@plane.so"), role=15)
        guest = _member(workspace, _make_user("publish-guest@plane.so"), role=5)
        outsider = _make_user("publish-outsider@plane.so")

        for user in (member, guest, outsider):
            client = _client_for(user)
            assert client.post(_publish_url(workspace.slug, page.id)).status_code in (403, 404)

        anonymous = APIClient()
        assert anonymous.post(_publish_url(workspace.slug, page.id)).status_code in (401, 403)
        assert DeployBoard.objects.filter(entity_name="page", entity_identifier=page.id).count() == 0

    @pytest.mark.django_db
    def test_project_page_cannot_be_published(self, session_client, workspace, create_user):
        project_page = Page.objects.create(
            workspace=workspace, owned_by=create_user, name="Project Page", access=Page.PUBLIC_ACCESS, is_global=False
        )
        assert session_client.post(_publish_url(workspace.slug, project_page.id)).status_code == 404

    @pytest.mark.django_db
    def test_cross_workspace_publish_is_rejected(self, session_client, workspace, create_user):
        other_owner = _make_user("other-owner@plane.so")
        other = Workspace.objects.create(name="Other", slug="other-workspace", owner=other_owner)
        _member(other, other_owner, role=20)
        page = _wiki_page(other, other_owner)

        # `create_user` administers `workspace` only; probing a page of `other`
        # through it must look like a missing page, never a cross-workspace leak.
        response = session_client.post(_publish_url(workspace.slug, page.id))
        assert response.status_code == 404
        assert DeployBoard.objects.filter(entity_name="page", entity_identifier=page.id).count() == 0


@pytest.mark.contract
class TestPublishedPageRetrieval:
    @pytest.mark.django_db
    def test_public_retrieval_returns_sanitized_page(self, api_client, workspace, create_user):
        page = _wiki_page(
            workspace,
            create_user,
            name="Public Handbook",
            description_html="<p>Hello</p><script>alert('xss')</script><p>World</p>",
        )
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()["anchor"]

        response = api_client.get(_public_page_url(anchor))
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Public Handbook"
        assert body["anchor"] == anchor
        assert "<script" not in body["description_html"]
        assert "Hello" in body["description_html"]
        assert "World" in body["description_html"]

    @pytest.mark.django_db
    def test_unknown_and_revoked_tokens_are_not_found(self, api_client, workspace, create_user):
        assert api_client.get(_public_page_url("doesnotexist")).status_code == 404

        page = _wiki_page(workspace, create_user)
        published = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()
        _client_for(create_user).delete(_publish_revoke_url(workspace.slug, page.id, published["id"]))
        assert api_client.get(_public_page_url(published["anchor"])).status_code == 404

    @pytest.mark.django_db
    def test_archived_or_deleted_page_is_not_served(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()["anchor"]

        page.archived_at = date(2026, 1, 1)
        page.save()
        assert api_client.get(_public_page_url(anchor)).status_code == 404

        page.archived_at = None
        page.save()
        assert api_client.get(_public_page_url(anchor)).status_code == 200
        page.delete()
        assert api_client.get(_public_page_url(anchor)).status_code == 404

    @pytest.mark.django_db
    def test_published_page_only_does_not_expose_descendants(self, api_client, workspace, create_user):
        parent = _wiki_page(workspace, create_user, name="Parent", description_html="<p>parent</p>")
        child = _wiki_page(
            workspace, create_user, name="Secret Child", parent=parent, description_html="<p>secret-child</p>"
        )
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, parent.id)).json()["anchor"]

        body = api_client.get(_public_page_url(anchor)).json()
        assert body["name"] == "Parent"
        assert "secret-child" not in body["description_html"]

        # The child's own asset is unreachable through the parent's token.
        child_asset = _page_asset(workspace, child, create_user, name="child.png")
        assert api_client.get(_public_asset_url(anchor, child_asset.id)).status_code == 404


@pytest.mark.contract
class TestPublishedPageAssets:
    @pytest.mark.django_db
    def test_published_page_asset_is_served_after_publish_only(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        asset = _page_asset(workspace, page, create_user)
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()["anchor"]

        with mock.patch(PUBLIC_S3_STORAGE_PATH) as mock_storage:
            mock_storage.return_value.generate_presigned_url.return_value = "https://signed.example/x"
            response = api_client.get(_public_asset_url(anchor, asset.id))
        assert response.status_code == 302
        mock_storage.return_value.generate_presigned_url.assert_called_once()

    @pytest.mark.django_db
    def test_asset_of_a_different_unpublished_page_is_not_served(self, api_client, workspace, create_user):
        published_page = _wiki_page(workspace, create_user, name="Published")
        other_page = _wiki_page(workspace, create_user, name="Other")
        other_asset = _page_asset(workspace, other_page, create_user, name="other.png")
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, published_page.id)).json()["anchor"]

        with mock.patch(PUBLIC_S3_STORAGE_PATH) as mock_storage:
            response = api_client.get(_public_asset_url(anchor, other_asset.id))
        assert response.status_code == 404
        mock_storage.return_value.generate_presigned_url.assert_not_called()

    @pytest.mark.django_db
    def test_revoked_publication_stops_serving_assets(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        asset = _page_asset(workspace, page, create_user)
        published = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()
        _client_for(create_user).delete(_publish_revoke_url(workspace.slug, page.id, published["id"]))

        with mock.patch(PUBLIC_S3_STORAGE_PATH) as mock_storage:
            response = api_client.get(_public_asset_url(published["anchor"], asset.id))
        assert response.status_code == 404
        mock_storage.return_value.generate_presigned_url.assert_not_called()


@pytest.mark.contract
class TestPublishRateLimitAndProjectIsolation:
    @pytest.mark.django_db
    def test_public_page_endpoint_is_rate_limited(self, api_client, workspace, create_user, monkeypatch):
        from plane.throttles.page_publish import PagePublishRateThrottle

        monkeypatch.setattr(PagePublishRateThrottle, "rate", "1/minute", raising=False)

        page = _wiki_page(workspace, create_user)
        anchor = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()["anchor"]

        assert api_client.get(_public_page_url(anchor)).status_code == 200
        assert api_client.get(_public_page_url(anchor)).status_code == 429

    @pytest.mark.django_db
    def test_project_publish_path_is_unaffected(self, api_client, workspace, create_user):
        project_deploy_board = DeployBoard.objects.create(
            entity_name="project",
            entity_identifier=workspace.id,
            workspace=workspace,
            is_disabled=False,
        )

        # A project anchor is still served as project settings and never as a page.
        assert api_client.get(_project_settings_url(project_deploy_board.anchor)).status_code == 200
        assert api_client.get(_public_page_url(project_deploy_board.anchor)).status_code == 404

        # A page anchor is never served as project settings.
        page = _wiki_page(workspace, create_user)
        page_anchor = _client_for(create_user).post(_publish_url(workspace.slug, page.id)).json()["anchor"]
        assert api_client.get(_project_settings_url(page_anchor)).status_code == 404
