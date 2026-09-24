import pytest
from django.utils import timezone

from plane.db.models import (
    Page,
    PageCollection,
    PageCollectionPage,
    PageShare,
    Project,
    ProjectMember,
    ProjectPage,
    User,
    UserFavorite,
    Workspace,
    WorkspaceMember,
)

pytestmark = pytest.mark.django_db


def make_user(email):
    return User.objects.create(email=email, username=email.split("@")[0])


def make_workspace(name, slug, owner):
    return Workspace.objects.create(name=name, slug=slug, owner=owner)


def add_member(workspace, user, **kwargs):
    return WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, **kwargs)


def make_wiki_page(workspace, owner, name="Launch handbook", **kwargs):
    return Page.objects.create(workspace=workspace, owned_by=owner, name=name, is_global=True, **kwargs)


@pytest.fixture
def context(api_client, settings, create_user):
    owner = make_user("owner@example.com")
    default = make_workspace("Instance", "home", owner)
    allowed = make_workspace("Marketing", "mkt", owner)
    denied = make_workspace("Finance", "fin", owner)
    add_member(allowed, create_user, is_active=True)
    add_member(denied, create_user, is_active=False)
    settings.COMPANY_WIKI_WORKSPACE_SLUG = default.slug
    settings.COMPANY_WIKI_OPEN_READ = True
    api_client.force_authenticate(user=create_user)
    return create_user, owner, default, allowed, denied


def result_ids(response):
    assert response.status_code == 200, response.content
    return {row["page_id"] for row in response.json()["results"]}


def test_scopes(context, api_client):
    response = api_client.get("/api/wiki/scopes/")
    assert response.status_code == 200
    assert [(r["slug"], r["is_default"], r["is_member"], r["can_create"]) for r in response.json()] == [
        ("home", True, False, False),
        ("mkt", False, True, True),
    ]
    assert all(not scope["can_manage_collections"] for scope in response.json())


def test_scope_reports_collection_management_for_owner(context, api_client):
    user, _, _, _, _ = context
    managed = make_workspace("Managed", "managed", user)
    add_member(managed, user, is_active=True)
    scopes = api_client.get("/api/wiki/scopes/").json()
    assert next(scope for scope in scopes if scope["slug"] == "managed")["can_manage_collections"] is True


def test_search_visibility(context, api_client):
    user, owner, default, allowed, denied = context
    visible = [make_wiki_page(default, owner), make_wiki_page(allowed, owner)]
    make_wiki_page(denied, owner)
    make_wiki_page(allowed, owner, access=Page.PRIVATE_ACCESS)
    response = api_client.get("/api/wiki/search/", {"query": "Launch"})
    assert result_ids(response) == {str(p.id) for p in visible}
    assert {r["workspace_slug"] for r in response.json()["results"]} == {"home", "mkt"}


def test_workspace_global_search_includes_visible_wiki_page(context, api_client):
    _, owner, _, workspace, _ = context
    page = make_wiki_page(workspace, owner, name="Handbook")
    response = api_client.get(
        f"/api/workspaces/{workspace.slug}/search/",
        {"search": "Handbook", "workspace_search": "true"},
    )
    assert response.status_code == 200, response.content
    assert any(str(item["id"]) == str(page.id) and item["project_ids"] == [] for item in response.json()["results"]["page"])


def test_workspace_global_search_respects_private_pages_and_collections(context, api_client):
    user, owner, _, workspace, _ = context
    visible = make_wiki_page(workspace, owner, name="Handbook visible")
    make_wiki_page(workspace, owner, name="Handbook private", access=Page.PRIVATE_ACCESS)
    shared = make_wiki_page(workspace, owner, name="Handbook shared", access=Page.PRIVATE_ACCESS)
    PageShare.objects.create(workspace=workspace, page=shared, member=user, role=PageShare.ROLE_VIEW)
    hidden = make_wiki_page(workspace, owner, name="Handbook hidden")
    collection = PageCollection.objects.create(workspace=workspace, name="Secret", access=PageCollection.ACCESS_PRIVATE)
    PageCollectionPage.objects.create(workspace=workspace, collection=collection, page=hidden)

    response = api_client.get(
        f"/api/workspaces/{workspace.slug}/search/",
        {"search": "Handbook", "workspace_search": "true", "entities": "page"},
    )
    assert response.status_code == 200, response.content
    assert {str(item["id"]) for item in response.json()["results"]["page"]} == {str(visible.id), str(shared.id)}


