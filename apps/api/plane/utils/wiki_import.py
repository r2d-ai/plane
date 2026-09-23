# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Notion / Confluence importers (WIKI-10, plan §13.2/§13.3).

Both importers are *safe by construction*:

* the archive is never extracted to disk — every entry is read into memory
  after its name passes :func:`safe_entry_name`, which rejects absolute paths,
  ``..`` segments, drive letters, NUL bytes and symlink entries (path traversal
  defense, plan §13.2/§13.3);
* every dimension is bounded by ``WIKI_IMPORT_*`` settings so a decompression
  bomb or a huge archive fails with a structured error instead of exhausting
  the worker;
* no remote URL is ever fetched, so an imported document cannot be used as an
  SSRF pivot;
* imported HTML is sanitized through the same
  :func:`plane.utils.content_validator.validate_html_content` path the editor
  write uses, so stored content is never less safe than user-authored content.

Each import returns a **mapping report** describing every created page, its
source key / parent, attachments, comments, links and anything skipped, and
emits one ``WikiEvent`` per created page so the AI event feed sees imports like
any other Wiki mutation.
"""

from __future__ import annotations

import io
import mimetypes
import posixpath
import re
import zipfile
from dataclasses import dataclass
from html import escape
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from plane.db.models import FileAsset, Page, PageComment, WikiEvent
from plane.utils.content_validator import validate_html_content
from plane.utils.html_processor import strip_tags
from plane.utils.wiki_ai import emit_wiki_event

SCHEMA_VERSION = "1.0"

NOTION_HTML_EXTENSIONS = (".html", ".htm")


class WikiImportError(Exception):
    """Raised when an import archive cannot be consumed within policy limits."""

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class ImportLimits:
    max_bytes: int
    max_entries: int
    max_pages: int
    max_depth: int
    max_attachments: int
    max_attachment_bytes: int
    max_comments: int


def default_limits():
    return ImportLimits(
        max_bytes=int(getattr(settings, "WIKI_IMPORT_MAX_BYTES", 50 * 1024 * 1024)),
        max_entries=int(getattr(settings, "WIKI_IMPORT_MAX_ENTRIES", 2000)),
        max_pages=int(getattr(settings, "WIKI_IMPORT_MAX_PAGES", 500)),
        max_depth=int(getattr(settings, "WIKI_IMPORT_MAX_DEPTH", 20)),
        max_attachments=int(getattr(settings, "WIKI_IMPORT_MAX_ATTACHMENTS", 500)),
        max_attachment_bytes=int(getattr(settings, "WIKI_IMPORT_MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)),
        max_comments=int(getattr(settings, "WIKI_IMPORT_MAX_COMMENTS", 2000)),
    )


# ---------------------------------------------------------------------------
# Archive reading (path-traversal safe)
# ---------------------------------------------------------------------------


def safe_entry_name(name):
    """Normalize a ZIP member name or raise a traversal error.

    Rejects NUL bytes, backslashes, absolute paths, drive letters and any
    ``..`` segment. The returned value is a normalized POSIX path relative to
    the archive root, safe to use as an in-memory key.
    """
    if not name or "\x00" in name:
        raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive contains an invalid entry name.")
    if "\\" in name:
        raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive contains a backslash in an entry name.")
    normalized = posixpath.normpath(name)
    if normalized.startswith("/") or normalized.startswith("../") or normalized == "..":
        raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive entry escapes the archive root.")
    if re.match(r"^[a-zA-Z]:", normalized):
        raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive entry uses an absolute drive path.")
    if any(segment == ".." for segment in normalized.split("/")):
        raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive entry escapes the archive root.")
    return normalized


def _is_symlink(info):
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def load_zip(file_obj, limits=None):
    """Read a ZIP archive into ``{normalized_name: bytes}`` with all guards.

    The archive is fully consumed in memory but bounded by ``max_bytes``; each
    entry is bounded by ``max_attachment_bytes``; the entry count and the
    aggregate uncompressed size are bounded too. Encrypted and symlink entries
    are rejected outright.
    """
    limits = limits or default_limits()
    raw = file_obj.read(limits.max_bytes + 1)
    if len(raw) > limits.max_bytes:
        raise WikiImportError("IMPORT_TOO_LARGE", "Archive exceeds the import size limit.")

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError) as exc:
        raise WikiImportError("INVALID_ARCHIVE", "Uploaded file is not a valid ZIP archive.") from exc

    entries = {}
    total_uncompressed = 0
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise WikiImportError("ENCRYPTED_ARCHIVE", "Encrypted archives are not supported.")
            if _is_symlink(info):
                raise WikiImportError("UNSAFE_ARCHIVE_PATH", "Archive contains a symbolic link entry.")
            if len(entries) >= limits.max_entries:
                raise WikiImportError("ARCHIVE_ENTRY_LIMIT", "Archive contains too many entries.")
            if info.file_size > limits.max_attachment_bytes:
                raise WikiImportError("ARCHIVE_ENTRY_LIMIT", "Archive entry exceeds the size limit.")
            name = safe_entry_name(info.filename)
            total_uncompressed += info.file_size
            if total_uncompressed > limits.max_bytes * 8:
                raise WikiImportError("IMPORT_TOO_LARGE", "Archive uncompressed data exceeds the import limit.")
            entries[name] = archive.read(info)

    if not entries:
        raise WikiImportError("EMPTY_ARCHIVE", "Archive contains no importable entries.")
    return entries


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _sanitize(html):
    ok, _error, clean = validate_html_content(html or "")
    if not ok or not clean:
        return ""
    return clean


def _guess_content_type(filename):
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _persist_attachment(workspace, user, page, name, content, content_type):
    """Store one extracted attachment as a ``FileAsset`` bound to ``page``.

    Kept as a module-level seam so it can be replaced in tests without an
    object store. Returns the created ``FileAsset``.
    """
    asset = FileAsset(
        attributes={"name": name, "type": content_type, "size": len(content)},
        workspace=workspace,
        page=page,
        user=user,
        entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        entity_identifier=str(page.pk),
        size=len(content),
        is_uploaded=True,
    )
    asset.asset.save(name, ContentFile(content), save=False)
    asset.save()
    return asset


def _store_attachment(report, workspace, user, page, source, name, content, limits):
    if len(report["attachments"]) >= limits.max_attachments:
        report["skipped"].append({"source": source, "reason": "attachment_limit"})
        return None
    if len(content) > limits.max_attachment_bytes:
        report["skipped"].append({"source": source, "reason": "attachment_too_large"})
        return None
    content_type = _guess_content_type(name)
    try:
        asset = _persist_attachment(workspace, user, page, name, content, content_type)
    except Exception:  # storage backends are external; a failure must not lose the page
        report["skipped"].append({"source": source, "reason": "attachment_storage_failed"})
        return None
    report["attachments"].append(
        {
            "source": source,
            "name": name,
            "page_id": str(page.pk),
            "file_asset_id": str(asset.id),
            "content_type": content_type,
            "size": len(content),
            "stored": True,
        }
    )
    return asset


def _create_page(
    workspace, user, name, html, parent, *, source, report, event_type=WikiEvent.PAGE_IMPORTED, payload=None
):
    """Create one imported Wiki page and record it on the report + event feed."""
    cleaned = _sanitize(html)
    page = Page.objects.create(
        workspace=workspace,
        name=(name or "Untitled")[:255],
        description_html=cleaned or "<p></p>",
        description_json={},
        owned_by=user,
        parent=parent,
        is_global=True,
        access=Page.PUBLIC_ACCESS,
        external_source=report["source"],
        external_id=source[:255],
    )
    emit_wiki_event(
        page,
        event_type,
        actor=user,
        payload={"import": report["source"], "source": source, **(payload or {})},
    )
    report["pages"].append(
        {
            "source": source,
            "page_id": str(page.pk),
            "name": page.name,
            "parent_page_id": str(parent.pk) if parent is not None else None,
        }
    )
    return page


def _finalize_report(report):
    report["stats"] = {
        "pages": len(report["pages"]),
        "attachments": len(report["attachments"]),
        "comments": len(report["comments"]),
        "links": len(report["links"]),
        "skipped": len(report["skipped"]),
        "conversions": len(report["conversions"]),
    }
    report["schema_version"] = SCHEMA_VERSION
    return report


def _new_report(source):
    return {
        "source": source,
        "schema_version": SCHEMA_VERSION,
        "pages": [],
        "attachments": [],
        "comments": [],
        "links": [],
        "skipped": [],
        "conversions": [],
    }


# ---------------------------------------------------------------------------
# Notion HTML import
# ---------------------------------------------------------------------------


def _notion_title(soup, path):
    heading = soup.find("h1", class_="page-title") or soup.find("h1")
    if heading is not None:
        title = heading.get_text(strip=True)
        if title:
            return title
    return posixpath.splitext(posixpath.basename(path))[0] or "Untitled"


def _notion_body(soup):
    container = soup.find("article") or soup.body or soup
    page_body = container.find("div", class_="page-body") if container else None
    return page_body if page_body is not None else container


def _resolve_relative(base_path, href):
    """Resolve an archive-relative href against the containing page's folder."""
    if not href or href.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:")):
        return None
    href = unquote(href.split("#", 1)[0])
    if not href:
        return None
    directory = posixpath.dirname(base_path)
    return safe_entry_name(posixpath.join(directory, href))


