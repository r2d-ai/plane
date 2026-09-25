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
from plane.db.models import APIToken, Project, ProjectMember, Workspace


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
