# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Stable Wiki <-> AI endpoints (WIKI-10, plan §13.1).

These endpoints are the *only* supported way an AI/provider integration reads
or mutates Wiki state. They are deliberately thin: authorization is the shared
``WorkspacePagePermission`` (same effective-access service as the rest of the
Wiki), and every payload is produced by :mod:`plane.utils.wiki_ai`, so a
consumer never touches the ``Page`` tables directly.

In scope for this PR (plan §13.1 "subset acceptable"):

* ``GET  .../pages/<page_id>/ai/context/``          — versioned context envelope
* ``POST .../pages/<page_id>/ai/summarize/``        — deterministic summary
* ``POST .../pages/<page_id>/ai/apply/``            — agent edit (versioned)
* ``POST .../pages/<page_id>/ai/label-suggestions/``— label suggestions
* ``POST .../wiki/ai/search/``                      — natural-language search
* ``GET  .../wiki/ai/events/``                      — durable event feed

The inline "AI block" remains provider-dependent and is intentionally left to a
follow-up: its contract is the same context/event surface plus the editor's
extension seam.
"""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.dateparse import parse_datetime

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkspacePagePermission
from plane.app.serializers import (
    WikiAIApplySerializer,
    WikiAILabelSuggestionSerializer,
    WikiAISearchSerializer,
    WikiAISummarizeSerializer,
    WikiEventSerializer,
)
from plane.db.models import Page, Workspace
from plane.utils.page_access import can_view_page, resolve_workspace_role
from plane.utils.wiki_ai import (
    SCHEMA_VERSION,
    emit_wiki_event,
    iter_wiki_events,
    page_context,
    search_pages,
    suggest_labels,
    summarize_html,
)

from plane.bgtasks.page_transaction_task import page_transaction
from plane.bgtasks.page_version_task import track_page_version

from ..base import BaseViewSet

AI_DISABLED = {"error": "Wiki AI integration is disabled.", "error_code": "WIKI_AI_DISABLED"}


def _ai_enabled():
    from django.conf import settings

    return bool(getattr(settings, "WIKI_AI_ENABLED", True))


def _resolve_page(slug, page_id, *, include_archived=False):
    page = (
        Page.objects.filter(
            id=page_id,
            workspace__slug=slug,
            is_global=True,
            deleted_at__isnull=True,
        )
        .select_related("workspace")
        .first()
    )
    if page is None:
        return None
    if not include_archived and page.archived_at is not None:
        return None
    return page


class WorkspacePageAIEndpoint(BaseViewSet):
    """Page-scoped AI capabilities (context, summarize, apply, labels)."""

    model = Page
    serializer_class = WikiEventSerializer
    permission_classes = [WorkspacePagePermission]

    def ai_context(self, request, slug, page_id):
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        page = _resolve_page(slug, page_id, include_archived=True)
        if page is None or not can_view_page(request.user, page, page.workspace):
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
        envelope = page_context(page, request.user, page.workspace)
        if envelope is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(envelope, status=status.HTTP_200_OK)

    def ai_summarize(self, request, slug, page_id):
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        page = _resolve_page(slug, page_id, include_archived=True)
        if page is None or not can_view_page(request.user, page, page.workspace):
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = WikiAISummarizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        max_sentences = serializer.validated_data.get("max_sentences", 5)
        return Response(
            {
                "schema_version": SCHEMA_VERSION,
                "page_id": str(page.pk),
                "summary": summarize_html(page.description_html, max_sentences=max_sentences),
                "provider": "local",
            },
            status=status.HTTP_200_OK,
        )

    def ai_label_suggestions(self, request, slug, page_id):
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        page = _resolve_page(slug, page_id, include_archived=True)
        if page is None or not can_view_page(request.user, page, page.workspace):
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = WikiAILabelSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        suggestions = suggest_labels(
            page,
            page.workspace,
            limit=serializer.validated_data.get("limit"),
        )
        return Response(
            {"schema_version": SCHEMA_VERSION, "page_id": str(page.pk), "suggestions": suggestions},
            status=status.HTTP_200_OK,
        )

    def ai_apply(self, request, slug, page_id):
        """Apply an agent-proposed edit through the normal page write pipeline.

        The edit is versioned exactly like a user edit (``page_transaction`` +
        ``track_page_version``) and emits a ``page.ai_edit`` event, so an AI
        write is indistinguishable from any other Wiki mutation for audit and
        realtime purposes.
        """
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        page = _resolve_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        if page.is_locked:
            return Response(
                {"error": "Page is locked", "error_code": "PAGE_LOCKED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WikiAIApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_html = page.description_html
        existing_instance = json.dumps({"description_html": old_html}, cls=DjangoJSONEncoder)

        page.description_html = serializer.validated_data["description_html"]
        if "description_json" in serializer.validated_data:
            page.description_json = serializer.validated_data["description_json"]
        page.save()

        page_transaction.delay(
            new_description_html=page.description_html,
            old_description_html=old_html,
            page_id=str(page.pk),
        )
        track_page_version.delay(
            page_id=str(page.pk),
            existing_instance=existing_instance,
            user_id=request.user.id,
        )
        emit_wiki_event(
            page,
            "page.ai_edit",
            actor=request.user,
            payload={"source": "ai"},
        )

        return Response(
            {
                "schema_version": SCHEMA_VERSION,
                "page_id": str(page.pk),
                "context": page_context(page, request.user, page.workspace),
            },
            status=status.HTTP_200_OK,
        )


class WorkspaceWikiAISearchEndpoint(BaseViewSet):
    """Natural-language Wiki search for AI consumers (plan §13.1)."""

    model = Page
    serializer_class = WikiEventSerializer
    permission_classes = [WorkspacePagePermission]

    def ai_search(self, request, slug):
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = WikiAISearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = search_pages(
            request.user,
            workspace,
            serializer.validated_data["query"],
            limit=serializer.validated_data.get("limit"),
        )
        result["schema_version"] = SCHEMA_VERSION
        return Response(result, status=status.HTTP_200_OK)


class WorkspaceWikiAIEventsEndpoint(BaseViewSet):
    """Durable Wiki event feed for AI consumers (plan §13.1, spec §20)."""

    model = Page
    serializer_class = WikiEventSerializer
    permission_classes = [WorkspacePagePermission]

    def ai_events(self, request, slug):
        if not _ai_enabled():
            return Response(AI_DISABLED, status=status.HTTP_404_NOT_FOUND)
        workspace = Workspace.objects.filter(slug=slug, deleted_at__isnull=True).first()
        if workspace is None:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        since_raw = request.query_params.get("since")
        since = None
        if since_raw:
            since = parse_datetime(since_raw)
            if since is None:
                return Response(
                    {"error": "Invalid since timestamp", "error_code": "INVALID_SINCE"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        event_types = [value for value in request.query_params.getlist("event_type") if value]
        limit = request.query_params.get("limit")
        try:
            limit = int(limit) if limit else None
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid limit", "error_code": "INVALID_LIMIT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        events = iter_wiki_events(
            workspace,
            request.user,
            since=since,
            limit=limit,
            event_types=event_types or None,
        )
        return Response(
            {
                "schema_version": SCHEMA_VERSION,
                "events": WikiEventSerializer(events, many=True).data,
                "role": resolve_workspace_role(workspace.id, request.user.id),
            },
            status=status.HTTP_200_OK,
        )
