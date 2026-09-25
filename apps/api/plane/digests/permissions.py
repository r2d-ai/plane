# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import UUID

from plane.db.models import ProjectMember


def get_accessible_project_ids(user_id: UUID | str) -> set[UUID]:
    """Return the set of project ids the user can still receive digest items for.

    Defense-in-depth: require both an active ``ProjectMember`` row AND an
    active ``WorkspaceMember`` row in the same workspace. The PATCH path on
    ``WorkSpaceMemberSerializer`` (``app/views/workspace/member.py:76``)
    deactivates ``WorkspaceMember.is_active`` without cascading to
    ``ProjectMember`` — only the ``destroy`` and ``leave`` actions cascade.
    Without the workspace-level check, a user revoked via PATCH would
    still receive issue metadata (identifier, title, workspace/project/
    state, priority, target date, direct URL) in their Personal Daily
    digest. The in-app API can revoke those reads later, but the email
    has already been delivered.
    """
    return set(
        ProjectMember.objects.filter(
            member_id=user_id,
            is_active=True,
            project__workspace__workspace_member__member_id=user_id,
            project__workspace__workspace_member__is_active=True,
            project__workspace__workspace_member__deleted_at__isnull=True,
        ).values_list("project_id", flat=True)
    )