def _replace_with_html(node, html):
    """Replace ``node`` with a parsed HTML fragment (contents, not a wrapper)."""
    fragment = BeautifulSoup(html, "html.parser")
    node.replace_with(*list(fragment.children))


def _notion_rewrite_body(body, page_path, page_ids, report, slug):
    """Rewrite internal page links and image attachments in the body in place."""
    # Internal links to other imported pages become real Wiki routes.
    for anchor in body.find_all("a"):
        href = anchor.get("href")
        target = _resolve_relative(page_path, href)
        if target is None:
            continue
        target_page_id = page_ids.get(target)
        if target_page_id is not None:
            anchor["href"] = f"/{slug}/wiki/{target_page_id}"
            report["links"].append({"source": page_path, "target_source": target, "target_page_id": target_page_id})
        else:
            report["links"].append({"source": page_path, "target_source": target, "target_page_id": None})

    # Attachments referenced from the body are stored once and replaced by the
    # asset id the editor resolves for ``img[src]`` (TipTap Image extension).
    asset_map = report.get("_asset_by_source", {})
    for image in body.find_all("img"):
        src = image.get("src")
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        target = _resolve_relative(page_path, src)
        asset_id = asset_map.get(target)
        if asset_id is not None:
            image["src"] = asset_id


def import_notion_html(file_obj, workspace, user, *, parent=None, limits=None):
    """Import a Notion *HTML* export ZIP (plan §13.2).

    Supported: the folder/per-page HTML layout Notion produces — hierarchy is
    derived from the folder tree, the first ``h1`` / file stem is the title,
    internal links between exported pages are rewritten to Wiki routes, and
    every non-page file is offered to the attachment pipeline. Unsupported
    entries and broken links are reported rather than silently dropped.
    """
    limits = limits or default_limits()
    entries = load_zip(file_obj, limits)
    report = _new_report("notion")

    html_paths = sorted(
        (name for name in entries if name.lower().endswith(NOTION_HTML_EXTENSIONS)),
        key=lambda name: (name.count("/"), name),
    )
    if not html_paths:
        raise WikiImportError("NO_IMPORTABLE_PAGES", "Archive contains no HTML pages to import.")
    if len(html_paths) > limits.max_pages:
        raise WikiImportError("IMPORT_PAGE_LIMIT", "Archive contains more pages than the import limit.")

    page_paths = set(html_paths)
    page_ids = {}
    page_instances = {}
    # Resolve every page's parent path first so creation can stay parent-first.
    parents = {}
    depths = {}
    for path in html_paths:
        directory = posixpath.dirname(path)
        candidate = f"{directory}.html" if directory else None
        candidate_alt = f"{directory}.htm" if directory else None
        parent_path = None
        for option in (candidate, candidate_alt):
            if option and option in page_paths:
                parent_path = option
                break
        parents[path] = parent_path
        depths[path] = 0 if parent_path is None else None

    # Compute depth with a bounded walk (cycle-safe even for a hostile archive).
    for path in html_paths:
        seen = set()
        current = path
        depth = 0
        while parents.get(current):
            if current in seen:
                raise WikiImportError("CYCLIC_HIERARCHY", "Archive page hierarchy contains a cycle.")
            seen.add(current)
            current = parents[current]
            depth += 1
            if depth > limits.max_depth:
                raise WikiImportError("IMPORT_DEPTH_LIMIT", "Archive page hierarchy is too deep.")
        depths[path] = depth

    # Attachments: every non-HTML entry is a candidate, keyed by its path.
    attachment_paths = {name for name in entries if name not in page_paths}
    order = sorted(html_paths, key=lambda item: (depths[item], item))

    with transaction.atomic():
        # Phase 1: create every page parent-first so forward links can resolve.
        bodies = {}
        for path in order:
            raw = entries[path]
            try:
                soup = BeautifulSoup(raw, "html.parser")
            except Exception:
                report["skipped"].append({"source": path, "reason": "unparseable_html"})
                continue
            body = _notion_body(soup)
            bodies[path] = body
            # A root page nests under the caller-supplied parent, if any.
            parent_instance = page_instances.get(parents[path]) if parents[path] else parent
            page = _create_page(
                workspace,
                user,
                _notion_title(soup, path),
                str(body) if body is not None else "",
                parent_instance,
                source=path,
                report=report,
            )
            page_ids[path] = str(page.pk)
            page_instances[path] = page

        # Phase 2: store attachments and rewrite links now that every page id
        # is known (a forward link may target a page created later).
        for path in order:
            body = bodies.get(path)
            page = page_instances.get(path)
            if body is None or page is None:
                continue
            referenced = set()
            for image in body.find_all("img"):
                target = _resolve_relative(path, image.get("src"))
                if target is not None and target in attachment_paths:
                    referenced.add(target)
            asset_map = report.setdefault("_asset_by_source", {})
            for name in sorted(referenced):
                if name in asset_map:
                    continue
                asset = _store_attachment(
                    report, workspace, user, page, name, posixpath.basename(name), entries[name], limits
                )
                if asset is not None:
                    asset_map[name] = str(asset.id)

            _notion_rewrite_body(body, path, page_ids, report, workspace.slug)
            page.description_html = _sanitize(str(body)) or "<p></p>"
            page.description_stripped = strip_tags(page.description_html)
            page.save(update_fields=["description_html", "description_stripped", "updated_at"])

        # Attachments that are not referenced from any imported page are still
        # captured on the report so nothing is silently lost.
        referenced_sources = set(report.get("_asset_by_source", {}).keys())
        for name in sorted(set(entries) - page_paths - referenced_sources):
            report["skipped"].append({"source": name, "reason": "unreferenced_attachment"})

    report.pop("_asset_by_source", None)
    return _finalize_report(report)


