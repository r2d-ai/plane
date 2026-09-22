# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-00 contract tests: the shared hierarchy guard is enforced on the
existing Project Page update path without changing its resolution rules.
"""

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


def _pages_url(slug, project_id, page_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/pages/{page_id}/"


def _make_project_page(workspace, project, owner, name, parent=None):
    page = Page.objects.create(workspace=workspace, owned_by=owner, name=name, parent=parent)
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page


@pytest.mark.contract
class TestProjectPageHierarchyGuard:
    def _setup(self, workspace, member):
        project = Project.objects.create(name="Project", identifier="PRJ", workspace=workspace)
        ProjectMember.objects.create(workspace=workspace, project=project, member=member, role=20)
        return project

    @pytest.mark.django_db
    def test_valid_reparent_allowed(self, session_client, workspace, create_user):
        project = self._setup(workspace, create_user)
        parent = _make_project_page(workspace, project, create_user, "Parent")
        child = _make_project_page(workspace, project, create_user, "Child")

        response = session_client.patch(
            _pages_url(workspace.slug, project.id, child.id), {"parent": str(parent.id)}, format="json"
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_self_parent_rejected(self, session_client, workspace, create_user):
        project = self._setup(workspace, create_user)
        page = _make_project_page(workspace, project, create_user, "Page")

        response = session_client.patch(
            _pages_url(workspace.slug, project.id, page.id), {"parent": str(page.id)}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "PAGE_SELF_PARENT"

    @pytest.mark.django_db
    def test_descendant_parent_cycle_rejected(self, session_client, workspace, create_user):
        project = self._setup(workspace, create_user)
        root = _make_project_page(workspace, project, create_user, "Root")
        child = _make_project_page(workspace, project, create_user, "Child", parent=root)

        response = session_client.patch(
            _pages_url(workspace.slug, project.id, root.id), {"parent": str(child.id)}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "PAGE_PARENT_CYCLE"