def test_project_page_search_keeps_project_result(context, api_client):
    user, owner, _, workspace, _ = context
    project = Project.objects.create(workspace=workspace, name="Campaign", identifier="CMP")
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=20, is_active=True)
    page = Page.objects.create(workspace=workspace, owned_by=owner, name="Handbook project")
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)

    response = api_client.get(
        f"/api/workspaces/{workspace.slug}/search/",
        {"search": "Handbook", "project_id": str(project.id), "workspace_search": "false", "entities": "page"},
    )
    assert response.status_code == 200, response.content
    assert [(str(item["id"]), item["project_ids"], item["project_identifiers"]) for item in response.json()["results"]["page"]] == [
        (str(page.id), [str(project.id)], [project.identifier])
    ]


def test_owned_private_and_inherited_shares(context, api_client):
    user, owner, _, workspace, _ = context
    owned = make_wiki_page(workspace, user, access=Page.PRIVATE_ACCESS)
    shared = make_wiki_page(workspace, owner, access=Page.PRIVATE_ACCESS)
    child = make_wiki_page(workspace, owner, access=Page.PRIVATE_ACCESS, parent=shared)
    PageShare.objects.create(workspace=workspace, page=shared, member=user, role=PageShare.ROLE_VIEW)
    assert result_ids(api_client.get("/api/wiki/search/", {"query": "Launch"})) == {
        str(p.id) for p in (owned, shared, child)
    }


def test_non_member_share_visibility_in_default_workspace(api_client, settings, create_user):
    # A caller without membership in the open-read default workspace keeps the
    # visibility its direct PageShare grants: the brief prescribes
    # page_visibility_q + hidden_page_ids and nothing more, so an active share
    # surfaces its page in search and in section=shared while a revoked share
    # grants nothing.
    user = create_user
    owner = make_user("owner@example.com")
    default = make_workspace("Instance", "home", owner)
    add_member(make_workspace("Marketing", "mkt", owner), user, is_active=True)
    settings.COMPANY_WIKI_WORKSPACE_SLUG = default.slug
    settings.COMPANY_WIKI_OPEN_READ = True
    shared_public = make_wiki_page(default, owner, name="Launch public shared", access=Page.PUBLIC_ACCESS)
    shared_private = make_wiki_page(default, owner, name="Launch private shared", access=Page.PRIVATE_ACCESS)
    revoked = make_wiki_page(default, owner, name="Launch revoked share", access=Page.PRIVATE_ACCESS)
    for page in (shared_public, shared_private):
        PageShare.objects.create(workspace=default, page=page, member=user, role=PageShare.ROLE_VIEW)
    PageShare.objects.create(
        workspace=default, page=revoked, member=user, role=PageShare.ROLE_VIEW, deleted_at=timezone.now()
    )
    api_client.force_authenticate(user=user)

    # The share-only page must not disappear; the revoked-share page must not
    # reappear in either result set.
    shared_ids = {str(shared_public.id), str(shared_private.id)}
    assert result_ids(api_client.get("/api/wiki/search/", {"query": "Launch"})) == shared_ids
    assert result_ids(api_client.get("/api/wiki/personal/", {"section": "shared"})) == shared_ids


def test_private_collection_subtree(context, api_client):
    user, owner, _, workspace, _ = context
    parent = make_wiki_page(workspace, user)
    child = make_wiki_page(workspace, owner, parent=parent)
    collection = PageCollection.objects.create(
        workspace=workspace, name="Private", access=PageCollection.ACCESS_PRIVATE
    )
    PageCollectionPage.objects.create(workspace=workspace, collection=collection, page=parent)
    PageShare.objects.create(workspace=workspace, page=child, member=user, role=PageShare.ROLE_VIEW)
    assert result_ids(api_client.get("/api/wiki/search/", {"query": "Launch"})) == set()


def test_archived_and_deleted_pages(context, api_client):
    user, owner, _, workspace, _ = context
    make_wiki_page(workspace, owner, archived_at=timezone.now())
    make_wiki_page(workspace, owner, deleted_at=timezone.now())
    assert result_ids(api_client.get("/api/wiki/search/", {"query": "Launch"})) == set()


def test_open_read_disabled_preserves_membership(context, api_client, settings):
    user, owner, default, workspace, _ = context
    settings.COMPANY_WIKI_OPEN_READ = False
    make_wiki_page(default, owner)
    visible = make_wiki_page(workspace, owner)
    assert result_ids(api_client.get("/api/wiki/search/", {"query": "Launch"})) == {str(visible.id)}
    assert [r["slug"] for r in api_client.get("/api/wiki/scopes/").json()] == ["mkt"]


