# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-09b contract tests: comment moderation (plan §12.5).

Covers hide/unhide, mandatory reason, workspace-admin permission, audit-trail
preservation and the list-visibility rule (hidden comments are excluded for
regular members and flagged for moderators).
"""

import pytest
from rest_framework.test import APIClient

from plane.db.models import (
    Page,
    PageComment,
    PageCommentModeration,
    User,
    Workspace,
    WorkspaceMember,
)


def _comments_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/comments/"


def _hide_url(slug, page_id, comment_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/comments/{comment_id}/hide/"


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


def _comment(page, actor, body="<p>hello</p>"):
    return PageComment.objects.create(
        workspace=page.workspace,
        page=page,
        actor=actor,
        comment_html=body,
    )


@pytest.mark.contract
class TestCommentModeration:
    @pytest.mark.django_db
    def test_admin_hides_comment_with_reason(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        author = _member(workspace, _make_user("author@plane.so"))
        comment = _comment(page, author)

        response = session_client.post(
            _hide_url(workspace.slug, page.id, comment.id), {"reason": "spam"}, format="json"
        )

        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.is_hidden is True
        assert comment.hidden_reason == "spam"
        assert comment.hidden_by_id == create_user.id
        assert comment.hidden_at is not None
        # Audit trail survives and the comment body is preserved.
        assert comment.comment_html == "<p>hello</p>"
        moderation = PageCommentModeration.objects.get(comment=comment)
        assert moderation.action == PageCommentModeration.ACTION_HIDE
        assert moderation.reason == "spam"
        assert moderation.actor_id == create_user.id

    @pytest.mark.django_db
    def test_hide_requires_reason(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        comment = _comment(page, create_user)

        response = session_client.post(_hide_url(workspace.slug, page.id, comment.id), {}, format="json")

        assert response.status_code == 400
        comment.refresh_from_db()
        assert comment.is_hidden is False
        assert PageCommentModeration.objects.count() == 0

    @pytest.mark.django_db
    def test_non_admin_owner_cannot_hide(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        member = _member(workspace, _make_user("member@plane.so"), role=15)
        comment = _comment(page, create_user)
        client = _client_for(member)

        response = client.post(_hide_url(workspace.slug, page.id, comment.id), {"reason": "nope"}, format="json")

        assert response.status_code == 403
        comment.refresh_from_db()
        assert comment.is_hidden is False

    @pytest.mark.django_db
    def test_comment_author_cannot_hide_own_comment(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        author = _member(workspace, _make_user("author2@plane.so"), role=15)
        comment = _comment(page, author)
        client = _client_for(author)

        response = client.post(_hide_url(workspace.slug, page.id, comment.id), {"reason": "self"}, format="json")

        assert response.status_code == 403

    @pytest.mark.django_db
    def test_unhide_restores_visibility_and_logs_action(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        comment = _comment(page, create_user)
        session_client.post(_hide_url(workspace.slug, page.id, comment.id), {"reason": "spam"}, format="json")

        response = session_client.delete(_hide_url(workspace.slug, page.id, comment.id))

        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.is_hidden is False
        assert comment.hidden_at is None
        actions = list(
            PageCommentModeration.objects.filter(comment=comment).values_list("action", flat=True)
        )
        assert PageCommentModeration.ACTION_HIDE in actions
        assert PageCommentModeration.ACTION_UNHIDE in actions

    @pytest.mark.django_db
    def test_hidden_comment_hidden_from_members_but_visible_to_admin(
        self, session_client, workspace, create_user
    ):
        page = _wiki_page(workspace, create_user)
        member = _member(workspace, _make_user("reader@plane.so"), role=15)
        comment = _comment(page, member, body="<p>off topic</p>")
        session_client.post(_hide_url(workspace.slug, page.id, comment.id), {"reason": "spam"}, format="json")

        member_response = _client_for(member).get(_comments_url(workspace.slug, page.id))
        admin_response = session_client.get(_comments_url(workspace.slug, page.id))

        assert member_response.status_code == 200
        assert member_response.json() == []
        assert admin_response.status_code == 200
        [payload] = admin_response.json()
        assert payload["is_hidden"] is True
        assert payload["hidden_reason"] == "spam"
        assert payload["comment_html"] == "<p>off topic</p>"

    @pytest.mark.django_db
    def test_hide_is_scoped_to_page(self, session_client, workspace, create_user):
        page = _wiki_page(workspace, create_user)
        other_page = _wiki_page(workspace, create_user, name="Other")
        comment = _comment(page, create_user)

        response = session_client.post(
            _hide_url(workspace.slug, other_page.id, comment.id), {"reason": "spam"}, format="json"
        )

        assert response.status_code == 404
        comment.refresh_from_db()
        assert comment.is_hidden is False

    @pytest.mark.django_db
    def test_hide_is_scoped_to_workspace(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-moderate", owner=create_user)
        foreign_page = _wiki_page(other, create_user)
        comment = _comment(foreign_page, create_user)

        response = session_client.post(
            _hide_url(workspace.slug, foreign_page.id, comment.id), {"reason": "spam"}, format="json"
        )

        assert response.status_code == 404
        comment.refresh_from_db()
        assert comment.is_hidden is False
