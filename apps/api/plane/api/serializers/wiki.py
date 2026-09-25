# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .base import BaseSerializer
from plane.db.models import Page


class WikiPageAPISerializer(BaseSerializer):
    """Read model for Workspace/Company Wiki pages exposed to API principals."""

    class Meta:
        model = Page
        fields = (
            "id",
            "name",
            "description_html",
            "description_stripped",
            "access",
            "parent",
            "owned_by",
            "archived_at",
            "is_locked",
            "sort_order",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
