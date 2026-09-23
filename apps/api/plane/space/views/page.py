# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public retrieval of an externally published Wiki page (WIKI-07b, spec §15).

The endpoint is anonymous and serves exactly the page whose token was published.
It never walks the page hierarchy: descendants of a published page are *not*
published by association, and their content/assets are unreachable from this
token. Output is sanitized with the shared ``nh3`` allow-list before it leaves
the server.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plane.db.models import DeployBoard, Page
from plane.throttles.page_publish import PagePublishRateThrottle
from plane.utils.content_validator import validate_html_content

from .base import BaseAPIView


class PublishedPageEndpoint(BaseAPIView):
    """Anonymous read of a published Wiki page by its public anchor."""

    permission_classes = [AllowAny]
    throttle_classes = [PagePublishRateThrottle]

    def get(self, request, anchor):
        deploy_board = DeployBoard.objects.filter(
            anchor=anchor,
            entity_name="page",
            is_disabled=False,
            deleted_at__isnull=True,
        ).first()
        if deploy_board is None or deploy_board.entity_identifier is None:
            return Response(
                {"error": "Requested resource could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Scope strictly to the published page: same workspace, workspace Wiki
        # page, alive and not archived. No hierarchy traversal happens here.
        page = (
            Page.objects.filter(
                id=deploy_board.entity_identifier,
                workspace_id=deploy_board.workspace_id,
                is_global=True,
                deleted_at__isnull=True,
                archived_at__isnull=True,
            )
            .only("name", "description_html", "updated_at")
            .first()
        )
        if page is None:
            return Response(
                {"error": "Requested resource could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, _, clean_html = validate_html_content(page.description_html or "")

        return Response(
            {
                "anchor": deploy_board.anchor,
                "name": page.name,
                "description_html": clean_html or "",
                "updated_at": page.updated_at,
            },
            status=status.HTTP_200_OK,
        )
