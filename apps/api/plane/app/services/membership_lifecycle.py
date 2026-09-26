# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Centralized lifecycle operations for workspace / project membership.

RD-447 (Workspace member PATCH {is_active:false} does not cascade to
ProjectMember) and the related "PATCH project_lead" bug are two faces of
the same defect: the membership graph is updated through one path but
silently left in an inconsistent state through another. Before this
module, four code paths performed (or failed to perform) the same
``WorkspaceMember.is_active=False`` cascade:

1. ``WorkSpaceMemberViewSet.destroy``  -- cascade :+1:
2. ``WorkSpaceMemberViewSet.leave``     -- cascade :+1:
3. ``WorkSpaceMemberViewSet.partial_update`` with ``{"is_active": false}``
                                          -- NO cascade :x:
5. (RD-449) ``ProjectDetailAPIEndpoint.patch`` setting ``project_lead``
                                          without creating a ProjectMember

This module owns the row-level state changes inside ``transaction.atomic``
so each caller can call the same function and the three revoke paths
plus the lead-change path can no longer drift apart. Authorization
(``is_workspace_admin``, last-admin guard, self-removal guard, role
comparison) is intentionally NOT performed here -- callers must enforce
those before calling. Tests for those guards continue to live at the view
level.
"""

from __future__ import annotations

# Django imports
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.db.models import ProjectMember, WorkspaceMember


@transaction.atomic
def revoke_workspace_member(workspace_member: WorkspaceMember) -> None:
    """Deactivate ``workspace_member`` and cascade the same state to every
    active ``ProjectMember`` they hold inside the same workspace.

    Behavior mirrors ``WorkSpaceMemberViewSet.destroy`` and ``.leave`` --
    the two paths that were already correct before RD-447 -- so PATCH can
    no longer fall behind them. The serializer that drove the PATCH should
    have already updated ``workspace_member.is_active``; if it hasn't
    (e.g. this function is called by a future path that bypasses the
    serializer) we still flip the flag here so all three revoke entry
    points produce the same end state.

    Caller responsibilities (NOT performed here):

    * workspace-admin permission (role / is_workspace_admin)
    * last-admin guard ("user is the only admin in some project")
    * self-removal guard ("you cannot remove yourself")
    * "promote another user to admin" pre-flight

    Idempotency: a second call on an already-inactive member is a no-op
    for both the workspace and project rows (the ``is_active=True``
    filter on the cascade and the ``update_fields`` write converge to
    the same state).
    """
    now = timezone.now()

    ProjectMember.objects.filter(
        workspace_id=workspace_member.workspace_id,
        member_id=workspace_member.member_id,
        is_active=True,
    ).update(is_active=False, updated_at=now)

    if workspace_member.is_active:
        workspace_member.is_active = False
        workspace_member.save(update_fields=["is_active", "updated_at"])


@transaction.atomic
def ensure_project_lead_membership(
    project_id, new_lead_id, workspace_id
) -> None:
    """Make sure ``new_lead_id`` has an active ``ProjectMember`` row for
    ``project_id`` with role=20 (admin).

    Called from ``ProjectDetailAPIEndpoint.patch`` when ``project_lead``
    transitions to a new user. The previous PATCH path set
    ``project.project_lead_id`` without ever creating the corresponding
    ``ProjectMember`` -- so the lead had ``project.project_lead ==
    <self>`` but was invisible to every membership-based permission
    gate (Leader Morning Pulse digest, project archive, etc.).

    Idempotent across four cases:

    * no active row -> create with ``role=20, is_active=True``
    * active row already at ``role=20`` -> no-op
    * inactive row (revoked, then re-promoted) -> reactivate at role=20
    * active row at a lower role (e.g. guest promoted to lead) -> bump
      role to 20 without changing is_active

    A ``None`` ``new_lead_id`` is treated as "no change" so callers can
    pass ``project.project_lead_id`` unconditionally without a None check.
    """
    if new_lead_id is None:
        return

    # Re-fetch inside the atomic block so we read the latest row state --
    # the caller may have written elsewhere in this transaction.
    pm = (
        ProjectMember.objects.select_for_update()
        .filter(project_id=project_id, member_id=new_lead_id)
        .first()
    )

    if pm is None:
        ProjectMember.objects.create(
            project_id=project_id,
            member_id=new_lead_id,
            workspace_id=workspace_id,
            role=20,
            is_active=True,
        )
        return

    needs_update = False
    update_fields: list[str] = []
    if not pm.is_active:
        pm.is_active = True
        needs_update = True
        update_fields.append("is_active")
    if pm.role != 20:
        pm.role = 20
        needs_update = True
        update_fields.append("role")
    if needs_update:
        update_fields.append("updated_at")
        pm.save(update_fields=update_fields)