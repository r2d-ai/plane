# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Dataset builders for v3 dashboard batch perf (``04-perf-plan.md``)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Tuple

from django.utils import timezone

from plane.db.models import Issue, Project, ProjectMember, ProjectNetwork, State, User, Workspace, WorkspaceMember

WORKSPACE_PROFILES = {
    "small": {"projects": 5, "issues_per_project": 200},
    "medium": {"projects": 25, "issues_per_project": 2000},
    "large": {"projects": 100, "issues_per_project": 5000},
}


def build_v3_perf_workspace(profile: str) -> Tuple[Workspace, User, Dict[str, Any]]:
    if profile not in WORKSPACE_PROFILES:
        raise ValueError(f"Unknown profile {profile!r}")
    spec = WORKSPACE_PROFILES[profile]
    owner = User.objects.create(
        email=f"v3-perf-{profile}-{uuid.uuid4().hex[:8]}@plane.so",
        username=f"v3-perf-{profile}-{uuid.uuid4().hex[:8]}",
        first_name="Perf",
    )
    owner.set_password("pw")
    owner.save()
    workspace = Workspace.objects.create(
        name=f"V3 perf {profile}",
        slug=f"v3-perf-{profile}-{uuid.uuid4().hex[:8]}",
        owner=owner,
        timezone="UTC",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)

    projects = []
    for index in range(spec["projects"]):
        project = Project.objects.create(
            workspace=workspace,
            name=f"Project {index:03d}",
            identifier=f"P{index:03d}"[:5],
            created_by=owner,
            updated_by=owner,
            network=ProjectNetwork.PUBLIC.value,
        )
        ProjectMember.objects.create(project=project, member=owner, role=20, is_active=True)
        state = State.objects.create(
            project=project,
            name="In progress",
            color="#336699",
            group="started",
        )
        projects.append((project, state))

    issue_rows = []
    for project, state in projects:
        for seq in range(spec["issues_per_project"]):
            issue_rows.append(
                Issue(
                    project=project,
                    workspace=workspace,
                    name=f"{project.identifier}-{seq}",
                    state=state,
                    priority="medium" if seq % 5 else "urgent",
                    created_by=owner,
                )
            )
            if len(issue_rows) >= 5000:
                Issue.objects.bulk_create(issue_rows, batch_size=5000)
                issue_rows = []
    if issue_rows:
        Issue.objects.bulk_create(issue_rows, batch_size=5000)

    return workspace, owner, {"projects": projects, "profile": profile, "spec": spec}
