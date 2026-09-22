# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace Wiki page version history (WIKI-01).

Every lookup is scoped by the URL workspace, the page and ``is_global=True`` so
a version belonging to a project page (or another workspace) can never be read
through this endpoint (spec §6.2).
"""

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkspacePagePermission
from plane.app.serializers import PageVersionDetailSerializer, PageVersionSerializer
from plane.db.models import PageVersion

from ..base import BaseAPIView


class WorkspacePageVersionEndpoint(BaseAPIView):
    permission_classes = [WorkspacePagePermission]

    def get(self, request, slug, page_id, pk=None):
        base = PageVersion.objects.filter(
            workspace__slug=slug,
            page_id=page_id,
            page__is_global=True,
            page__deleted_at__isnull=True,
        )

        if pk:
            page_version = base.filter(pk=pk).distinct().first()
            if page_version is None:
                return Response({"error": "Page version not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(PageVersionDetailSerializer(page_version).data, status=status.HTTP_200_OK)

        serializer = PageVersionSerializer(base, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
