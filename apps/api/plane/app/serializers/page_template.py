# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Serializer for workspace-scoped page templates (spec §16; plan §10.1).

``workspace`` is read-only: the view always derives it from the URL workspace so
a caller can never create or read a template in another workspace (BOLA/IDOR
invariant, spec §6.2). ``description_html`` is write-only — templates are small
metadata surfaces, and the document body is copied server-side when a page is
created from the template.
"""

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import PageTemplate


class PageTemplateSerializer(BaseSerializer):
    description_html = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = PageTemplate
        fields = [
            "id",
            "workspace",
            "name",
            "description_html",
            "description_stripped",
            "logo_props",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["workspace", "description_stripped", "created_by", "updated_by"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Template name is required.")
        return value.strip()