@pytest.mark.parametrize(
    "params",
    [{}, {"query": "  "}, {"query": "x", "limit": 101}, {"query": "x", "limit": 0}, {"query": "x", "limit": "bad"}],
)
def test_invalid_search(context, api_client, params):
    assert api_client.get("/api/wiki/search/", params).status_code == 400


@pytest.mark.parametrize("section", ["favorites", "owned", "shared"])
def test_personal_sections(context, api_client, section):
    user, owner, _, workspace, denied = context
    owned = make_wiki_page(workspace, user)
    favorite = make_wiki_page(workspace, owner)
    shared = make_wiki_page(workspace, owner, access=Page.PRIVATE_ACCESS)
    make_wiki_page(workspace, owner, parent=shared, access=Page.PRIVATE_ACCESS)
    hidden = make_wiki_page(workspace, user)
    boundary = make_wiki_page(workspace, owner)
    hidden.parent = boundary
    hidden.save()
    collection = PageCollection.objects.create(
        workspace=workspace, name="Private", access=PageCollection.ACCESS_PRIVATE
    )
    PageCollectionPage.objects.create(workspace=workspace, collection=collection, page=boundary)
    for page in (favorite, hidden):
        UserFavorite.objects.create(workspace=workspace, user=user, entity_type="page", entity_identifier=page.id)
    UserFavorite.objects.create(workspace=workspace, user=owner, entity_type="page", entity_identifier=owned.id)
    for page in (shared, hidden):
        PageShare.objects.create(workspace=workspace, page=page, member=user, role=PageShare.ROLE_VIEW)
    revoked = make_wiki_page(workspace, owner)
    PageShare.objects.create(
        workspace=workspace, page=revoked, member=user, role=PageShare.ROLE_VIEW, deleted_at=timezone.now()
    )
    make_wiki_page(denied, user)
    response = api_client.get("/api/wiki/personal/", {"section": section})
    assert result_ids(response) == {str({"favorites": favorite, "owned": owned, "shared": shared}[section].id)}
    assert all(
        r["workspace_slug"] == workspace.slug and r["workspace_name"] == workspace.name
        for r in response.json()["results"]
    )


def test_invalid_personal_section(context, api_client):
    assert api_client.get("/api/wiki/personal/", {"section": "unknown"}).status_code == 400


def test_personal_pages_paginate_and_filter_across_workspaces(context, api_client):
    user, _, default, workspace, denied = context
    expected = {
        str(make_wiki_page(default if index % 2 else workspace, user, name=f"Handbook {index:02d}").id)
        for index in range(31)
    }
    make_wiki_page(denied, user, name="Handbook inaccessible")
    make_wiki_page(workspace, user, name="Other document")

    found = []
    cursor = None
    for _ in range(7):
        params = {"section": "owned", "query": "Handbook", "limit": 7}
        if cursor:
            params["cursor"] = cursor
        response = api_client.get("/api/wiki/personal/", params)
        assert response.status_code == 200, response.content
        found.extend(row["page_id"] for row in response.json()["results"])
        cursor = response.json()["next_cursor"]
        if not cursor:
            break

    assert set(found) == expected
    assert len(found) == len(expected)
    assert cursor is None


def test_personal_pages_reject_invalid_pagination(context, api_client):
    for params in (
        {"section": "owned", "limit": "bad"},
        {"section": "owned", "limit": 0},
        {"section": "owned", "query": "x" * 201},
        {"section": "owned", "cursor": "tampered"},
    ):
        assert api_client.get("/api/wiki/personal/", params).status_code == 400


def test_content_summary_and_workspace_limit(context, api_client):
    user, owner, default, workspace, _ = context
    for i in range(23):
        make_wiki_page(workspace, owner, name=f"Page {i}", description_html="<p>" + "needle " * 40 + "</p>")
    make_wiki_page(default, owner, description_html="<p>needle</p>")
    response = api_client.get("/api/wiki/search/", {"query": "needle", "limit": 100})
    assert len(result_ids(response)) == 21
    assert all(
        len(r["matched_content_summary"]) <= 160 and "description_html" not in r for r in response.json()["results"]
    )
    assert len(result_ids(api_client.get("/api/wiki/search/", {"query": "needle", "limit": 3}))) == 3
