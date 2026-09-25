# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from html import escape
from typing import Any

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
                        "identifier": escape(item.get("identifier", "")),
                        "name": escape(item.get("name", "")),
                        "workspace": escape(item.get("workspace", {}).get("name", "")),
                        "project": escape(item.get("project", {}).get("name", "")),
                        "state": escape(item.get("state", {}).get("name", "")),
                        "priority": escape(item.get("priority", "")),
                        "target_date": escape(item.get("target_date") or ""),
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
        "recipient_name": escape(snapshot.get("recipient", {}).get("display_name", "")),
        "generated_at": escape(snapshot.get("generated_at", "")),
        "sections": sections,
        "preferences_url": _preferences_url(first_workspace_slug),
        "plane_url": (settings.APP_BASE_URL or settings.WEB_URL or "").rstrip("/"),
    }

    html_content = render_to_string("emails/digests/personal-daily.html", context)
    text_content = generate_plain_text_from_html(html_content)
    return subject, html_content, text_content
