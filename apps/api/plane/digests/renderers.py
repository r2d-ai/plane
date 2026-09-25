# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from typing import Any, Iterable

from django.conf import settings
from django.template.loader import render_to_string

from plane.digests.constants import MAX_ITEMS_PER_SECTION, PERSONAL_DAILY_BUCKETS
from plane.utils.email import generate_plain_text_from_html

SECTION_LABELS = {
    "overdue": "Overdue",
    "due_today": "Due today",
    "blocked": "Blocked",
    "due_soon": "Due soon",
    "stale": "Stale in progress",
}

# Leader Morning Pulse uses a SEPARATE label set. It must NOT be merged
# with SECTION_LABELS — the keys differ (`unassigned_high_urgent` and
# `due_today_not_started` are not in personal daily) and `render_*`
# accepts (buckets, labels) as explicit parameters so the caller cannot
# accidentally pass a personal-daily (buckets, SECTION_LABELS) pair to
# the leader renderer. That call would KeyError on the missing labels
# and surface as an SMTP failure + a failed delivery row, which is
# noisy but correct: the bug is in the call site, not in the template.
LEADER_MORNING_SECTION_LABELS = {
    "overdue": "Overdue",
    "blocked": "Blocked",
    "unassigned_high_urgent": "Unassigned · high/urgent",
    "due_today_not_started": "Due today · not started",
    "stale": "Stale in progress",
}


def _preferences_url(workspace_slug: str | None) -> str:
    base_url = (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/")
    slug = workspace_slug or "settings"
    return f"{base_url}/{slug}/settings/account/notifications/"


def _subject_parts(counts: dict[str, int]) -> str:
    parts = []
    if counts.get("overdue"):
        parts.append(f"{counts['overdue']} overdue")
    if counts.get("due_today"):
        parts.append(f"{counts['due_today']} due today")
    if counts.get("blocked"):
        parts.append(f"{counts['blocked']} blocked")
    if counts.get("due_soon"):
        parts.append(f"{counts['due_soon']} due soon")
    if counts.get("stale"):
        parts.append(f"{counts['stale']} stale")
    return " · ".join(parts) if parts else "work items"


def render_personal_daily_email(snapshot: dict[str, Any]) -> tuple[str, str, str]:
    counts = snapshot.get("counts", {})
    subject_summary = _subject_parts(counts)
    subject = f"[Plane] Today's work — {subject_summary}"

    sections = []
    for bucket in PERSONAL_DAILY_BUCKETS:
        items = snapshot.get("sections", {}).get(bucket, [])
        if not items:
            continue
        visible_items = items[:MAX_ITEMS_PER_SECTION]
        overflow = max(len(items) - len(visible_items), 0)
        sections.append(
            {
                "key": bucket,
                "label": SECTION_LABELS[bucket],
                "items": [
                    {
                        "identifier": item.get("identifier", ""),
                        "name": item.get("name", ""),
                        "workspace": item.get("workspace", {}).get("name", ""),
                        "project": item.get("project", {}).get("name", ""),
                        "state": item.get("state", {}).get("name", ""),
                        "priority": item.get("priority", ""),
                        "target_date": item.get("target_date") or "",
                        "url": item.get("url", ""),
                    }
                    for item in visible_items
                ],
                "overflow": overflow,
            }
        )

    first_workspace_slug = None
    for bucket in PERSONAL_DAILY_BUCKETS:
        for item in snapshot.get("sections", {}).get(bucket, []):
            first_workspace_slug = item.get("workspace", {}).get("slug")
            if first_workspace_slug:
                break
        if first_workspace_slug:
            break

    context = {
        "recipient_name": snapshot.get("recipient", {}).get("display_name", ""),
        "generated_at": snapshot.get("generated_at", ""),
        "sections": sections,
        "preferences_url": _preferences_url(first_workspace_slug),
        "plane_url": (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/"),
    }

    html_content = render_to_string("emails/digests/personal-daily.html", context)
    text_content = generate_plain_text_from_html(html_content)
    return subject, html_content, text_content


def render_leader_morning_email(
    snapshot: dict[str, Any],
    buckets: Iterable[str],
    labels: dict[str, str],
) -> tuple[str, str, str]:
    """Render Leader Morning Pulse email.

    `buckets` and `labels` are passed in (NOT read from module-global)
    per RD-449 decision: this prevents the renderer from being called
    with a personal-daily snapshot (or vice versa) and silently
    mis-labelling. The caller is `deliver_leader_morning`, which uses
    `LEADER_MORNING_BUCKETS` + `LEADER_MORNING_SECTION_LABELS`.

    `buckets` is iterated in the order provided so the section order in
    the email matches the order the buckets were declared.
    """
    counts = snapshot.get("counts", {})
    total_exceptions = sum(
        counts.get(bucket, 0) for bucket in buckets
    )
    subject = (
        f"[Plane] Morning Pulse — {total_exceptions} điểm cần chú ý"
        if total_exceptions
        else "[Plane] Morning Pulse"
    )

    sections = []
    for bucket in buckets:
        items = snapshot.get("sections", {}).get(bucket, [])
        if not items:
            continue
        visible_items = items[:MAX_ITEMS_PER_SECTION]
        overflow = max(len(items) - len(visible_items), 0)
        sections.append(
            {
                "key": bucket,
                "label": labels[bucket],
                "items": [
                    {
                        "identifier": item.get("identifier", ""),
                        "name": item.get("name", ""),
                        "workspace": item.get("workspace", {}).get("name", ""),
                        "project": item.get("project", {}).get("name", ""),
                        "state": item.get("state", {}).get("name", ""),
                        "priority": item.get("priority", ""),
                        "target_date": item.get("target_date") or "",
                        "assignees": [
                            a.get("display_name", "")
                            for a in item.get("assignees", [])
                        ],
                        "url": item.get("url", ""),
                    }
                    for item in visible_items
                ],
                "overflow": overflow,
            }
        )

    # First-match workspace slug wins for the preferences link. Spec §22.1
    # points at /<workspace>/settings/account/notifications/. We use the
    # first non-empty slug from the rendered sections.
    first_workspace_slug = None
    for bucket in buckets:
        for item in snapshot.get("sections", {}).get(bucket, []):
            first_workspace_slug = item.get("workspace", {}).get("slug")
            if first_workspace_slug:
                break
        if first_workspace_slug:
            break

    context = {
        "recipient_name": snapshot.get("recipient", {}).get("display_name", ""),
        "generated_at": snapshot.get("generated_at", ""),
        "total_exceptions": total_exceptions,
        "projects_scanned_count": snapshot.get("projects_scanned_count", 0),
        "sections": sections,
        "preferences_url": _preferences_url(first_workspace_slug),
        "plane_url": (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/"),
    }

    html_content = render_to_string("emails/digests/leader-morning.html", context)
    text_content = generate_plain_text_from_html(html_content)
    return subject, html_content, text_content
