# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-09b contract tests: page/collection analytics (plan §12.3).

Covers view recording, the "preload is not a view" rule, the explicit privacy
policy (identification on/off, recording disabled), aggregates, CSV export,
Collection roll-ups, permission gating and BOLA/IDOR scoping.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionPage,
    PageView,
    User,
    Workspace,
    WorkspaceMember,
)


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _views_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/views/"


def _analytics_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/analytics/"


def _analytics_export_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/analytics/export/"


def _collection_analytics_url(slug, collection_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/analytics/"


def _collection_analytics_export_url(slug, collection_id):
    return f"/api/workspaces/{slug}/page-collections/{collection_id}/analytics/export/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="P", access=Page.PUBLIC_ACCESS):
    return Page.objects.create(
        workspace=workspace, owned_by=owner, name=name, access=access, is_global=True
    )


def _view(page, *, viewer=None, days_ago=0, collection=None):
    return PageView.objects.create(
        workspace=page.workspace,
        page=page,
        collection=collection,
        viewer=viewer,
        viewed_at=timezone.now() - timedelta(days=days_ago),
    )


@pytest.mark.contract
class TestPageViewRecording:
    @pytest.mark.django_db
    def test_record_view_creates_row(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        response = session_client.post(_views_url(workspace.slug, page.id), {}, format="json")

        assert response.status_code == 201
        assert PageView.objects.filter(page=page).count() == 1

    @pytest.mark.django_db
    def test_preload_is_not_counted(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        response = session_client.post(_views_url(workspace.slug, page.id), {"preload": True}, format="json")

        assert response.status_code == 204
        assert PageView.objects.filter(page=page).count() == 0

    @pytest.mark.django_db
    def test_recording_disabled_is_a_noop(self, session_client, workspace, create_user, settings):
        settings.PAGE_ANALYTICS_ENABLED = False
        page = _wiki_page(workspace, create_user)

        response = session_client.post(_views_url(workspace.slug, page.id), {}, format="json")

        assert response.status_code == 204
        assert PageView.objects.filter(page=page).count() == 0

    @pytest.mark.django_db
    def test_view_is_anonymous_when_identification_disabled(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        session_client.post(_views_url(workspace.slug, page.id), {}, format="json")

        assert PageView.objects.get(page=page).viewer_id is None

    @pytest.mark.django_db
    def test_viewer_stored_when_identification_enabled(self, session_client, workspace, create_user, settings):
        settings.PAGE_ANALYTICS_IDENTIFY_VIEWERS = True
        page = _wiki_page(workspace, create_user)

        session_client.post(_views_url(workspace.slug, page.id), {}, format="json")

        assert PageView.objects.get(page=page).viewer_id == create_user.id

    @pytest.mark.django_db
    def test_record_view_is_scoped_to_workspace(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-ws", owner=create_user)
        foreign_page = _wiki_page(other, create_user)

        response = session_client.post(_views_url(workspace.slug, foreign_page.id), {}, format="json")

        assert response.status_code == 404
        assert PageView.objects.filter(page=foreign_page).count() == 0

    @pytest.mark.django_db
    def test_record_view_counts_nearest_collection(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        collection = PageCollection.objects.create(workspace=workspace, name="Handbook")
        PageCollectionPage.objects.create(collection=collection, page=page, workspace=workspace)

        session_client.post(_views_url(workspace.slug, page.id), {}, format="json")

        assert PageView.objects.get(page=page).collection_id == collection.id


@pytest.mark.contract
class TestPageAnalyticsRead:
    @pytest.mark.django_db
    def test_owner_reads_aggregates(self, session_client, workspace, create_user, settings):
        settings.PAGE_ANALYTICS_IDENTIFY_VIEWERS = True
        page = _wiki_page(workspace, create_user)
        other = _member(workspace, _make_user("viewer@plane.so"))
        _view(page, viewer=create_user, days_ago=0)
        _view(page, viewer=create_user, days_ago=0)
        _view(page, viewer=other, days_ago=1)

        response = session_client.get(_analytics_url(workspace.slug, page.id))

        assert response.status_code == 200
        body = response.json()
        assert body["total_views"] == 3
        assert body["unique_viewers"] == 2
        assert body["identify_viewers"] is True
        assert len(body["timeline"]) == 2
        assert sum(item["views"] for item in body["timeline"]) == 3
        assert {v["viewer"] for v in body["viewers"]} == {str(create_user.id), str(other.id)}

    @pytest.mark.django_db
    def test_unique_viewers_hidden_when_identification_disabled(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        _view(page, viewer=create_user)

        response = session_client.get(_analytics_url(workspace.slug, page.id))

        assert response.status_code == 200
        body = response.json()
        assert body["total_views"] == 1
        assert body["unique_viewers"] is None
        assert body["viewers"] == []

    @pytest.mark.django_db
    def test_window_filters_old_views(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        _view(page, days_ago=0)
        _view(page, days_ago=40)

        response = session_client.get(_analytics_url(workspace.slug, page.id))

        assert response.status_code == 200
        assert response.json()["total_views"] == 1

    @pytest.mark.django_db
    def test_member_without_manage_cannot_read_analytics(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        member = _member(workspace, _make_user("member@plane.so"))
        client = _client_for(member)

        response = client.get(_analytics_url(workspace.slug, page.id))

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_analytics_scoped_to_workspace(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-analytics", owner=create_user)
        foreign_page = _wiki_page(other, create_user)

        response = session_client.get(_analytics_url(workspace.slug, foreign_page.id))

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_csv_export_streams_rows(self, session_client, workspace, create_user, settings):
        settings.PAGE_ANALYTICS_IDENTIFY_VIEWERS = True
        page = _wiki_page(workspace, create_user, name="Runbook")
        _view(page, viewer=create_user)

        response = session_client.get(_analytics_export_url(workspace.slug, page.id))

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        content = b"".join(response.streaming_content).decode("utf-8")
        assert "viewed_at" in content
        assert str(page.id) in content
        assert create_user.email in content

    @pytest.mark.django_db
    def test_csv_export_omits_viewer_when_identification_disabled(
        self, session_client, workspace, create_user
    ):
        page = _wiki_page(workspace, create_user, name="Runbook")
        _view(page, viewer=create_user)

        response = session_client.get(_analytics_export_url(workspace.slug, page.id))

        assert response.status_code == 200
        content = b"".join(response.streaming_content).decode("utf-8")
        header = content.splitlines()[0]
        assert "viewer_email" not in header
        assert create_user.email not in content


@pytest.mark.contract
class TestCollectionAnalytics:
    @pytest.mark.django_db
    def test_admin_reads_collection_rollup(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        collection = PageCollection.objects.create(workspace=workspace, name="Handbook")
        PageCollectionPage.objects.create(collection=collection, page=page, workspace=workspace)
        _view(page, collection=collection)
        _view(page, collection=collection)

        response = session_client.get(_collection_analytics_url(workspace.slug, collection.id))

        assert response.status_code == 200
        body = response.json()
        assert body["collection"] == str(collection.id)
        assert body["collection_name"] == "Handbook"
        assert body["total_views"] == 2

    @pytest.mark.django_db
    def test_member_cannot_read_collection_rollup(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member2@plane.so"))
        collection = PageCollection.objects.create(workspace=workspace, name="Private Ops")
        client = _client_for(member)

        response = client.get(_collection_analytics_url(workspace.slug, collection.id))

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_collection_analytics_scoped_to_workspace(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-colls", owner=create_user)
        foreign = PageCollection.objects.create(workspace=other, name="Foreign")

        response = session_client.get(_collection_analytics_url(workspace.slug, foreign.id))

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_collection_csv_export(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user, name="Runbook")
        collection = PageCollection.objects.create(workspace=workspace, name="Handbook")
        _view(page, collection=collection)

        response = session_client.get(_collection_analytics_export_url(workspace.slug, collection.id))

        assert response.status_code == 200
        content = b"".join(response.streaming_content).decode("utf-8")
        assert str(page.id) in content