# ---------------------------------------------------------------------------
# Confluence XML import
# ---------------------------------------------------------------------------

_CONFLUENCE_MACRO_DIAGRAM = {"drawio", "drawio-macro", "drawio-sketch"}
_CONFLUENCE_MACRO_MERMAID = {"mermaid"}


def _prop_text(prop):
    return "".join(prop.itertext()).strip()


def _prop_id(prop):
    child = prop.find("id")
    if child is not None and child.text:
        return child.text.strip()
    return None


def _object_id(obj):
    """Confluence objects carry their id as a direct ``<id name="id">`` child."""
    node = obj.find("id")
    if node is not None and node.text:
        return node.text.strip()
    return None


def _parse_confluence_objects(xml_bytes):
    """Parse a Confluence ``entities.xml`` into pages/bodies/comments/attachments."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise WikiImportError("INVALID_CONFLUENCE_XML", "Confluence export XML could not be parsed.") from exc

    pages = {}
    bodies = {}
    comments = {}
    attachments = {}
    spaces = {}

    for obj in root.iter("object"):
        cls = obj.get("class")
        own_id = _object_id(obj)
        props = {prop.get("name"): prop for prop in obj.findall("property")}
        if cls == "Page":
            if not own_id:
                continue
            pages[own_id] = {
                "title": _prop_text(props["title"]) if "title" in props else "",
                "parent_id": _prop_id(props["parent"]) if "parent" in props else None,
                "space_id": _prop_id(props["space"]) if "space" in props else None,
            }
        elif cls == "BodyContent":
            content_id = _prop_id(props["content"]) if "content" in props else None
            body = props.get("body")
            if content_id and body is not None:
                bodies[content_id] = "".join(body.itertext())
        elif cls == "Comment":
            if not own_id:
                continue
            comments[own_id] = {
                "page_id": _prop_id(props["content"]) if "content" in props else None,
            }
        elif cls == "Attachment":
            if not own_id:
                continue
            attachments[own_id] = {
                "page_id": _prop_id(props["content"]) if "content" in props else None,
                "filename": _prop_text(props["fileName"]) if "fileName" in props else "",
                "title": _prop_text(props["title"]) if "title" in props else "",
            }
        elif cls == "Space":
            if own_id:
                spaces[own_id] = {
                    "key": _prop_text(props["key"]) if "key" in props else "",
                    "name": _prop_text(props["name"]) if "name" in props else "",
                }

    return {"pages": pages, "bodies": bodies, "comments": comments, "attachments": attachments, "spaces": spaces}


def _confluence_body_to_html(body, report):
    """Convert Confluence storage-format XML into sanitizable HTML.

    Practical conversions: mermaid macros become fenced code blocks, draw.io
    macros become labelled placeholders recorded on the report, ``ac:image``
    attachment references become ``<img>``, page links become anchors, and the
    remaining Confluence vocabulary is unwrapped to its text.
    """
    if not body:
        return ""
    soup = BeautifulSoup(body, "html.parser")

    for macro in soup.find_all("ac:structured-macro"):
        name = (macro.get("ac:name") or "").lower()
        if name in _CONFLUENCE_MACRO_MERMAID:
            raw = escape(macro.get_text())
            _replace_with_html(macro, f'<pre><code class="language-mermaid">{raw}</code></pre>')
            report["conversions"].append({"type": "mermaid", "converted": True})
        elif name in _CONFLUENCE_MACRO_DIAGRAM:
            title = ""
            label = macro.find("ac:parameter", attrs={"ac:name": "diagramName"})
            if label is not None:
                title = label.get_text(strip=True)
            _replace_with_html(macro, f"<p>[draw.io diagram: {escape(title or 'untitled')}]</p>")
            report["conversions"].append({"type": "drawio", "converted": False, "title": title})
        else:
            report["conversions"].append({"type": name or "unknown", "converted": False})

    for image in soup.find_all("ac:image"):
        filename = None
        attachment = image.find("ri:attachment")
        if attachment is not None:
            filename = attachment.get("ri:filename")
        if filename:
            _replace_with_html(image, f'<img alt="{escape(filename)}" src="{escape(filename)}"/>')
        else:
            image.decompose()

    for link in soup.find_all("ac:link"):
        target = link.find("ri:page")
        text = link.get_text(strip=True) or (target.get("ri:content-title") if target is not None else "")
        if target is not None:
            _replace_with_html(link, f'<a href="#">{escape(text)}</a>')
        else:
            link.replace_with(text)

    # Unwrap any remaining Confluence-specific elements, keeping their text.
    for tag in soup.find_all(re.compile(r"^(ac|ri):")):
        tag.unwrap()

    return str(soup.body) if soup.body is not None else str(soup)


def import_confluence_xml(file_obj, workspace, user, *, parent=None, limits=None):
    """Import a supported Confluence XML export ZIP (plan §13.3).

    Supported: a ZIP containing ``entities.xml`` (Confluence space export) with
    ``Page``, ``BodyContent``, ``Comment``, ``Attachment`` and ``Space``
    objects. Pages, hierarchy, comments and referenced attachments are
    imported; mermaid diagrams are converted, draw.io diagrams are recorded as
    placeholders. Anything unsupported is listed in the mapping report.
    """
    limits = limits or default_limits()
    entries = load_zip(file_obj, limits)
    report = _new_report("confluence")

    entities_name = next(
        (name for name in entries if posixpath.basename(name).lower() == "entities.xml"),
        None,
    )
    if entities_name is None:
        raise WikiImportError("UNSUPPORTED_CONFLUENCE_ARCHIVE", "Archive does not contain an entities.xml export.")

    parsed = _parse_confluence_objects(entries[entities_name])
    pages = parsed["pages"]
    bodies = parsed["bodies"]
    comments = parsed["comments"]
    attachments = parsed["attachments"]
    report["spaces"] = [{"key": space["key"], "name": space["name"]} for space in parsed["spaces"].values()]
    if not pages:
        raise WikiImportError("NO_IMPORTABLE_PAGES", "Confluence export contains no pages.")
    if len(pages) > limits.max_pages:
        raise WikiImportError("IMPORT_PAGE_LIMIT", "Confluence export contains more pages than the import limit.")

    # Depth + cycle guard over the parent graph.
    depths = {}

    def depth_of(page_id, seen):
        if page_id in depths:
            return depths[page_id]
        if page_id in seen:
            raise WikiImportError("CYCLIC_HIERARCHY", "Confluence page hierarchy contains a cycle.")
        seen.add(page_id)
        parent_id = pages[page_id].get("parent_id")
        depth = 0
        if parent_id and parent_id in pages:
            depth = depth_of(parent_id, seen) + 1
        seen.discard(page_id)
        if depth > limits.max_depth:
            raise WikiImportError("IMPORT_DEPTH_LIMIT", "Confluence page hierarchy is too deep.")
        depths[page_id] = depth
        return depth

    for page_id in pages:
        depth_of(page_id, set())

    attachment_by_filename = {
        attachment["filename"]: attachment for attachment in attachments.values() if attachment.get("filename")
    }
    name_to_archive = {posixpath.basename(name): name for name in entries}

    page_instances = {}
    with transaction.atomic():
        for page_id in sorted(pages, key=lambda pid: (depths[pid], pages[pid]["title"])):
            page_data = pages[page_id]
            body_html = _confluence_body_to_html(bodies.get(page_id, ""), report)
            parent_id = page_data.get("parent_id")
            parent_instance = page_instances.get(parent_id) if parent_id else parent
            page = _create_page(
                workspace,
                user,
                page_data.get("title") or "Untitled",
                body_html,
                parent_instance,
                source=page_id,
                report=report,
                payload={"confluence_space_id": page_data.get("space_id")},
            )
            page_instances[page_id] = page

            # Attachments referenced by this page's storage-format body.
            for filename, attachment in attachment_by_filename.items():
                if attachment.get("page_id") != page_id:
                    continue
                archive_name = name_to_archive.get(filename)
                if archive_name is None:
                    report["skipped"].append({"source": filename, "reason": "attachment_binary_missing"})
                    continue
                _store_attachment(
                    report,
                    workspace,
                    user,
                    page,
                    filename,
                    filename,
                    entries[archive_name],
                    limits,
                )

        # Comments become PageComment rows on their page.
        for comment_id in comments:
            page_id = comments[comment_id].get("page_id")
            page = page_instances.get(page_id)
            if page is None:
                report["skipped"].append({"source": comment_id, "reason": "comment_page_not_imported"})
                continue
            if len(report["comments"]) >= limits.max_comments:
                report["skipped"].append({"source": comment_id, "reason": "comment_limit"})
                continue
            html = _sanitize(_confluence_body_to_html(bodies.get(comment_id, ""), report)) or "<p></p>"
            instance = PageComment.objects.create(
                workspace=workspace,
                page=page,
                actor=user,
                comment_html=html,
            )
            report["comments"].append({"source": comment_id, "page_id": str(page.pk), "comment_id": str(instance.pk)})

    return _finalize_report(report)
