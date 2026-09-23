# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-07c unit tests: nested Wiki export primitives (spec §17.2, plan §10.3).

Pins HTML->Markdown rendering, safe file naming, stable hierarchy traversal with
per-page permission filtering, the size/depth/page limits and the ZIP layout.
"""

import io
import zipfile

import pytest

from plane.db.models import Page, User, WorkspaceMember
from plane.utils.page_export import (
    PageExportError,
    build_export_archive,
    collect_export_tree,
    export_page_archive,
    html_to_markdown,
    safe_export_name,
)


def _user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="T", last_name="U")


def _wiki_page(workspace, owner, name="Page", access=Page.PUBLIC_ACCESS, parent=None, sort_order=65535):
    return Page.objects.create(
        workspace=workspace,
        owned_by=owner,
        name=name,
        access=access,
        is_global=True,
        parent=parent,
        sort_order=sort_order,
    )


def _names(node):
    return node.page.name


def _flatten(node):
    result = [node]
    for child in node.children:
        result.extend(_flatten(child))
    return result


@pytest.mark.unit
class TestHtmlToMarkdown:
    def test_headings_paragraphs_and_inline(self):
        html = "<h1>Title</h1><p>Hello <strong>bold</strong> and <em>italic</em>.</p>"
        assert html_to_markdown(html) == "# Title\n\nHello **bold** and *italic*."

    def test_links_code_and_images(self):
        html = '<p><a href="https://plane.so">Plane</a> <code>x = 1</code></p><p><img src="/a.png" alt="A"></p>'
        markdown = html_to_markdown(html)
        assert "[Plane](https://plane.so)" in markdown
        assert "`x = 1`" in markdown
        assert "![A](/a.png)" in markdown

    def test_lists_and_nested_lists(self):
        html = "<ul><li>One</li><li>Two<ul><li>Nested</li></ul></li></ul>"
        assert html_to_markdown(html) == "- One\n- Two\n    - Nested"

    def test_ordered_list_and_blockquote_and_rule(self):
        html = "<ol><li>First</li><li>Second</li></ol><blockquote><p>Quoted</p></blockquote><hr>"
        markdown = html_to_markdown(html)
        assert "1. First" in markdown
        assert "2. Second" in markdown
        assert "> Quoted" in markdown
        assert "---" in markdown

    def test_pre_and_table(self):
        html = (
            '<pre><code class="language-python">print(1)</code></pre>'
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
        )
        markdown = html_to_markdown(html)
        assert "```python\nprint(1)\n```" in markdown
        assert "| A | B |" in markdown
        assert "| --- | --- |" in markdown
        assert "| 1 | 2 |" in markdown

    def test_script_and_style_are_dropped(self):
        html = "<p>Safe</p><script>alert(1)</script><style>p{color:red}</style>"
        assert html_to_markdown(html) == "Safe"

    def test_empty_html(self):
        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""


@pytest.mark.unit
class TestSafeExportName:
    def test_sanitizes_and_lowercases(self):
        assert safe_export_name("My Page: Getting Started!") == "my-page-getting-started"

    def test_falls_back_when_no_ascii(self):
        assert safe_export_name("   ") == "page"
        assert safe_export_name("", fallback="root") == "root"

    def test_truncates_long_names(self):
        assert len(safe_export_name("a" * 200)) == 80


@pytest.mark.unit
class TestCollectExportTree:
    @pytest.mark.django_db
    def test_stable_hierarchy_order(self, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Root", sort_order=1)
        second = _wiki_page(workspace, create_user, name="Second", parent=root, sort_order=2)
        first = _wiki_page(workspace, create_user, name="First", parent=root, sort_order=1)
        grandchild = _wiki_page(workspace, create_user, name="Grandchild", parent=first, sort_order=1)

        tree = collect_export_tree(root, create_user, workspace)

        assert [node.page.id for node in _flatten(tree)] == [
            root.id,
            first.id,
            grandchild.id,
            second.id,
        ]

    @pytest.mark.django_db
    def test_private_descendant_without_access_is_excluded(self, workspace, create_user):
        member = _user("member@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        root = _wiki_page(workspace, create_user, name="Root")
        public_child = _wiki_page(workspace, create_user, name="Public child", parent=root)
        private_child = _wiki_page(
            workspace, create_user, name="Private child", access=Page.PRIVATE_ACCESS, parent=root
        )

        tree = collect_export_tree(root, member, workspace)

        included = {node.page.id for node in _flatten(tree)}
        assert root.id in included
        assert public_child.id in included
        assert private_child.id not in included

    @pytest.mark.django_db
    def test_private_descendant_with_share_is_included(self, workspace, create_user):
        from plane.db.models import PageShare

        member = _user("shared@plane.so")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
        root = _wiki_page(workspace, create_user, name="Root")
        private_child = _wiki_page(
            workspace, create_user, name="Shared child", access=Page.PRIVATE_ACCESS, parent=root
        )
        PageShare.objects.create(
            workspace=workspace, page=private_child, member=member, role=PageShare.ROLE_VIEW
        )

        tree = collect_export_tree(root, member, workspace)

        assert private_child.id in {node.page.id for node in _flatten(tree)}

    @pytest.mark.django_db
    def test_depth_limit_rejects_deep_tree(self, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Root")
        parent = root
        for index in range(4):
            parent = _wiki_page(workspace, create_user, name=f"Level {index}", parent=parent)

        with pytest.raises(PageExportError) as exc:
            collect_export_tree(root, create_user, workspace, max_depth=2)

        assert exc.value.code == "PAGE_EXPORT_DEPTH_LIMIT"

    @pytest.mark.django_db
    def test_page_limit_rejects_wide_tree(self, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Root")
        for index in range(4):
            _wiki_page(workspace, create_user, name=f"Child {index}", parent=root)

        with pytest.raises(PageExportError) as exc:
            collect_export_tree(root, create_user, workspace, max_pages=3)

        assert exc.value.code == "PAGE_EXPORT_PAGE_LIMIT"

    @pytest.mark.django_db
    def test_archived_descendants_are_excluded(self, workspace, create_user):
        from django.utils import timezone

        root = _wiki_page(workspace, create_user, name="Root")
        _wiki_page(workspace, create_user, name="Live", parent=root)
        archived = _wiki_page(workspace, create_user, name="Archived", parent=root)
        archived.archived_at = timezone.now().date()
        archived.save(update_fields=["archived_at"])

        tree = collect_export_tree(root, create_user, workspace)

        assert archived.id not in {node.page.id for node in _flatten(tree)}


@pytest.mark.unit
class TestBuildExportArchive:
    @pytest.mark.django_db
    def test_zip_layout_orders_siblings_and_writes_index(self, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Handbook")
        child = _wiki_page(workspace, create_user, name="Getting Started", parent=root, sort_order=1)
        leaf = _wiki_page(workspace, create_user, name="Install", parent=child, sort_order=1)

        tree = collect_export_tree(root, create_user, workspace)
        html_by_id = {
            root.id: "<p>Root</p>",
            child.id: "<p>Child</p>",
            leaf.id: "<p>Leaf</p>",
        }
        data = build_export_archive(tree, html_by_id)

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            assert names == [
                "handbook/index.md",
                "handbook/01-getting-started/index.md",
                "handbook/01-getting-started/01-install.md",
            ]
            assert archive.read("handbook/index.md").decode() == "# Handbook\n\nRoot\n"

    @pytest.mark.django_db
    def test_sibling_order_prefixes_keep_duplicate_names_distinct(self, workspace, create_user):
        root = _wiki_page(workspace, create_user, name="Root")
        _wiki_page(workspace, create_user, name="Dup", parent=root, sort_order=1)
        _wiki_page(workspace, create_user, name="Dup", parent=root, sort_order=2)

        tree = collect_export_tree(root, create_user, workspace)
        data = build_export_archive(tree, {})

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            assert "root/01-dup.md" in names
            assert "root/02-dup.md" in names

    @pytest.mark.django_db
    def test_size_limit_rejected(self, settings, workspace, create_user):
        settings.PAGE_EXPORT_MAX_BYTES = 1
        root = _wiki_page(workspace, create_user, name="Root")

        with pytest.raises(PageExportError) as exc:
            export_page_archive(root, create_user, workspace)

        assert exc.value.code == "PAGE_EXPORT_SIZE_LIMIT"
