# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializer for public Wiki page publishing (WIKI-07b, spec §15, plan §10.2).

A published page is stored as a ``DeployBoard`` row with ``entity_name="page"``
and ``entity_identifier=<page_id>``: the existing publish primitive whose
``anchor`` is the public token. This serializer intentionally exposes only the
publish identity — never the page body, which is served sanitized by the public
endpoint in the space app.
"""

from rest_framework import serializers

# Module imports
from plane.db.models import DeployBoard

from .base import BaseSerializer


class PagePublishSerializer(BaseSerializer):
    """Publish state of a Wiki page (internal, authenticated API)."""

    page = serializers.UUIDField(source="entity_identifier", read_only=True)

    class Meta:
        model = DeployBoard
        fields = [
            "id",
            "workspace",
            "page",
            "anchor",
            "is_disabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "page",
            "anchor",
            "is_disabled",
            "created_at",
            "updated_at",
        ]
