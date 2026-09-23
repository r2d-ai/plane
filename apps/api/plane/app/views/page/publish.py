# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""External publishing of Workspace/Company Wiki pages (WIKI-07b, spec §15).

Publishing creates a public token for exactly one page. It reuses the existing
``DeployBoard`` publish primitive with ``entity_name="page"`` so the public
rendering surface (space app) and its asset pipeline keep a single anchor
concept. The public permission path is completely separate: this API only
manages the token and never exposes the page body, which is served sanitized by
``plane.space``.

Authorization is delegated to ``WorkspacePagePermission`` (MANAGE capability —
page owner or workspace admin). Every lookup is scoped by workspace +
``is_global=True`` + not-deleted so a page UUID cannot be published from another
workspace (BOLA/IDOR invariant, spec §6.2).
"""

from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkspacePagePermission
from plane.app.serializers import PagePublishSerializer
from plane.db.models import DeployBoard, Page
from plane.db.models.deploy_board import get_anchor

from ..base import BaseViewSet


class PagePublishViewSet(BaseViewSet):
    """Publish state, publish and revoke for one Workspace Wiki page."""

    model = DeployBoard
    permission_classes = [WorkspacePagePermission]
    serializer_class = PagePublishSerializer

    def _get_page(self, slug, page_id):
        return (
            Page.objects.filter(
                id=page_id,
                workspace__slug=slug,
                is_global=True,
                deleted_at__isnull=True,
            )
            .select_related("workspace")
            .first()
        )

    def _live_publish(self, page):
        """Publish row for the page, enabled or revoked (but not soft-deleted)."""
        return DeployBoard.objects.filter(
            entity_name="page",
            entity_identifier=page.id,
            workspace_id=page.workspace_id,
            deleted_at__isnull=True,
        ).first()

    def publish_state(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        publish = self._live_publish(page)
        if publish is None or publish.is_disabled:
            return Response({"page": str(page.id), "anchor": None}, status=status.HTTP_200_OK)
        return Response(PagePublishSerializer(publish).data, status=status.HTTP_200_OK)

    def publish(self, request, slug, page_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        publish = self._live_publish(page)
        if publish is None:
            publish = DeployBoard(
                entity_name="page",
                entity_identifier=page.id,
                workspace_id=page.workspace_id,
                is_disabled=False,
            )
            created = True
        else:
            created = False
            # Republishing after a revoke rotates the token so a previously
            # revoked public link can never come back to life.
            if publish.is_disabled:
                publish.anchor = get_anchor()
            publish.is_disabled = False
        publish.save()

        return Response(
            PagePublishSerializer(publish).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def publish_revoke(self, request, slug, page_id, publish_id):
        page = self._get_page(slug, page_id)
        if page is None:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)

        publish = DeployBoard.objects.filter(
            id=publish_id,
            entity_name="page",
            entity_identifier=page.id,
            workspace_id=page.workspace_id,
            deleted_at__isnull=True,
        ).first()
        if publish is None:
            return Response({"error": "Publish not found"}, status=status.HTTP_404_NOT_FOUND)

        publish.is_disabled = True
        publish.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
