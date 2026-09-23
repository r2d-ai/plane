# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-06c realtime sharing permission matrix (plan §9.5, spec §5.3/§5.4/§22.6).

The live (Hocuspocus/Yjs) document never decides authorization itself: every
load (`GET .../pages/<id>/description/`) and persist
(`PATCH .../pages/<id>/description/`) call the same workspace-scoped Page API.
These contract tests pin the matrix the live service relies on, on exactly the
endpoints it calls, so a `workspace_page` session can never read or write a
page the share role forbids:

* VIEW    — may load the document bytes, must not persist, must not comment;
* COMMENT — may load and comment, must not persist document content;
* EDIT    — may load and persist;
* share removal — later loads/writes are denied (the statuses the live layer
  turns into a force-close, WIKI-02 §5.5).
"""

import base64

import pytest
from rest_framework.test import APIClient

from plane.db.models import Page, PageComment, PageShare, User, WorkspaceMember


def _description_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/description/"


def _comments_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/comments/"


def _comment_url(slug, page_id, comment_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/comments/{comment_id}/"


def _shares_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/shares/"


def _share_url(slug, page_id, share_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/shares/{share_id}/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _wiki_page(workspace, owner, name="P", access=Page.PRIVATE_ACCESS):
    return Page.objects.create(workspace=workspace, owned_by=owner, name=name, access=access, is_global=True)


def _share(workspace, page, member, role=PageShare.ROLE_VIEW):
    return PageShare.objects.create(workspace=workspace, page=page, member=member, role=role)


def _binary():
    """A base64 Yjs-shaped payload that passes the binary validator (>4 bytes)."""
    return base64.b64encode(b"\x00\x01\x02\x03\x04\x05binary").decode()


def _persist(client, slug, page_id, html="<p>Edited</p>"):
    return client.patch(
        _description_url(slug, page_id),
        {"description_binary": _binary(), "description_html": html},
        format="json",
    )


@pytest.mark.contract
class TestRealtimeSharingPermissionMatrix:
    @pytest.mark.django_db
    def test_view_role_can_load_but_cannot_persist(self, api_client, workspace, create_user):
        viewer = _member(workspace, _make_user("viewer@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, viewer, PageShare.ROLE_VIEW)

        api_client.force_authenticate(user=viewer)
        assert api_client.get(_description_url(workspace.slug, page.id)).status_code == 200

        assert _persist(api_client, workspace.slug, page.id).status_code == 403
        page.refresh_from_db()
        assert page.description_html != "<p>Edited</p>"

    @pytest.mark.django_db
    def test_view_role_cannot_comment(self, api_client, workspace, create_user):
        viewer = _member(workspace, _make_user("viewer@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, viewer, PageShare.ROLE_VIEW)

        api_client.force_authenticate(user=viewer)
        response = api_client.post(_comments_url(workspace.slug, page.id), {"comment_html": "<p>Hi</p>"}, format="json")
        assert response.status_code == 403, response.json()
        assert PageComment.objects.filter(page=page).count() == 0

    @pytest.mark.django_db
    def test_comment_role_can_comment_but_cannot_edit_document(self, api_client, workspace, create_user):
        commenter = _member(workspace, _make_user("commenter@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, commenter, PageShare.ROLE_COMMENT)

        api_client.force_authenticate(user=commenter)
        assert api_client.get(_description_url(workspace.slug, page.id)).status_code == 200

        response = api_client.post(
            _comments_url(workspace.slug, page.id),
            {"comment_html": "<p>Looks good</p>"},
            format="json",
        )
        assert response.status_code == 201, response.json()
        assert PageComment.objects.filter(page=page, actor=commenter).count() == 1

        before = page.description_html
        assert _persist(api_client, workspace.slug, page.id).status_code == 403
        page.refresh_from_db()
        assert page.description_html == before

    @pytest.mark.django_db
    def test_edit_role_can_edit_document(self, api_client, workspace, create_user):
        editor = _member(workspace, _make_user("editor@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, editor, PageShare.ROLE_EDIT)

        api_client.force_authenticate(user=editor)
        assert api_client.get(_description_url(workspace.slug, page.id)).status_code == 200
        assert _persist(api_client, workspace.slug, page.id).status_code == 200
        page.refresh_from_db()
        assert page.description_html == "<p>Edited</p>"

    @pytest.mark.django_db
    def test_comment_author_can_edit_and_delete_own_comment(self, api_client, workspace, create_user):
        commenter = _member(workspace, _make_user("commenter@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, commenter, PageShare.ROLE_COMMENT)

        api_client.force_authenticate(user=commenter)
        created = api_client.post(
            _comments_url(workspace.slug, page.id),
            {"comment_html": "<p>First</p>"},
            format="json",
        )
        assert created.status_code == 201
        comment_id = created.json()["id"]

        assert (
            api_client.patch(
                _comment_url(workspace.slug, page.id, comment_id),
                {"comment_html": "<p>Edited</p>"},
                format="json",
            ).status_code
            == 200
        )
        assert api_client.delete(_comment_url(workspace.slug, page.id, comment_id)).status_code == 204

    @pytest.mark.django_db
    def test_view_share_cannot_delete_someone_elses_comment(self, api_client, workspace, create_user):
        commenter = _member(workspace, _make_user("commenter@plane.so"))
        viewer = _member(workspace, _make_user("viewer@plane.so"))
        page = _wiki_page(workspace, create_user)
        _share(workspace, page, commenter, PageShare.ROLE_COMMENT)
        _share(workspace, page, viewer, PageShare.ROLE_VIEW)

        comment = PageComment.objects.create(
            workspace=workspace, page=page, actor=commenter, comment_html="<p>Mine</p>"
        )

        api_client.force_authenticate(user=viewer)
        assert api_client.delete(_comment_url(workspace.slug, page.id, comment.id)).status_code == 403
        assert PageComment.objects.filter(id=comment.id).exists()

    @pytest.mark.django_db
    def test_share_removal_blocks_later_loads_and_writes(self, session_client, workspace, create_user):
        editor = _member(workspace, _make_user("revoked@plane.so"))
        editor_client = _client_for(editor)
        page = _wiki_page(workspace, create_user)
        share_id = session_client.post(
            _shares_url(workspace.slug, page.id),
            {"member": str(editor.id), "role": PageShare.ROLE_EDIT},
            format="json",
        ).json()["id"]

        assert editor_client.get(_description_url(workspace.slug, page.id)).status_code == 200
        assert _persist(editor_client, workspace.slug, page.id).status_code == 200

        assert session_client.delete(_share_url(workspace.slug, page.id, share_id)).status_code == 204

        # The live layer force-closes on any of 401/403/404 (WIKI-02 §5.5); a
        # revoked member gets not-found because the private page no longer
        # resolves for them (spec §6.5).
        assert editor_client.get(_description_url(workspace.slug, page.id)).status_code == 404
        assert _persist(editor_client, workspace.slug, page.id).status_code == 404
