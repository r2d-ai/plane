# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Nested Wiki page export (WIKI-07c, spec §17.2, plan §10.3).

A root page is selected and its whole permitted subtree is packaged as a ZIP:
descendants are traversed in a stable hierarchy order, every included page is
gated by the centralized effective-access service (``can_view_page``), and the
result is bounded by explicit size/depth limits so a single request cannot
exhaust the worker.

The existing single-page pipeline renders PDF/Markdown in the browser; the
server has no PDF/DOCX renderer, so each exported page is written as Markdown
(the server side of the same textual pipeline). PDF/DOCX stay a client-side
single-page concern. See the PR body for the §31.4–§31.7 drift note.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore[import-untyped]
from django.conf import settings

from plane.db.models import Page
from plane.utils.page_access import PageAccessResolver, can_view_page, resolve_workspace_role


class PageExportError(Exception):
    """Raised when an export cannot be produced within policy limits."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class ExportNode:
    """A visible page in the export tree, ordered by its hierarchy position."""

    page: Page
    depth: int = 0
    children: list["ExportNode"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

_HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
_LIST_TAGS = {"ul", "ol"}
_SKIP_TAGS = {"script", "style", "head", "title", "meta", "link"}
_BLOCK_PASSTHROUGH = {
    "div",
    "section",
    "article",
    "header",
    "footer",
    "main",
    "aside",
    "figure",
    "figcaption",
    "details",
    "summary",
    "dl",
    "dd",
    "dt",
    "span",
}


def _collapse_whitespace(text):
    return re.sub(r"\s+", " ", text)


def _inline(node):
    """Render an inline node (and its children) as Markdown text."""
    if isinstance(node, NavigableString):
        return _collapse_whitespace(str(node))
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name in _SKIP_TAGS:
        return ""
    if name == "br":
        return "  \n"
    if name in ("strong", "b"):
        return f"**{_inline_children(node)}**"
    if name in ("em", "i"):
        return f"*{_inline_children(node)}*"
    if name in ("s", "del", "strike"):
        return f"~~{_inline_children(node)}~~"
    if name == "code":
        return f"`{node.get_text()}`"
    if name == "a":
        label = _inline_children(node).strip()
        href = node.get("href")
        return f"[{label}]({href})" if href else label
    if name == "img":
        src = node.get("src")
        if not src:
            return ""
        return f"![{node.get('alt') or ''}]({src})"
    return _inline_children(node)


def _inline_children(node):
    return "".join(_inline(child) for child in node.children)


def _render_list(list_tag, depth, lines):
    ordered = list_tag.name.lower() == "ol"
    for index, item in enumerate(list_tag.find_all("li", recursive=False), start=1):
        nested = []
        content = []
        for child in item.children:
            if isinstance(child, Tag) and child.name.lower() in _LIST_TAGS:
                nested.append(child)
            else:
                content.extend(_block(child))
        text = " ".join(part.strip() for part in content if part.strip()).strip()
        bullet = f"{index}." if ordered else "-"
        lines.append(f"{'    ' * depth}{bullet} {text}".rstrip())
        for sub in nested:
            _render_list(sub, depth + 1, lines)


def _render_table(table):
    rows = []
    for row_index, tr in enumerate(table.find_all("tr")):
        cells = [
            _inline_children(cell).strip().replace("\n", " ")
            for cell in tr.find_all(["th", "td"], recursive=False)
        ]
        if not cells:
            continue
        rows.append("| " + " | ".join(cells) + " |")
        if row_index == 0:
            rows.append("| " + " | ".join("---" for _ in cells) + " |")
    return "\n".join(rows)


def _block(node):
    """Render a node that may start a block, returning a list of block strings."""
    if isinstance(node, NavigableString):
        text = _collapse_whitespace(str(node)).strip()
        return [text] if text else []
    if not isinstance(node, Tag):
        return []
    name = node.name.lower()
    if name in _SKIP_TAGS:
        return []
    if name in _HEADINGS:
        text = _inline_children(node).strip()
        return [f"{_HEADINGS[name]} {text}".rstrip()] if text else []
    if name == "p":
        text = _inline_children(node).strip()
        return [text] if text else []
    if name == "hr":
        return ["---"]
    if name in _LIST_TAGS:
        lines: list[str] = []
        _render_list(node, 0, lines)
        return ["\n".join(lines)] if lines else []
    if name == "blockquote":
        inner = "\n\n".join(_blocks(node))
        return ["> " + inner.replace("\n", "\n> ")] if inner.strip("> ") else []
    if name == "pre":
        code_tag = node.find("code")
        language = ""
        if code_tag is not None and code_tag.get("class"):
            language = next(
                (cls.replace("language-", "") for cls in code_tag["class"] if cls.startswith("language-")),
                "",
            )
        return [f"```{language}\n{node.get_text().rstrip()}\n```"]
    if name == "table":
        rendered = _render_table(node)
        return [rendered] if rendered else []
    if name in _BLOCK_PASSTHROUGH:
        return _blocks(node)
    text = _inline(node).strip()
    return [text] if text else []


def _blocks(node):
    blocks: list[str] = []
    for child in node.children:
        blocks.extend(_block(child))
    return blocks


def html_to_markdown(html):
    """Convert sanitized Page HTML into Markdown for archive files.

    The stored ``description_html`` is already sanitized by the write path
    (spec §22.2), so this only re-serializes it: unknown/custom elements are
    unwrapped and keep their text, never their attributes.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = "\n\n".join(part for part in _blocks(soup) if part.strip())
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def render_page_markdown(page, html_by_id):
    """A single page's Markdown file: title heading + converted body."""
    title = (page.name or "").strip()
    body = html_to_markdown(html_by_id.get(page.id, ""))
    parts = [f"# {title}"] if title else []
    if body:
        parts.append(body)
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# File naming
# ---------------------------------------------------------------------------

