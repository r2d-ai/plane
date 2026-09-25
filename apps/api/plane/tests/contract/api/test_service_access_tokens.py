# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from rest_framework import status

from plane.api.service_tokens import (
    SCOPE_LEVEL_INSTANCE,
    SCOPE_LEVEL_WORKSPACE,
    create_service_access_token,
    revoke_service_access_token,
)
from plane.db.models import APIToken, Page, Project, ProjectMember, Workspace, WorkspaceMember


def make_workspace(owner, *, slug):
    return Workspace.objects.create(
        name=slug.replace("-", " ").title(),
        owner=owner,
        slug=slug,
    )


def make_private_project(workspace, *, name, identifier):
    return Project.objects.create(
        name=name,
        identifier=identifier,
        workspace=workspace,
        network=0,
    )


def api_client_for_service_token(api_client, raw_token):
    api_client.credentials(HTTP_X_API_KEY=raw_token)
    return api_client


@pytest.mark.contract
class TestServiceAccessTokenContract:
    @pytest.mark.django_db
    def test_workspace_token_secret_is_hash_only_and_only_returned_on_create(
        self, session_client, create_user, workspace
    ):
        url = f"/api/workspaces/{workspace.slug}/service-tokens/"
        payload = {
            "label": "MCP Daily Digest",
            "description": "Read-only workspace digest",
            "scopes": ["workspaces:read", "projects:read"],
        }

        response = session_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["token"].startswith("plane_wsat_")

        token = APIToken.objects.get(pk=response.data["id"])
        assert token.token is None
        assert token.token_hash
        assert token.token_prefix
        assert token.scope_level == SCOPE_LEVEL_WORKSPACE
        assert token.workspace_id == workspace.id
        assert token.user.is_bot is True
        assert token.user.bot_type == "SERVICE_TOKEN"

        list_response = session_client.get(url)
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.data) == 1
        assert "token" not in list_response.data[0]
        assert "token_hash" not in list_response.data[0]

    @pytest.mark.django_db
    def test_workspace_token_reads_private_project_without_synthetic_membership(
        self, api_client, create_user, workspace
    ):
        project = make_private_project(
            workspace,
            name="Private Digest Project",
            identifier="PDP",
        )
        token, raw_token = create_service_access_token(
            label="Digest bot",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["workspaces:read", "projects:read"],
            workspace=workspace,
        )

        client = api_client_for_service_token(api_client, raw_token)
        response = client.get(f"/api/v1/workspaces/{workspace.slug}/projects/")

        assert response.status_code == status.HTTP_200_OK, response.data
        result_ids = {str(item["id"]) for item in response.data["results"]}
        assert str(project.id) in result_ids

        assert not ProjectMember.objects.filter(
            project=project,
            member=token.user,
        ).exists()

    @pytest.mark.django_db
    def test_workspace_token_cannot_escape_bound_workspace(
        self, api_client, create_user, workspace
    ):
        other_workspace = make_workspace(
            create_user,
            slug=f"other-{uuid4().hex[:8]}",
        )
        make_private_project(
            other_workspace,
            name="Other Private Project",
            identifier="OPP",
        )
        _token, raw_token = create_service_access_token(
            label="Bound agent",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["workspaces:read", "projects:read"],
            workspace=workspace,
        )

        client = api_client_for_service_token(api_client, raw_token)
        response = client.get(
            f"/api/v1/workspaces/{other_workspace.slug}/projects/"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_missing_resource_scope_is_denied(
        self, api_client, create_user, workspace
    ):
        _token, raw_token = create_service_access_token(
            label="Workspace discovery only",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["workspaces:read"],
            workspace=workspace,
        )

        client = api_client_for_service_token(api_client, raw_token)
        response = client.get(f"/api/v1/workspaces/{workspace.slug}/projects/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_instance_token_discovers_and_reads_all_workspaces(
        self, api_client, create_user, workspace
    ):
        first_project = make_private_project(
            workspace,
            name="First Private Project",
            identifier="FPP",
        )
        second_workspace = make_workspace(
            create_user,
            slug=f"second-{uuid4().hex[:8]}",
        )
        second_project = make_private_project(
            second_workspace,
            name="Second Private Project",
            identifier="SPP",
        )

        token, raw_token = create_service_access_token(
            label="Instance digest",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_INSTANCE,
            scopes=["workspaces:read", "projects:read"],
        )
        client = api_client_for_service_token(api_client, raw_token)

        context_response = client.get("/api/v1/auth/context/")
        assert context_response.status_code == status.HTTP_200_OK
        assert context_response.data["principal_type"] == "service"
        assert context_response.data["scope_level"] == "instance"
        assert context_response.data["workspace"] is None
        assert "token" not in context_response.data
        assert "token_hash" not in context_response.data

        workspaces_response = client.get("/api/v1/workspaces/")
        assert workspaces_response.status_code == status.HTTP_200_OK
        workspace_ids = {str(item["id"]) for item in workspaces_response.data}
        assert str(workspace.id) in workspace_ids
        assert str(second_workspace.id) in workspace_ids

        first_response = client.get(
            f"/api/v1/workspaces/{workspace.slug}/projects/"
        )
        second_response = client.get(
            f"/api/v1/workspaces/{second_workspace.slug}/projects/"
        )
        assert first_response.status_code == status.HTTP_200_OK
        assert second_response.status_code == status.HTTP_200_OK
        assert str(first_project.id) in {
            str(item["id"]) for item in first_response.data["results"]
        }
        assert str(second_project.id) in {
            str(item["id"]) for item in second_response.data["results"]
        }

        assert not ProjectMember.objects.filter(member=token.user).exists()

    @pytest.mark.django_db
    def test_workspace_token_reads_private_wiki_page(
        self, api_client, create_user, workspace
    ):
        from plane.db.models import Page

        page = Page.objects.create(
            workspace=workspace,
            name="Private runbook",
            description_html="<p>Internal recovery procedure</p>",
            owned_by=create_user,
            access=Page.PRIVATE_ACCESS,
            is_global=True,
        )
        token, raw_token = create_service_access_token(
            label="Wiki digest",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:read"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.get(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/"
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert str(page.id) in {
            str(item["id"]) for item in response.data["results"]
        }
        assert not ProjectMember.objects.filter(member=token.user).exists()

    @pytest.mark.django_db
    def test_revoked_service_token_stops_authenticating(
        self, api_client, create_user, workspace
    ):
        token, raw_token = create_service_access_token(
            label="Revoke me",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["workspaces:read"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        before = client.get("/api/v1/auth/context/")
        assert before.status_code == status.HTTP_200_OK

        revoke_service_access_token(token, create_user)

        after = client.get("/api/v1/auth/context/")
        assert after.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }



@pytest.mark.contract
class TestServiceAccessTokenWikiWriteContract:
    @pytest.mark.django_db
    def test_workspace_write_token_creates_page_without_membership(
        self, api_client, create_user, workspace
    ):
        token, raw_token = create_service_access_token(
            label="Wiki writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:read", "wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.post(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/",
            {
                "name": "Agent runbook",
                "description_html": "<p>Safe</p><script>alert(1)</script>",
                "description_json": {"type": "doc"},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        page = Page.objects.get(pk=response.data["id"])
        assert page.is_global is True
        assert page.workspace_id == workspace.id
        assert page.owned_by_id == token.user_id
        assert page.access == Page.PUBLIC_ACCESS
        assert "<script" not in page.description_html
        assert not WorkspaceMember.objects.filter(workspace=workspace, member=token.user).exists()
        assert not ProjectMember.objects.filter(member=token.user).exists()

    @pytest.mark.django_db
    def test_read_only_token_cannot_create_or_update_wiki(
        self, api_client, create_user, workspace
    ):
        page = Page.objects.create(
            workspace=workspace,
            name="Existing",
            owned_by=create_user,
            is_global=True,
        )
        _token, raw_token = create_service_access_token(
            label="Read only",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:read"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        create_response = client.post(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/",
            {"name": "Denied"},
            format="json",
        )
        update_response = client.patch(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/{page.id}/",
            {"name": "Denied"},
            format="json",
        )

        assert create_response.status_code == status.HTTP_403_FORBIDDEN
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        page.refresh_from_db()
        assert page.name == "Existing"

    @pytest.mark.django_db
    def test_workspace_write_token_cannot_escape_workspace(
        self, api_client, create_user, workspace
    ):
        other_workspace = make_workspace(create_user, slug=f"wiki-other-{uuid4().hex[:8]}")
        page = Page.objects.create(
            workspace=other_workspace,
            name="Other workspace page",
            owned_by=create_user,
            is_global=True,
        )
        _token, raw_token = create_service_access_token(
            label="Bound wiki writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        create_response = client.post(
            f"/api/v1/workspaces/{other_workspace.slug}/wiki/pages/",
            {"name": "Escape attempt"},
            format="json",
        )
        update_response = client.patch(
            f"/api/v1/workspaces/{other_workspace.slug}/wiki/pages/{page.id}/",
            {"name": "Escape attempt"},
            format="json",
        )

        assert create_response.status_code == status.HTTP_403_FORBIDDEN
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        page.refresh_from_db()
        assert page.name == "Other workspace page"

    @pytest.mark.django_db
    def test_write_scope_updates_and_reparents_page(
        self, api_client, create_user, workspace
    ):
        parent = Page.objects.create(
            workspace=workspace,
            name="Runbooks",
            owned_by=create_user,
            is_global=True,
        )
        page = Page.objects.create(
            workspace=workspace,
            name="Old name",
            description_html="<p>Old</p>",
            owned_by=create_user,
            is_global=True,
            access=Page.PRIVATE_ACCESS,
        )
        _token, raw_token = create_service_access_token(
            label="Wiki editor",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.patch(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/{page.id}/",
            {
                "name": "Updated by agent",
                "description_html": "<p>Updated</p>",
                "parent": str(parent.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        page.refresh_from_db()
        assert page.name == "Updated by agent"
        assert page.description_html == "<p>Updated</p>"
        assert page.parent_id == parent.id
        assert page.access == Page.PRIVATE_ACCESS

    @pytest.mark.django_db
    def test_write_scope_rejects_acl_fields(
        self, api_client, create_user, workspace
    ):
        page = Page.objects.create(
            workspace=workspace,
            name="Private policy",
            owned_by=create_user,
            is_global=True,
            access=Page.PRIVATE_ACCESS,
        )
        _token, raw_token = create_service_access_token(
            label="Content writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.patch(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/{page.id}/",
            {"access": Page.PUBLIC_ACCESS},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["unsupported_fields"] == ["access"]
        page.refresh_from_db()
        assert page.access == Page.PRIVATE_ACCESS

    @pytest.mark.django_db
    def test_write_scope_enforces_hierarchy_invariants(
        self, api_client, create_user, workspace
    ):
        parent = Page.objects.create(
            workspace=workspace,
            name="Parent",
            owned_by=create_user,
            is_global=True,
        )
        child = Page.objects.create(
            workspace=workspace,
            name="Child",
            owned_by=create_user,
            is_global=True,
            parent=parent,
        )
        _token, raw_token = create_service_access_token(
            label="Hierarchy writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.patch(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/{parent.id}/",
            {"parent": str(child.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "PAGE_PARENT_CYCLE"
        parent.refresh_from_db()
        assert parent.parent_id is None

    @pytest.mark.django_db
    def test_write_scope_controls_archive_and_lock_lifecycle(
        self, api_client, create_user, workspace
    ):
        page = Page.objects.create(
            workspace=workspace,
            name="Lifecycle page",
            owned_by=create_user,
            is_global=True,
        )
        _token, raw_token = create_service_access_token(
            label="Lifecycle writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_WORKSPACE,
            scopes=["wiki.pages:write"],
            workspace=workspace,
        )
        client = api_client_for_service_token(api_client, raw_token)
        base = f"/api/v1/workspaces/{workspace.slug}/wiki/pages/{page.id}"

        lock_response = client.post(f"{base}/lock/")
        assert lock_response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert page.is_locked is True

        blocked_update = client.patch(
            f"{base}/",
            {"name": "Must not change while locked"},
            format="json",
        )
        assert blocked_update.status_code == status.HTTP_400_BAD_REQUEST

        unlock_response = client.post(f"{base}/unlock/")
        assert unlock_response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert page.is_locked is False

        archive_response = client.post(f"{base}/archive/")
        assert archive_response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert page.archived_at is not None

        update_archived = client.patch(
            f"{base}/",
            {"name": "Must not update archived page"},
            format="json",
        )
        assert update_archived.status_code == status.HTTP_404_NOT_FOUND

        unarchive_response = client.post(f"{base}/unarchive/")
        assert unarchive_response.status_code == status.HTTP_200_OK
        page.refresh_from_db()
        assert page.archived_at is None

    @pytest.mark.django_db
    def test_instance_write_token_can_target_explicit_workspace(
        self, api_client, create_user, workspace
    ):
        _token, raw_token = create_service_access_token(
            label="Instance wiki writer",
            description="",
            created_by=create_user,
            scope_level=SCOPE_LEVEL_INSTANCE,
            scopes=["wiki.pages:write"],
        )
        client = api_client_for_service_token(api_client, raw_token)

        response = client.post(
            f"/api/v1/workspaces/{workspace.slug}/wiki/pages/",
            {"name": "Company digest"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        page = Page.objects.get(pk=response.data["id"])
        assert page.workspace_id == workspace.id
