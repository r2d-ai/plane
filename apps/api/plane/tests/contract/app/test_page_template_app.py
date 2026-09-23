# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-07a contract tests: page templates (spec §16; plan §10.1).

Covers workspace-scoped visibility, save-page-as-template, create-page-from-
template, content preservation, management permissions, BOLA/IDOR scoping and
the tenant boundary against the Company Wiki open-read override.
"""

import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    Page,
    PageTemplate,
    User,
    Workspace,
    WorkspaceMember,
)


def _templates_url(slug):
    return f"/api/workspaces/{slug}/page-templates/"


def _template_url(slug, template_id):
    return f"/api/workspaces/{slug}/page-templates/{template_id}/"


def _template_use_url(slug, template_id):
    return f"/api/workspaces/{slug}/page-templates/{template_id}/use/"


def _save_as_template_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/save-as-template/"


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="P", html="<p>hello</p>"):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=Page.PUBLIC_ACCESS,
        is_global=True,
        description_html=html,
    )


def _template(workspace, name, created_by=None, html="<p>body</p>"):
    template = PageTemplate.objects.create(
        workspace=workspace,
        name=name,
        description_html=html,
        description_json={},
    )
    # ``BaseModel.save`` clears ``created_by`` when there is no request user
    # (crum), so pin the creator explicitly for the management-permission tests.
    if created_by is not None:
        PageTemplate.objects.filter(pk=template.pk).update(created_by=created_by)
        template.created_by_id = created_by.id
    return template


@pytest.mark.contract
class TestPageTemplateCrud:
    @pytest.mark.django_db
    def test_create_template(self, session_client, workspace):
        response = session_client.post(_templates_url(workspace.slug), {"name": "Weekly"}, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Weekly"
        assert body["workspace"] == str(workspace.id)
        assert PageTemplate.objects.filter(workspace=workspace).count() == 1

    @pytest.mark.django_db
    def test_blank_name_rejected(self, session_client, workspace):
        response = session_client.post(_templates_url(workspace.slug), {"name": "   "}, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_guest_cannot_create(self, workspace, create_user):
        guest = _member(workspace, _make_user("guest@plane.so"), role=5)
        response = _client_for(guest).post(_templates_url(workspace.slug), {"name": "Nope"}, format="json")
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_list_is_workspace_scoped(self, session_client, workspace, create_user):
        mine = _template(workspace, "Mine", created_by=create_user)

        other_workspace = Workspace.objects.create(name="Other", owner=create_user, slug="other-workspace")
        WorkspaceMember.objects.create(workspace=other_workspace, member=create_user, role=20)
        _template(other_workspace, "Theirs", created_by=create_user)

        response = session_client.get(_templates_url(workspace.slug))
        assert response.status_code == 200
        assert {item["id"] for item in response.json()} == {str(mine.id)}

    @pytest.mark.django_db
    def test_member_sees_all_workspace_templates(self, session_client, workspace, create_user):
        member = _member(workspace, _make_user("member@plane.so"))
        first = _template(workspace, "First", created_by=create_user)
        second = _template(workspace, "Second", created_by=create_user)

        response = _client_for(member).get(_templates_url(workspace.slug))
        assert response.status_code == 200
        assert {item["id"] for item in response.json()} == {str(first.id), str(second.id)}

    @pytest.mark.django_db
    def test_rename_requires_owner_or_admin(self, session_client, workspace, create_user):
        owner = _member(workspace, _make_user("owner@plane.so"))
        other = _member(workspace, _make_user("other@plane.so"))
        template = _template(workspace, "Owned", created_by=owner)

        # A different member cannot rename.
        forbidden = _client_for(other).patch(
            _template_url(workspace.slug, template.id), {"name": "Hijacked"}, format="json"
        )
        assert forbidden.status_code == 403

        # The creator can.
        allowed = _client_for(owner).patch(
            _template_url(workspace.slug, template.id), {"name": "Renamed"}, format="json"
        )
        assert allowed.status_code == 200
        assert allowed.json()["name"] == "Renamed"

        # A workspace admin can too.
        admin_ok = session_client.patch(
            _template_url(workspace.slug, template.id), {"name": "Admin renamed"}, format="json"
        )
        assert admin_ok.status_code == 200

    @pytest.mark.django_db
    def test_delete_requires_owner_or_admin(self, session_client, workspace, create_user):
        owner = _member(workspace, _make_user("owner@plane.so"))
        other = _member(workspace, _make_user("other@plane.so"))
        template = _template(workspace, "Owned", created_by=owner)

        assert _client_for(other).delete(_template_url(workspace.slug, template.id)).status_code == 403
        assert _client_for(owner).delete(_template_url(workspace.slug, template.id)).status_code == 204
        assert PageTemplate.objects.filter(id=template.id, deleted_at__isnull=True).count() == 0


@pytest.mark.contract
class TestSavePageAsTemplate:
    @pytest.mark.django_db
    def test_save_page_as_template_copies_document(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user, name="Runbook", html="<p>steps</p>")

        response = session_client.post(_save_as_template_url(workspace.slug, page.id), {}, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Runbook"
        template = PageTemplate.objects.get(id=body["id"])
        assert template.workspace_id == workspace.id
        assert template.description_html == "<p>steps</p>"
        assert template.description_stripped == "steps"
        assert template.created_by_id == create_user.id

    @pytest.mark.django_db
    def test_save_page_as_template_custom_name(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user, name="Runbook")
        response = session_client.post(
            _save_as_template_url(workspace.slug, page.id), {"name": "Ops template"}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Ops template"

    @pytest.mark.django_db
    def test_save_page_as_template_is_workspace_scoped(self, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        other_workspace = Workspace.objects.create(name="Other", owner=create_user, slug="other-workspace")
        WorkspaceMember.objects.create(workspace=other_workspace, member=create_user, role=20)

        response = _client_for(create_user).post(_save_as_template_url(other_workspace.slug, page.id), {}, format="json")
        assert response.status_code == 404


@pytest.mark.contract
class TestCreatePageFromTemplate:
    @pytest.mark.django_db
    def test_create_page_from_template_copies_content(self, session_client, workspace, create_user):
        template = _template(workspace, "Meeting notes", created_by=create_user, html="<p>agenda</p>")

        response = session_client.post(_template_use_url(workspace.slug, template.id), {}, format="json")

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Meeting notes"
        page = Page.objects.get(id=body["id"])
        assert page.workspace_id == workspace.id
        assert page.is_global is True
        assert page.owned_by_id == create_user.id
        assert page.description_html == "<p>agenda</p>"

    @pytest.mark.django_db
    def test_create_page_from_template_honours_name_and_parent(self, session_client, workspace, create_user):
        parent = _wiki_page(workspace, create_user, name="Parent")
        template = _template(workspace, "Child template", created_by=create_user)

        response = session_client.post(
            _template_use_url(workspace.slug, template.id),
            {"name": "Child", "parent": str(parent.id)},
            format="json",
        )

        assert response.status_code == 201
        page = Page.objects.get(id=response.json()["id"])
        assert page.name == "Child"
        assert page.parent_id == parent.id
        assert page.parent_id != template.id

    @pytest.mark.django_db
    def test_created_page_is_listed_in_workspace_wiki(self, session_client, workspace, create_user):
        template = _template(workspace, "Listed", created_by=create_user, html="<p>x</p>")
        page_id = session_client.post(_template_use_url(workspace.slug, template.id), {}, format="json").json()["id"]

        listed = session_client.get(_pages_url(workspace.slug))
        assert listed.status_code == 200
        assert page_id in {item["id"] for item in listed.json()}

    @pytest.mark.django_db
    def test_project_parent_is_rejected(self, session_client, workspace, create_user):
        # A Project Page (is_global=False) cannot be the parent of a Wiki page.
        project_page = Page.objects.create(
            workspace=workspace,
            owned_by=create_user,
            name="Project page",
            is_global=False,
        )
        template = _template(workspace, "T", created_by=create_user)

        response = session_client.post(
            _template_use_url(workspace.slug, template.id),
            {"parent": str(project_page.id)},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "PAGE_PARENT_CROSS_SCOPE"

    @pytest.mark.django_db
    def test_guest_cannot_create_page_from_template(self, workspace, create_user):
        guest = _member(workspace, _make_user("guest@plane.so"), role=5)
        template = _template(workspace, "T", created_by=create_user)

        response = _client_for(guest).post(_template_use_url(workspace.slug, template.id), {}, format="json")
        assert response.status_code == 403


@pytest.mark.contract
class TestPageTemplateTenantBoundary:
    @pytest.mark.django_db
    def test_foreign_template_uuid_is_not_found(self, workspace, create_user):
        template = _template(workspace, "Secret", created_by=create_user)
        other_workspace = Workspace.objects.create(name="Other", owner=create_user, slug="other-workspace")
        WorkspaceMember.objects.create(workspace=other_workspace, member=create_user, role=20)
        client = _client_for(create_user)

        assert client.get(_template_url(other_workspace.slug, template.id)).status_code == 404
        assert client.post(_template_use_url(other_workspace.slug, template.id), {}, format="json").status_code == 404

    @pytest.mark.django_db
    def test_open_read_does_not_expose_templates(self, settings, workspace, create_user):
        outsider = _make_user("outsider@plane.so")
        _template(workspace, "Internal", created_by=create_user)
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

        response = _client_for(outsider).get(_templates_url(workspace.slug))
        assert response.status_code == 403

    @pytest.mark.django_db
    def test_anonymous_is_denied(self, api_client, workspace, create_user):
        _template(workspace, "Internal", created_by=create_user)
        assert api_client.get(_templates_url(workspace.slug)).status_code in (401, 403)
