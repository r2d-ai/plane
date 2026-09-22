# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-00 hierarchy scope guard regression tests.

The guard is shared by Project Pages and Wiki pages, so these cases pin both
same-scope success and every rejection path: self-parent, deleted parent,
cross-workspace parent, project-vs-wiki nesting, and cycles (including a
malformed legacy cycle that must fail safe).
"""

import pytest
from django.utils import timezone

from plane.db.models import Page, Workspace
from plane.utils.page_hierarchy import PageHierarchyError, validate_page_parent


def _make_page(workspace, owner, name="Page", is_global=False, parent=None):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        is_global=is_global,
        parent=parent,
    )


@pytest.mark.unit
class TestValidatePageParent:
    @pytest.mark.django_db
    def test_none_parent_allowed(self, workspace, create_user):
        page = _make_page(workspace, create_user)

        validate_page_parent(page, None)

    @pytest.mark.django_db
    def test_same_scope_parent_allowed(self, workspace, create_user):
        parent = _make_page(workspace, create_user, name="Parent", is_global=True)
        child = _make_page(workspace, create_user, name="Child", is_global=True)

        validate_page_parent(child, parent)

    @pytest.mark.django_db
    def test_self_parent_rejected(self, workspace, create_user):
        page = _make_page(workspace, create_user)

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(page, page)

        assert exc.value.code == "PAGE_SELF_PARENT"

    @pytest.mark.django_db
    def test_cross_workspace_parent_rejected(self, workspace, create_user):
        other_workspace = Workspace.objects.create(name="Other Workspace", slug="other-workspace", owner=create_user)
        parent = _make_page(other_workspace, create_user, name="Other parent", is_global=True)
        child = _make_page(workspace, create_user, name="Child", is_global=True)

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(child, parent)

        assert exc.value.code == "PAGE_PARENT_CROSS_WORKSPACE"

    @pytest.mark.django_db
    def test_project_parent_wiki_child_rejected(self, workspace, create_user):
        parent = _make_page(workspace, create_user, name="Project parent")
        child = _make_page(workspace, create_user, name="Wiki child", is_global=True)

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(child, parent)

        assert exc.value.code == "PAGE_PARENT_CROSS_SCOPE"

    @pytest.mark.django_db
    def test_wiki_parent_project_child_rejected(self, workspace, create_user):
        parent = _make_page(workspace, create_user, name="Wiki parent", is_global=True)
        child = _make_page(workspace, create_user, name="Project child")

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(child, parent)

        assert exc.value.code == "PAGE_PARENT_CROSS_SCOPE"

    @pytest.mark.django_db
    def test_deleted_parent_rejected(self, workspace, create_user):
        parent = _make_page(workspace, create_user, name="Parent", is_global=True)
        deleted_at = timezone.now()
        Page.objects.filter(pk=parent.pk).update(deleted_at=deleted_at)
        parent.deleted_at = deleted_at
        child = _make_page(workspace, create_user, name="Child", is_global=True)

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(child, parent)

        assert exc.value.code == "PAGE_PARENT_DELETED"

    @pytest.mark.django_db
    def test_descendant_parent_cycle_rejected(self, workspace, create_user):
        root = _make_page(workspace, create_user, name="Root", is_global=True)
        child = _make_page(workspace, create_user, name="Child", is_global=True, parent=root)
        grandchild = _make_page(workspace, create_user, name="Grandchild", is_global=True, parent=child)

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(root, grandchild)

        assert exc.value.code == "PAGE_PARENT_CYCLE"

    @pytest.mark.django_db
    def test_malformed_cycle_terminates_and_rejects(self, workspace, create_user):
        page_a = _make_page(workspace, create_user, name="A", is_global=True)
        page_b = _make_page(workspace, create_user, name="B", is_global=True, parent=page_a)
        # Force a malformed A -> B -> A cycle straight in the DB.
        Page.objects.filter(pk=page_a.pk).update(parent=page_b)
        page_a.parent_id = page_b.pk

        with pytest.raises(PageHierarchyError):
            validate_page_parent(page_a, page_b)

    @pytest.mark.django_db
    def test_unrelated_malformed_cycle_fails_safe(self, workspace, create_user):
        page_a = _make_page(workspace, create_user, name="A", is_global=True)
        page_b = _make_page(workspace, create_user, name="B", is_global=True)
        page_c = _make_page(workspace, create_user, name="C", is_global=True)
        # Force a B <-> C cycle that does not contain A.
        Page.objects.filter(pk=page_b.pk).update(parent=page_c)
        Page.objects.filter(pk=page_c.pk).update(parent=page_b)
        page_b.parent_id = page_c.pk
        page_c.parent_id = page_b.pk

        with pytest.raises(PageHierarchyError) as exc:
            validate_page_parent(page_a, page_b)

        assert exc.value.code == "PAGE_PARENT_CYCLE"


@pytest.mark.unit
class TestRecursiveArchiveHierarchy:
    @pytest.mark.django_db
    def test_archive_touches_all_descendants(self, workspace, create_user):
        from plane.app.views.page.base import unarchive_archive_page_and_descendants

        root = _make_page(workspace, create_user, name="Root", is_global=True)
        child = _make_page(workspace, create_user, name="Child", is_global=True, parent=root)
        grandchild = _make_page(workspace, create_user, name="Grandchild", is_global=True, parent=child)

        unarchive_archive_page_and_descendants(root.id, timezone.now())

        for page in Page.objects.filter(pk__in=[root.pk, child.pk, grandchild.pk]):
            assert page.archived_at is not None

    @pytest.mark.django_db
    def test_archive_is_cycle_safe(self, workspace, create_user):
        from plane.app.views.page.base import unarchive_archive_page_and_descendants

        root = _make_page(workspace, create_user, name="Root", is_global=True)
        child = _make_page(workspace, create_user, name="Child", is_global=True, parent=root)
        # Force a malformed root -> child -> root cycle straight in the DB.
        Page.objects.filter(pk=root.pk).update(parent=child)

        unarchive_archive_page_and_descendants(root.id, timezone.now())

        for page in Page.objects.filter(pk__in=[root.pk, child.pk]):
            assert page.archived_at is not None
