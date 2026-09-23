# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializers for Wiki page/collection analytics (WIKI-09b, plan §12.3)."""

from rest_framework import serializers

from .base import BaseSerializer
from plane.db.models import PageView


class PageViewRecordSerializer(serializers.Serializer):
    """Input for the view-recording endpoint.

    ``preload`` marks a background/prefetch read: the view short-circuits and no
    row is written, so preloads never inflate a page's view count. The timestamp
    is always server-side, so a client cannot backdate or forge a view.
    """

    preload = serializers.BooleanField(required=False, default=False)


class PageViewSerializer(BaseSerializer):
    """Output for analytics rows / CSV export."""

    viewer_detail = serializers.SerializerMethodField()

    class Meta:
        model = PageView
        fields = [
            "id",
            "page",
            "collection",
            "viewer",
            "viewer_detail",
            "viewed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_viewer_detail(self, obj):
        viewer = obj.viewer
        if viewer is None:
            return None
        return {
            "id": str(viewer.id),
            "email": viewer.email,
            "display_name": viewer.display_name,
            "avatar_url": viewer.avatar_url,
        }
