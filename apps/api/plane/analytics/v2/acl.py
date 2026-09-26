# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""ACL-safe base queryset for Analytics V2 (spec §37).

The single entry point every analytics source must funnel through. Returns a
``QuerySet`` of :class:`plane.db.models.Issue` already restricted to the projects
the principal can see, with archived / draft / triage rows excluded. The
returned queryset never references a project the principal cannot access.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union
from uuid import UUID

from django.db.models import Q, QuerySet

from plane.db.models import Issue, Project, ProjectMember, ProjectNetwork, WorkspaceMember


def _to_uuid_list(value: Union[None, str, Iterable[str], Iterable[UUID]]) -> List[str]:
    """Coerce a user-supplied project-id list into a clean ``[str, ...]``."""
    if value is None:
        return []
    if isinstance(value, str):
        # Accept both single UUID and a comma-separated list. Either way, strip blanks.
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v) for v in value if v]


def visible_project_ids(
    *,
    workspace,
    principal,
    project_ids: Union[None, str, Sequence[Union[str, UUID]]] = None,
) -> List[str]:
    """Return the principal's accessible project IDs, optionally intersected with
    ``project_ids``.

    The result is order-stable and contains no project that the principal cannot
    read. The returned list is a plain ``[str, ...]`` so it composes with Django
    queryset ``id__in`` filters and is JSON-serialisable for response metadata.
    """
    qs = Project.objects.filter(
        workspace_id=workspace.id,
        deleted_at__isnull=True,
        archived_at__isnull=True,
    )

    requested = _to_uuid_list(project_ids)
    if requested:
        qs = qs.filter(id__in=requested)

    qs = qs.filter(
        Q(network=ProjectNetwork.PUBLIC.value)  # public projects are visible to all workspace members
        | Q(
            id__in=ProjectMember.objects.filter(
                member_id=getattr(principal, "id", principal),
                is_active=True,
            ).values_list("project_id", flat=True)
        )
    )

    # Also require an active workspace membership — same defense-in-depth as
    # plane.digests.permissions.get_accessible_project_ids. Service principals
    # (is_bot / no WorkspaceMember row) get only public projects.
    if getattr(principal, "is_bot", False):
        return list(qs.filter(network=ProjectNetwork.PUBLIC.value).values_list("id", flat=True))

    if not WorkspaceMember.objects.filter(
        member_id=getattr(principal, "id", principal),
        workspace_id=workspace.id,
        is_active=True,
        deleted_at__isnull=True,
    ).exists():
        return []

    return [str(pid) for pid in qs.values_list("id", flat=True)]


def base_issue_queryset(
    *,
    workspace,
    principal,
    project_ids: Union[None, str, Sequence[Union[str, UUID]]] = None,
) -> QuerySet:
    """Return the canonical ACL-safe issue queryset for Analytics V2.

    The queryset:

    * belongs to ``workspace``;
    * is restricted to the principal's visible projects, intersected with the
      caller-supplied ``project_ids`` if any;
    * excludes archived projects, drafts and triage state.
    """
    visible = visible_project_ids(
        workspace=workspace, principal=principal, project_ids=project_ids
    )
    if not visible:
        return Issue.objects.none()

    return (
        Issue.issue_objects.filter(
            workspace_id=workspace.id,
            project_id__in=visible,
        )
        .filter(
            project__deleted_at__isnull=True,
            project__archived_at__isnull=True,
        )
    )