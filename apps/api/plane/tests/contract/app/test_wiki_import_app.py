# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-10 contract tests: Notion / Confluence importers (plan §13.2/§13.3).

Covers the happy path (pages, hierarchy, attachments, comments, links,
mapping report), structured errors for malformed archives, path-traversal and
symlink rejection, page/entry limits, permission denial and BOLA/IDOR scoping.
"""

import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Page, PageComment, User, WikiEvent, Workspace, WorkspaceMember


def _notion_url(slug):
    return f"/api/workspaces/{slug}/wiki/import/notion/"


def _confluence_url(slug):
    return f"/api/workspaces/{slug}/wiki/import/confluence/"


def _make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0], first_name="Other", last_name="User")


def _member(workspace, user, role=15):
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _zip_upload(files, name="export.zip"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


NOTION_ROOT = """<html><body><article><h1 class="page-title">Handbook</h1><div class="page-body">
<p>See <a href="Handbook/Child.html">the child page</a>.</p>
<img src="Handbook/logo.png" alt="logo"/>
</div></article></body></html>"""

NOTION_CHILD = """<html><body><article><h1 class="page-title">Child</h1><div class="page-body">
<p>Child body</p></div></article></body></html>"""


@pytest.fixture
def fake_attachment_storage(monkeypatch):
    """Persist attachments as FileAsset rows without touching an object store."""

    def _persist(workspace, user, page, name, content, content_type):
        return FileAsset.objects.create(
            attributes={"name": name, "type": content_type, "size": len(content)},
            asset=f"{workspace.id}/{name}",
            workspace=workspace,
            page=page,
            user=user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
            entity_identifier=str(page.pk),
            size=len(content),
            is_uploaded=True,
        )

    monkeypatch.setattr("plane.utils.wiki_import._persist_attachment", _persist)


CONFLUENCE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<confluence xmlns:ac="http://atlassian.com/content" xmlns:ri="http://atlassian.com/resource/identifier">
  <object class="Space">
    <id name="id">1</id>
    <property name="key">DOC</property>
    <property name="name">Docs</property>
  </object>
  <object class="Page">
    <id name="id">100</id>
    <property name="title">Home</property>
    <property name="space"><id name="id">1</id></property>
  </object>
  <object class="Page">
    <id name="id">101</id>
    <property name="title">Child</property>
    <property name="parent"><id name="id">100</id></property>
    <property name="space"><id name="id">1</id></property>
  </object>
  <object class="BodyContent">
    <id name="id">200</id>
    <property name="content"><id name="id">100</id></property>
    <property name="body">&lt;p&gt;Home body&lt;/p&gt;&lt;ac:structured-macro ac:name="mermaid"&gt;
      &lt;ac:plain-text-body&gt;graph TD&lt;/ac:plain-text-body&gt;&lt;/ac:structured-macro&gt;</property>
  </object>
  <object class="BodyContent">
    <id name="id">201</id>
    <property name="content"><id name="id">101</id></property>
    <property name="body">&lt;p&gt;Child body&lt;/p&gt;</property>
  </object>
  <object class="Comment">
    <id name="id">300</id>
    <property name="content"><id name="id">100</id></property>
  </object>
  <object class="BodyContent">
    <id name="id">301</id>
    <property name="content"><id name="id">300</id></property>
    <property name="body">&lt;p&gt;a comment&lt;/p&gt;</property>
  </object>
  <object class="Attachment">
    <id name="id">400</id>
    <property name="content"><id name="id">100</id></property>
    <property name="fileName">diagram.png</property>
  </object>
</confluence>"""