def safe_export_name(name, fallback="page"):
    """A predictable, path-safe file stem derived from a page name."""
    stem = re.sub(r"[^0-9a-z]+", "-", (name or "").strip().lower())
    stem = re.sub(r"-{2,}", "-", stem).strip("-")
    return stem[:80] or fallback


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


def _sibling_sort_key(page):
    sort_order = page.sort_order
    if sort_order is None:
        sort_order = Page.DEFAULT_SORT_ORDER
    return (sort_order, (page.name or "").lower(), str(page.id))


def _get_limit(setting_name, default):
    value = getattr(settings, setting_name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def collect_export_tree(
    root_page,
    user,
    workspace,
    *,
    workspace_role=None,
    resolver=None,
    max_depth=None,
    max_pages=None,
):
    """Build the permitted descendant tree rooted at ``root_page``.

    Sibling order is ``(sort_order, name, id)`` — the same stable order the Wiki
    tree UI uses. Every candidate page must pass the centralized VIEW check, so
    private descendants without a share or Collection membership are dropped
    (spec §17.2 "permission check for every included page", §22.1 BOLA).
    Archived, deleted and non-Wiki rows are never traversed. Depth and page
    count are bounded by ``PAGE_EXPORT_MAX_DEPTH`` / ``PAGE_EXPORT_MAX_PAGES``.
    """
    max_depth = _get_limit("PAGE_EXPORT_MAX_DEPTH", 10) if max_depth is None else max_depth
    max_pages = _get_limit("PAGE_EXPORT_MAX_PAGES", 200) if max_pages is None else max_pages
    resolver = resolver or PageAccessResolver(workspace.id)
    if workspace_role is None:
        workspace_role = resolve_workspace_role(workspace.id, getattr(user, "id", None))

    rows = list(
        Page.objects.filter(
            workspace=workspace,
            is_global=True,
            deleted_at__isnull=True,
            archived_at__isnull=True,
        )
        .only("id", "parent_id", "name", "sort_order", "created_at", "access", "owned_by_id")
        .order_by("sort_order", "name", "created_at")
    )
    by_id = {row.id: row for row in rows}
    children: dict = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)
    for siblings in children.values():
        siblings.sort(key=_sibling_sort_key)

    if root_page.id not in by_id:
        raise PageExportError("PAGE_EXPORT_ROOT_NOT_FOUND", "Root page is not exportable.")

    included = 0

    def walk(row, depth):
        nonlocal included
        if depth > max_depth:
            raise PageExportError(
                "PAGE_EXPORT_DEPTH_LIMIT",
                "Page hierarchy is deeper than the export depth limit.",
            )
        if not can_view_page(user, row, workspace, workspace_role=workspace_role, resolver=resolver):
            return None
        included += 1
        if included > max_pages:
            raise PageExportError(
                "PAGE_EXPORT_PAGE_LIMIT",
                "Page hierarchy has more pages than the export size limit.",
            )
        node = ExportNode(page=row, depth=depth)
        for child in children.get(row.id, []):
            child_node = walk(child, depth + 1)
            if child_node is not None:
                node.children.append(child_node)
        return node

    return walk(by_id[root_page.id], 0)


# ---------------------------------------------------------------------------
# ZIP packaging
# ---------------------------------------------------------------------------


def _collect_entries(root, html_by_id):
    entries: list[tuple[str, str]] = []

    def emit(node, parent_dir, prefix):
        stem = safe_export_name(node.page.name)
        if node.children:
            directory = f"{prefix}{stem}"
            path = f"{parent_dir}/{directory}" if parent_dir else directory
            entries.append((f"{path}/index.md", render_page_markdown(node.page, html_by_id)))
            for index, child in enumerate(node.children, start=1):
                emit(child, path, f"{index:02d}-")
        else:
            filename = f"{prefix}{stem}.md"
            path = f"{parent_dir}/{filename}" if parent_dir else filename
            entries.append((path, render_page_markdown(node.page, html_by_id)))

    emit(root, "", "")
    return entries


def build_export_archive(root, html_by_id, *, max_bytes=None):
    """Package the export tree as an in-memory ZIP, bounded by size limit."""
    max_bytes = _get_limit("PAGE_EXPORT_MAX_BYTES", 25 * 1024 * 1024) if max_bytes is None else max_bytes
    entries = _collect_entries(root, html_by_id)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in entries:
            archive.writestr(path, content.encode("utf-8"))
    data = buffer.getvalue()
    if len(data) > max_bytes:
        raise PageExportError(
            "PAGE_EXPORT_SIZE_LIMIT",
            "Export archive is larger than the configured size limit.",
        )
    return data


def export_page_archive(root_page, user, workspace, *, workspace_role=None):
    """Full nested-export pipeline: traverse, then package."""
    resolver = PageAccessResolver(workspace.id)
    tree = collect_export_tree(
        root_page,
        user,
        workspace,
        workspace_role=workspace_role,
        resolver=resolver,
    )
    if tree is None:
        raise PageExportError("PAGE_EXPORT_ROOT_NOT_FOUND", "Root page is not exportable.")

    page_ids = []

    def collect_ids(node):
        page_ids.append(node.page.id)
        for child in node.children:
            collect_ids(child)

    collect_ids(tree)
    html_by_id = dict(Page.objects.filter(id__in=page_ids).values_list("id", "description_html"))
    return build_export_archive(tree, html_by_id)
