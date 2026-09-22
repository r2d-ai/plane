# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-05 effective-ACL truth table (plan §8.4, spec §19.1).

Pins the single deterministic algorithm before/around the Collection APIs:
workspace role + page access + Collection access/member role + parent
inheritance => effective capability, with a private Collection acting as a
mandatory boundary.
"""

import pytest

from plane.db.models import Page, PageCollection, PageCollectionMember, User, WorkspaceMember
from plane.utils.page_access import Capability, effective_capability


def _user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="T", last_name="U")


def _wiki_page(workspace, owner, name="P", access=Page.PUBLIC_ACCESS, parent=None):
    return Page.objects.create(
        workspace=workspace, owned_by=owner, name=name, access=access, is_global=True, parent=parent
    )


def _collection(workspace, name, access=PageCollection.ACCESS_PRIVATE, created_by=None):
    return PageCollection.objects.create(workspace=workspace, name=name, access=access, created_by=created_by)


def _add_page(collection, page):
    from plane.db.models import PageCollectionPage

    return PageCollectionPage.objects.create(collection=collection, page=page, workspace=collection.workspace)


@pytest.mark.unit
class TestEffectiveCapabilityTruthTable:
    @pytest.mark.django_db
    def test_workspace_baseline_without_collection(self, workspace, create_user):
        member = _user("member@plane.so")
        guest = _user("guest@plane.so")
        outsider = _user("outsider@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)

        page = _wiki_page(workspace, create_user)

        assert effective_capability(create_user, page, workspace) == Capability.EDIT
        assert effective_capability(member, page, workspace) == Capability.EDIT
        assert effective_capability(guest, page, workspace) == Capability.VIEW
        assert effective_capability(outsider, page, workspace) == Capability.NONE

    @pytest.mark.django_db
    def test_private_page_requires_owner(self, workspace, create_user):
        member = _user("member@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        page = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)

        assert effective_capability(create_user, page, workspace) == Capability.EDIT
        assert effective_capability(member, page, workspace) == Capability.NONE

    @pytest.mark.django_db
    def test_private_collection_is_a_mandatory_boundary(self, workspace, create_user):
        member = _user("member@plane.so")
        editor = _user("editor@plane.so")
        viewer = _user("viewer@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=editor, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15)

        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE)
        page = _wiki_page(workspace, create_user)
        _add_page(collection, page)
        PageCollectionMember.objects.create(collection=collection, member=editor, role=PageCollection.ROLE_EDIT)
        PageCollectionMember.objects.create(collection=collection, member=viewer, role=PageCollection.ROLE_VIEW)

        # Non-member workspace member: boundary blocks everything.
        assert effective_capability(member, page, workspace) == Capability.NONE
        # Explicit role inside the boundary, capped by the most restrictive side.
        assert effective_capability(editor, page, workspace) == Capability.EDIT
        assert effective_capability(viewer, page, workspace) == Capability.VIEW
        # Workspace admin/owner bypasses the boundary.
        assert effective_capability(create_user, page, workspace) == Capability.EDIT

    @pytest.mark.django_db
    def test_private_collection_role_caps_workspace_baseline(self, workspace, create_user):
        viewer = _user("viewer@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=viewer, role=15)  # member baseline is EDIT
        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE)
        page = _wiki_page(workspace, create_user)
        _add_page(collection, page)
        PageCollectionMember.objects.create(collection=collection, member=viewer, role=PageCollection.ROLE_VIEW)

        # Member baseline is EDIT, but the Collection role caps it to VIEW.
        assert effective_capability(viewer, page, workspace) == Capability.VIEW

    @pytest.mark.django_db
    def test_parent_inheritance_through_subtree(self, workspace, create_user):
        member = _user("member@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)

        collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE)
        parent = _wiki_page(workspace, create_user, name="Parent")
        child = _wiki_page(workspace, create_user, name="Child", parent=parent)
        grandchild = _wiki_page(workspace, create_user, name="Grandchild", parent=child)
        _add_page(collection, parent)

        for page in (parent, child, grandchild):
            assert effective_capability(member, page, workspace) == Capability.NONE

    @pytest.mark.django_db
    def test_public_collection_grants_public_role(self, workspace, create_user):
        member = _user("member@plane.so")
        guest = _user("guest@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)

        collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC)
        page = _wiki_page(workspace, create_user)
        _add_page(collection, page)

        assert effective_capability(member, page, workspace) == Capability.EDIT
        assert effective_capability(guest, page, workspace) == Capability.VIEW

    @pytest.mark.django_db
    def test_company_wiki_open_read_is_read_only(self, settings, workspace, create_user):
        outsider = _user("outsider@plane.so")
        settings.COMPANY_WIKI_WORKSPACE_SLUG = workspace.slug
        settings.COMPANY_WIKI_OPEN_READ = True

        page = _wiki_page(workspace, create_user)
        assert effective_capability(outsider, page, workspace) == Capability.VIEW

        private = _wiki_page(workspace, create_user, access=Page.PRIVATE_ACCESS)
        assert effective_capability(outsider, private, workspace) == Capability.NONE

        private_collection = _collection(workspace, "Private", PageCollection.ACCESS_PRIVATE)
        gated = _wiki_page(workspace, create_user)
        _add_page(private_collection, gated)
        assert effective_capability(outsider, gated, workspace) == Capability.NONE

        public_collection = _collection(workspace, "Public", PageCollection.ACCESS_PUBLIC)
        grouped = _wiki_page(workspace, create_user)
        _add_page(public_collection, grouped)
        assert effective_capability(outsider, grouped, workspace) == Capability.VIEW