@pytest.mark.contract
class TestNotionImport:
    @pytest.mark.django_db
    def test_imports_hierarchy_attachments_and_links(
        self, session_client, workspace, create_user, fake_attachment_storage
    ):
        upload = _zip_upload(
            {
                "Handbook.html": NOTION_ROOT,
                "Handbook/Child.html": NOTION_CHILD,
                "Handbook/logo.png": b"\x89PNG-bytes",
            }
        )

        response = session_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 201
        report = response.json()["mapping_report"]
        assert report["stats"]["pages"] == 2
        assert report["stats"]["attachments"] == 1
        assert report["stats"]["links"] == 1

        root = Page.objects.get(workspace=workspace, name="Handbook")
        child = Page.objects.get(workspace=workspace, name="Child")
        assert child.parent_id == root.id
        assert child.is_global is True

        attachment = report["attachments"][0]
        assert attachment["name"] == "logo.png"
        assert attachment["stored"] is True
        root.refresh_from_db()
        assert attachment["file_asset_id"] in root.description_html

        link = report["links"][0]
        assert link["target_page_id"] == str(child.id)
        assert f"/{workspace.slug}/wiki/{child.id}" in root.description_html

        assert WikiEvent.objects.filter(workspace=workspace, event_type=WikiEvent.PAGE_IMPORTED).count() == 2

    @pytest.mark.django_db
    def test_path_traversal_rejected(self, session_client, workspace, create_user):
        upload = _zip_upload({"../evil.html": b"<html><body>evil</body></html>"})

        response = session_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSAFE_ARCHIVE_PATH"

    @pytest.mark.django_db
    def test_invalid_archive_rejected(self, session_client, workspace, create_user):
        upload = SimpleUploadedFile("bad.zip", b"not a zip", content_type="application/zip")

        response = session_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_ARCHIVE"

    @pytest.mark.django_db
    def test_missing_file_rejected(self, session_client, workspace, create_user):
        response = session_client.post(_notion_url(workspace.slug), {}, format="multipart")
        assert response.status_code == 400
        assert response.json()["error_code"] == "IMPORT_FILE_REQUIRED"

    @pytest.mark.django_db
    def test_page_limit_rejected(self, settings, session_client, workspace, create_user):
        settings.WIKI_IMPORT_MAX_PAGES = 1
        upload = _zip_upload(
            {
                "Handbook.html": NOTION_ROOT,
                "Handbook/Child.html": NOTION_CHILD,
            }
        )

        response = session_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart")
        assert response.status_code == 400
        assert response.json()["error_code"] == "IMPORT_PAGE_LIMIT"

    @pytest.mark.django_db
    def test_guest_cannot_import(self, api_client, workspace, create_user):
        guest = _member(workspace, _make_user("guest-import@plane.so"), role=5)
        upload = _zip_upload({"Handbook.html": NOTION_ROOT})

        api_client.force_authenticate(user=guest)
        assert api_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart").status_code == 403

    @pytest.mark.django_db
    def test_non_member_cannot_import(self, api_client, workspace, create_user):
        outsider = _make_user("outsider-import@plane.so")
        upload = _zip_upload({"Handbook.html": NOTION_ROOT})

        api_client.force_authenticate(user=outsider)
        assert api_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart").status_code == 403

    @pytest.mark.django_db
    def test_import_nests_under_parent(self, session_client, workspace, create_user):
        parent = Page.objects.create(workspace=workspace, owned_by=create_user, name="Root", is_global=True)
        upload = _zip_upload({"Handbook.html": NOTION_ROOT})

        response = session_client.post(
            _notion_url(workspace.slug),
            {"file": upload, "parent": str(parent.id)},
            format="multipart",
        )

        assert response.status_code == 201
        imported = Page.objects.get(workspace=workspace, name="Handbook")
        assert imported.parent_id == parent.id

    @pytest.mark.django_db
    def test_parent_from_other_workspace_not_found(self, session_client, workspace, create_user):
        other = Workspace.objects.create(name="Other", slug="other-workspace", owner=create_user)
        foreign = Page.objects.create(workspace=other, owned_by=create_user, name="Foreign", is_global=True)
        upload = _zip_upload({"Handbook.html": NOTION_ROOT})

        response = session_client.post(
            _notion_url(workspace.slug),
            {"file": upload, "parent": str(foreign.id)},
            format="multipart",
        )
        assert response.status_code == 404


@pytest.mark.contract
class TestConfluenceImport:
    @pytest.mark.django_db
    def test_imports_pages_comments_attachments_and_mermaid(
        self, session_client, workspace, create_user, fake_attachment_storage
    ):
        upload = _zip_upload(
            {
                "entities.xml": CONFLUENCE_XML,
                "attachments/diagram.png": b"\x89PNG-bytes",
            }
        )

        response = session_client.post(_confluence_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 201
        report = response.json()["mapping_report"]
        assert report["stats"]["pages"] == 2
        assert report["stats"]["comments"] == 1
        assert report["stats"]["attachments"] == 1
        assert {"key": "DOC", "name": "Docs"} in report["spaces"]
        assert any(item["type"] == "mermaid" and item["converted"] for item in report["conversions"])

        home = Page.objects.get(workspace=workspace, name="Home")
        child = Page.objects.get(workspace=workspace, name="Child")
        assert child.parent_id == home.id
        assert "language-mermaid" in home.description_html
        assert PageComment.objects.filter(page=home).count() == 1
        assert report["comments"][0]["page_id"] == str(home.id)

    @pytest.mark.django_db
    def test_missing_entities_rejected(self, session_client, workspace, create_user):
        upload = _zip_upload({"readme.txt": b"nothing here"})

        response = session_client.post(_confluence_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_CONFLUENCE_ARCHIVE"

    @pytest.mark.django_db
    def test_invalid_xml_rejected(self, session_client, workspace, create_user):
        upload = _zip_upload({"entities.xml": b"<not-xml"})

        response = session_client.post(_confluence_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_CONFLUENCE_XML"

    @pytest.mark.django_db
    def test_symlink_entry_rejected(self, session_client, workspace, create_user):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            info = zipfile.ZipInfo("link.html")
            info.external_attr = 0o120777 << 16
            archive.writestr(info, b"<html></html>")
        upload = SimpleUploadedFile("export.zip", buffer.getvalue(), content_type="application/zip")

        response = session_client.post(_notion_url(workspace.slug), {"file": upload}, format="multipart")

        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSAFE_ARCHIVE_PATH"
