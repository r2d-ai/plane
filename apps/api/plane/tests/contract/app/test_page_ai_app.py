# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-10 contract tests: stable Wiki <-> AI endpoints (plan §13.1).

Covers the versioned context envelope, deterministic summarize/label
suggestions, agent edits through the normal versioned write pipeline, the
natural-language search discoverability policy, the durable event feed and its
permission filtering, BOLA/IDOR scoping and the feature flag.
"""

import pytest
from rest_framework.test import APIClient

from plane.db.models import Label, Page, User, WikiEvent, Workspace, WorkspaceMember


def _context_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/ai/context/"


def _summarize_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/ai/summarize/"


def _apply_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/ai/apply/"


def _labels_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/ai/label-suggestions/"


def _search_url(slug):
    return f"/api/workspaces/{slug}/wiki/ai/search/"


def _events_url(slug):
    return f"/api/workspaces/{slug}/wiki/ai/events/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _wiki_page(workspace, owner, name="Page", html="<p>Hello world.</p>", access=Page.PUBLIC_ACCESS, parent=None):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=access,
        is_global=True,
        parent=parent,
        description_html=html,
    )


@pytest.mark.contract
class TestWorkspacePageAIContext:
    @pytest.mark.django_db
    def test_owner_gets_versioned_context(self, session_client, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Handbook")
        child = _wiki_page(workspace, create_user, name="Getting Started", parent=root)

        response = session_client.get(_context_url(workspace.slug, child.id))

        assert response.status_code == 200
        body = response.json()
        assert body["schema_version"]
        assert body["page"]["id"] == str(child.id)
        assert body["page"]["description_html"] == "<p>Hello world.</p>"
        assert [item["name"] for item in body["hierarchy"]["breadcrumbs"]] == ["Handbook", "Getting Started"]
        assert body["capabilities"]["edit"] is True

    @pytest.mark.django_db
    def test_non_member_is_forbidden(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        outsider = _make_user("outsider@plane.so")

        api_client.force_authenticate(user=outsider)
        assert api_client.get(_context_url(workspace.slug, page.id)).status_code == 403

    @pytest.mark.django_db
    def test_private_page_hidden_from_member(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)

        api_client.force_authenticate(user=member)
        assert api_client.get(_context_url(workspace.slug, page.id)).status_code == 404

    @pytest.mark.django_db
    def test_cross_workspace_page_not_found(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-workspace", owner=create_user)
        foreign = _wiki_page(other, create_user)

        assert session_client.get(_context_url(workspace.slug, foreign.id)).status_code == 404

    @pytest.mark.django_db
    def test_disabled_flag_returns_404(self, settings, session_client, workspace, create_user):
        settings.WIKI_AI_ENABLED = False
        page = _wiki_page(workspace, create_user)

        response = session_client.get(_context_url(workspace.slug, page.id))
        assert response.status_code == 404
        assert response.json()["error_code"] == "WIKI_AI_DISABLED"


@pytest.mark.contract
class TestWorkspacePageAISummarize:
    @pytest.mark.django_db
    def test_summarize_returns_local_summary(self, session_client, workspace, create_user):
        page = _wiki_page(
            workspace,
            create_user,
            html="<p>The wiki documents onboarding. Onboarding steps are listed here. "
            "The onboarding checklist is short. Unrelated filler sentence.</p>",
        )

        response = session_client.post(_summarize_url(workspace.slug, page.id), {}, format="json")

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "local"
        assert "onboarding" in body["summary"].lower()


@pytest.mark.contract
class TestWorkspacePageAIApply:
    @pytest.mark.django_db
    def test_member_with_edit_applies_edit_and_emits_event(self, api_client, workspace, create_user):
        member = _member(workspace, _make_user("editor@plane.so"))
        page = _wiki_page(workspace, create_user, html="<p>old</p>")

        api_client.force_authenticate(user=member)
        response = api_client.post(
            _apply_url(workspace.slug, page.id),
            {"description_html": "<p>new agent content</p>"},
            format="json",
        )

        assert response.status_code == 200
        page.refresh_from_db()
        assert page.description_html == "<p>new agent content</p>"
        assert WikiEvent.objects.filter(page=page, event_type=WikiEvent.PAGE_AI_EDIT).exists()
        assert response.json()["context"]["page"]["description_html"] == "<p>new agent content</p>"

    @pytest.mark.django_db
    def test_guest_cannot_apply(self, api_client, workspace, create_user):
        guest = _member(workspace, _make_user("guest@plane.so"), role=5)
        page = _wiki_page(workspace, create_user)

        api_client.force_authenticate(user=guest)
        response = api_client.post(
            _apply_url(workspace.slug, page.id),
            {"description_html": "<p>nope</p>"},
            format="json",
        )
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_locked_page_rejected(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        page.is_locked = True
        page.save(update_fields=["is_locked"])

        response = session_client.post(
            _apply_url(workspace.slug, page.id),
            {"description_html": "<p>nope</p>"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_LOCKED"

    @pytest.mark.django_db
    def test_apply_rejects_script_content(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)

        response = session_client.post(
            _apply_url(workspace.slug, page.id),
            {"description_html": "<script>alert(1)</script><p>ok</p>"},
            format="json",
        )

        assert response.status_code == 200
        page.refresh_from_db()
        assert "<script" not in page.description_html


@pytest.mark.contract
class TestWorkspacePageAILabelSuggestions:
    @pytest.mark.django_db
    def test_suggests_matching_workspace_label(self, session_client, workspace, create_user):
        Label.objects.create(workspace=workspace, name="onboarding", project=None)
        page = _wiki_page(workspace, create_user, name="Onboarding guide", html="<p>onboarding steps</p>")

        response = session_client.post(_labels_url(workspace.slug, page.id), {}, format="json")

        assert response.status_code == 200
        names = [item["name"] for item in response.json()["suggestions"]]
        assert "onboarding" in names

    @pytest.mark.django_db
    def test_excludes_labels_already_applied(self, session_client, workspace, create_user):
        from plane.db.models import PageLabel

        label = Label.objects.create(workspace=workspace, name="onboarding", project=None)
        page = _wiki_page(workspace, create_user, name="Onboarding guide")
        PageLabel.objects.create(workspace=workspace, page=page, label=label)

        response = session_client.post(_labels_url(workspace.slug, page.id), {}, format="json")
        assert response.json()["suggestions"] == []


@pytest.mark.contract
class TestWorkspaceWikiAISearch:
    @pytest.mark.django_db
    def test_search_finds_public_page(self, session_client, workspace, create_user):
        _wiki_page(workspace, create_user, name="Onboarding handbook", html="<p>steps</p>")

        response = session_client.post(_search_url(workspace.slug), {"query": "onboarding"}, format="json")

        assert response.status_code == 200
        names = [item["name"] for item in response.json()["results"]]
        assert "Onboarding handbook" in names

    @pytest.mark.django_db
    def test_search_excludes_private_pages(self, session_client, workspace, create_user):
        _wiki_page(workspace, create_user, name="Secret onboarding", access=Page.PRIVATE_ACCESS)

        response = session_client.post(_search_url(workspace.slug), {"query": "onboarding"}, format="json")

        assert response.status_code == 200
        assert response.json()["results"] == []

    @pytest.mark.django_db
    def test_non_member_forbidden(self, api_client, workspace, create_user):
        outsider = _make_user("outsider-search@plane.so")
        api_client.force_authenticate(user=outsider)
        assert api_client.post(_search_url(workspace.slug), {"query": "x"}, format="json").status_code == 403


@pytest.mark.contract
class TestWorkspaceWikiAIEvents:
    @pytest.mark.django_db
    def test_create_page_emits_event(self, session_client, workspace, create_user):
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/pages/",
            {"name": "Evented"},
            format="json",
        )
        assert response.status_code == 201

        events = session_client.get(_events_url(workspace.slug)).json()["events"]
        assert any(event["event_type"] == WikiEvent.PAGE_CREATED for event in events)

    @pytest.mark.django_db
    def test_private_page_event_not_leaked_to_member(self, api_client, workspace, create_user):
        page = _wiki_page(workspace, create_user, name="Private secret", access=Page.PRIVATE_ACCESS)
        WikiEvent.objects.create(
            workspace=workspace,
            page=page,
            page_name=page.name,
            event_type=WikiEvent.PAGE_CREATED,
        )
        member = _member(workspace, _make_user("event-member@plane.so"))

        api_client.force_authenticate(user=member)
        events = api_client.get(_events_url(workspace.slug)).json()["events"]
        assert all(event["page_id"] != str(page.id) for event in events)

    @pytest.mark.django_db
    def test_invalid_since_rejected(self, session_client, workspace, create_user):
        response = session_client.get(_events_url(workspace.slug) + "?since=not-a-date")
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_SINCE"
