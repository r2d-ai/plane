# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Stable Wiki <-> AI contract (WIKI-10, plan §13.1).

The Wiki must expose stable APIs/events so an AI/provider integration can
consume page state without coupling to the ``Page`` tables directly (plan
§13.1). This module is that boundary:

* :func:`page_context` renders a versioned, permission-filtered context
  envelope for one page (content + hierarchy + labels + capabilities).
* :func:`emit_wiki_event` appends to the ``WikiEvent`` feed, the durable
  event stream a consumer tails instead of watching the database.
* :func:`iter_wiki_events` reads that feed back, filtered by the caller's
  effective page visibility, so private pages never leak through events
  (spec §22.5).
* :func:`summarize_html`, :func:`suggest_labels` and :func:`search_pages`
  implement the deferred capabilities (summarize / label suggestions /
  natural-language search) with deterministic, provider-free primitives. A
  real provider plugs in above these functions; the API shape stays the same.

Nothing here trusts the caller: every page-level read goes through the
centralized effective-access service (:mod:`plane.utils.page_access`), so the
AI layer cannot become a BOLA bypass.
"""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from django.conf import settings
from django.db.models import Q

from plane.db.models import Label, Page, PageCollectionPage, WikiEvent
from plane.utils.page_access import (
    _UNSET,
    Capability,
    can_view_page,
    filter_visible_pages,
    get_page_capabilities,
    hidden_page_ids,
    resolve_workspace_role,
    searchable_page_q,
)

SCHEMA_VERSION = getattr(settings, "WIKI_AI_CONTEXT_SCHEMA_VERSION", "1.0")

# Words that carry no retrieval signal in a natural-language Wiki query.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "by",
    "with",
    "about",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "this",
    "that",
    "these",
    "those",
    "page",
    "pages",
    "wiki",
    "find",
    "show",
    "me",
    "all",
    "any",
    "please",
    "can",
    "you",
    "what",
    "which",
    "where",
    "who",
    "how",
    "when",
    "why",
    "do",
    "does",
    "did",
    "i",
    "we",
    "our",
    "my",
    "it",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[0-9a-zA-Z\u00c0-\u024f\u0400-\u04ff\u4e00-\u9fff]+")


def _is_enabled():
    return bool(getattr(settings, "WIKI_AI_ENABLED", True))


def _limit(setting_name, default):
    value = getattr(settings, setting_name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Event feed
# ---------------------------------------------------------------------------


def emit_wiki_event(page, event_type, *, actor=None, payload=None, workspace=None):
    """Append one event to the durable Wiki event feed.

    ``payload`` must stay metadata-only: never put ``description_html`` or
    ``description_json`` in it (spec §20 "avoid embedding sensitive page
    content by default"). ``page_id`` is embedded for consumers that need to
    resolve the page again through the REST API.
    """
    if page is None:
        return None
    ws = workspace if workspace is not None else page.workspace
    body = dict(payload or {})
    body.setdefault("page_id", str(page.pk))
    body.setdefault("scope", page.scope if hasattr(page, "scope") else None)
    return WikiEvent.objects.create(
        workspace=ws,
        page=page,
        page_name=(page.name or "")[:255],
        event_type=event_type,
        actor=actor,
        payload=body,
    )


def iter_wiki_events(workspace, user, *, since=None, limit=None, event_types=None):
    """Return the event feed filtered to pages ``user`` may view.

    Visibility is computed once for the workspace (public + owned + shared,
    minus private-Collection subtrees) and then applied as an ``id__in`` filter
    so events for private pages are never returned (spec §22.5). Events whose
    page was hard-deleted (``page IS NULL``) are only returned to workspace
    admins/owners, who may audit them.
    """
    limit = min(int(limit or _limit("WIKI_AI_MAX_EVENTS", 200)), _limit("WIKI_AI_MAX_EVENTS", 200))
    role = resolve_workspace_role(workspace.id, getattr(user, "id", None))

    queryset = WikiEvent.objects.filter(workspace=workspace).select_related("actor", "page")
    if since is not None:
        queryset = queryset.filter(created_at__gt=since)
    if event_types:
        queryset = queryset.filter(event_type__in=event_types)

    visible = set(
        filter_visible_pages(
            Page.objects.filter(workspace=workspace, is_global=True),
            user,
            workspace,
            workspace_role=role,
        ).values_list("id", flat=True)
    )

    from plane.utils.page_access import is_workspace_admin

    if is_workspace_admin(workspace, user, workspace_role=role):
        queryset = queryset.filter(Q(page_id__in=visible) | Q(page__isnull=True))
    else:
        queryset = queryset.filter(page_id__in=visible)

    return queryset.order_by("-created_at")[:limit]


# ---------------------------------------------------------------------------
# Page context
# ---------------------------------------------------------------------------


def page_breadcrumbs(page, user=None, workspace=None, *, workspace_role=_UNSET, resolver=None):
    """Visible ancestor chain from the root to ``page`` (cycle-safe, bounded).

    An ancestor the caller cannot view is dropped from the chain: a public page
    under a private parent must not leak that parent's id or name through the
    context envelope (spec §22.5). The page itself is always included — the
    caller already passed the VIEW check before this is called.
    """
    chain = []
    seen = set()
    current = page
    while current is not None and current.pk not in seen:
        seen.add(current.pk)
        if user is None or can_view_page(user, current, workspace, workspace_role=workspace_role, resolver=resolver):
            chain.append({"id": str(current.pk), "name": current.name or ""})
        if current.parent_id is None:
            break
        current = (
            Page.objects.filter(pk=current.parent_id)
            .select_related("workspace")
            .only("id", "name", "parent_id", "workspace", "access", "owned_by")
            .first()
        )
    chain.reverse()
    return chain


def _page_collection(page):
    association = (
        PageCollectionPage.objects.filter(page_id=page.pk, deleted_at__isnull=True).select_related("collection").first()
    )
    if association is None or association.collection.deleted_at is not None:
        return None
    return {"id": str(association.collection.id), "name": association.collection.name}


def page_context(page, user, workspace=None, *, resolver=None, workspace_role=_UNSET):
    """Versioned, permission-filtered AI context envelope for ``page``.

    Returns ``None`` when the caller has no VIEW capability, so a caller can
    never receive context for a page it cannot read (spec §22.5 "AI context").
    The envelope is intentionally schema-versioned: consumers negotiate
    ``schema_version`` and the Wiki can evolve without breaking them.
    """
    workspace = workspace if workspace is not None else page.workspace
    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, getattr(user, "id", None))
    capability = get_page_capabilities(user, page, workspace, workspace_role=workspace_role, resolver=resolver)
    if capability < Capability.VIEW:
        return None

    labels = [
        {"id": str(label_id), "name": name}
        for label_id, name in (
            Page.objects.filter(pk=page.pk).values_list("labels__id", "labels__name").order_by("labels__name")
        )
        if label_id is not None
    ]
    # Children go through the same visibility policy as the Wiki list, so a
    # private child, a child behind a private Collection boundary, or a child
    # only reachable through an unshared private parent is never listed
    # (spec §22.5).
    children = list(
        filter_visible_pages(
            Page.objects.filter(workspace=workspace, is_global=True, parent_id=page.pk, archived_at__isnull=True),
            user,
            workspace,
            workspace_role=workspace_role,
        )
        .values("id", "name")
        .order_by("sort_order", "name")[:50]
    )

    breadcrumbs = page_breadcrumbs(page, user, workspace, workspace_role=workspace_role, resolver=resolver)
    # The visible parent is the nearest visible ancestor; a private parent is
    # reported as absent rather than leaked by id (spec §22.5).
    visible_parent_id = breadcrumbs[-2]["id"] if len(breadcrumbs) >= 2 else None

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_for": {"user_id": str(getattr(user, "id", ""))},
        "page": {
            "id": str(page.pk),
            "name": page.name or "",
            "description_html": page.description_html or "",
            "description_stripped": page.description_stripped or "",
            "description_json": page.description_json or {},
            "access": page.access,
            "is_locked": page.is_locked,
            "archived_at": page.archived_at.isoformat() if page.archived_at else None,
            "updated_at": page.updated_at.isoformat() if page.updated_at else None,
            "owned_by": str(page.owned_by_id) if page.owned_by_id else None,
        },
        "hierarchy": {
            "parent_id": visible_parent_id,
            "breadcrumbs": breadcrumbs,
            "children": [{"id": str(child["id"]), "name": child["name"]} for child in children],
        },
        "labels": labels,
        "collection": _page_collection(page),
        "capabilities": {
            "view": capability >= Capability.VIEW,
            "comment": capability >= Capability.COMMENT,
            "edit": capability >= Capability.EDIT,
        },
    }


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def _html_text(html):
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def summarize_html(html, *, max_sentences=5):
    """Deterministic extractive summary of page HTML (no external provider).

    Sentences are ranked by term frequency (title terms are not special-cased
    here), the top ``max_sentences`` kept, then restored to document order so
    the result reads naturally. A real provider can replace this function
    behind the same endpoint without changing the API contract.
    """
    text = _html_text(html)
    if not text:
        return ""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    counts = Counter(word for word in _WORD.findall(text.lower()))
    scored = []
    for index, sentence in enumerate(sentences):
        words = _WORD.findall(sentence.lower())
        if not words:
            continue
        score = sum(counts[word] for word in words) / len(words)
        scored.append((score, index, sentence))
    top = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_sentences]
    ordered = [sentence for _, _, sentence in sorted(top, key=lambda item: item[1])]
    return " ".join(ordered)


# ---------------------------------------------------------------------------
# Label suggestions
# ---------------------------------------------------------------------------


def suggest_labels(page, workspace, *, limit=None):
    """Suggest existing workspace labels for ``page`` (plan §13.1).

    Suggestions are derived from the page title and content matching a
    workspace-level label's name tokens. A real AI provider can re-rank or
    extend this list; the endpoint contract (label id + name + score + reason)
    stays stable.
    """
    limit = min(int(limit or _limit("WIKI_AI_MAX_SUGGESTIONS", 10)), _limit("WIKI_AI_MAX_SUGGESTIONS", 10))
    title = (page.name or "").lower()
    body = (page.description_stripped or page.name or "").lower()
    if not body:
        return []

    existing = set(Page.objects.filter(pk=page.pk).values_list("labels__id", flat=True))
    candidates = Label.objects.filter(workspace=workspace, project__isnull=True, deleted_at__isnull=True)
    suggestions = []
    for label in candidates:
        if label.id in existing:
            continue
        tokens = [token for token in _WORD.findall((label.name or "").lower()) if token not in _STOPWORDS]
        if not tokens:
            continue
        title_hits = sum(1 for token in tokens if token in title)
        body_hits = sum(body.count(token) for token in tokens)
        if title_hits == 0 and body_hits == 0:
            continue
        score = title_hits * 3 + body_hits
        suggestions.append(
            {
                "label_id": str(label.id),
                "name": label.name,
                "score": score,
                "reason": "title match" if title_hits else "content match",
            }
        )
    suggestions.sort(key=lambda item: (-item["score"], item["name"] or ""))
    return suggestions[:limit]


# ---------------------------------------------------------------------------
# Natural-language search
# ---------------------------------------------------------------------------


def parse_query(raw):
    """Turn a natural-language Wiki query into retrieval terms.

    Extracts quoted phrases and meaningful keywords (stopwords removed) so the
    same input works for a keyword backend today and a semantic backend later.
    """
    raw = (raw or "").strip()
    phrases = [phrase.lower() for phrase in re.findall(r'"([^"]+)"', raw)]
    unquoted = re.sub(r'"[^"]*"', " ", raw)
    keywords = []
    for token in _WORD.findall(unquoted.lower()):
        if len(token) < 3 or token in _STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return {"raw": raw, "phrases": phrases, "keywords": keywords}


def search_pages(user, workspace, query, *, limit=None, workspace_role=_UNSET, resolver=None):
    """Permission-filtered keyword search over Wiki pages.

    Only pages the caller may view are ever considered (spec §6, §22.5), and
    private pages are excluded from the discoverable set exactly like the
    workspace search contract. Results carry a short text snippet, never the
    full body.
    """
    limit = min(int(limit or _limit("WIKI_AI_SEARCH_MAX_RESULTS", 25)), _limit("WIKI_AI_SEARCH_MAX_RESULTS", 25))
    parsed = parse_query(query)
    if not parsed["keywords"] and not parsed["phrases"]:
        return {"query": parsed, "results": []}

    if workspace_role is _UNSET:
        workspace_role = resolve_workspace_role(workspace.id, getattr(user, "id", None))

    # Same discoverability policy as the workspace Wiki search (spec §6.5):
    # public pages plus private pages an explicit share grants, minus subtrees
    # behind a private Collection boundary. A private page never appears in an
    # AI result even for its owner, so the surface cannot be used to enumerate.
    queryset = Page.objects.filter(
        workspace=workspace,
        is_global=True,
        archived_at__isnull=True,
    ).filter(searchable_page_q(user, workspace))
    hidden = hidden_page_ids(workspace, user, workspace_role=workspace_role)
    if hidden:
        queryset = queryset.exclude(id__in=hidden)

    condition = Q()
    for keyword in parsed["keywords"]:
        condition |= Q(name__icontains=keyword) | Q(description_stripped__icontains=keyword)
    for phrase in parsed["phrases"]:
        condition |= Q(name__icontains=phrase) | Q(description_stripped__icontains=phrase)
    queryset = queryset.filter(condition).distinct()

    results = []
    for page in queryset.select_related("owned_by")[: limit * 2]:
        title = (page.name or "").lower()
        body = (page.description_stripped or "").lower()
        score = 0
        for keyword in parsed["keywords"]:
            if keyword in title:
                score += 5
            score += min(body.count(keyword), 5)
        for phrase in parsed["phrases"]:
            if phrase in title:
                score += 8
            score += min(body.count(phrase), 5) * 2
        if score == 0:
            continue
        results.append(
            {
                "id": str(page.pk),
                "name": page.name or "",
                "snippet": _snippet(page.description_stripped or "", parsed),
                "score": score,
                "owned_by": str(page.owned_by_id) if page.owned_by_id else None,
                "access": page.access,
            }
        )
    results.sort(key=lambda item: (-item["score"], item["name"].lower()))
    results = results[:limit]
    return {"query": parsed, "results": results}


def _snippet(text, parsed, *, length=240):
    if not text:
        return ""
    lowered = text.lower()
    index = -1
    for term in parsed["phrases"] + parsed["keywords"]:
        found = lowered.find(term)
        if found != -1 and (index == -1 or found < index):
            index = found
    if index == -1:
        return text[:length]
    start = max(0, index - 60)
    return text[start : start + length]
