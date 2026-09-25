# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import UUID

from plane.db.models import ProjectMember


def get_accessible_project_ids(user_id: UUID | str) -> set[UUID]:
    return set(
        ProjectMember.objects.filter(member_id=user_id, is_active=True).values_list("project_id", flat=True)
    )
