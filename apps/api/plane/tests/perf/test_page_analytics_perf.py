# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-09b: measured performance suite for the page/collection analytics paths.

Opt-in unless ``WIKI_PERF=1``. It materialises a realistic ``page_views``
dataset, captures ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` for the aggregate
SQL the analytics endpoints run, then A/Bs the shipped indexes by dropping them
and measuring again, and finally evaluates a candidate workspace index. Every
index shipped in ``0128_page_analytics_and_comment_moderation`` must be
justified by a plan below.

Run inside the repository-supported test stack:

    WIKI_PERF=1 WIKI_PERF_REPORT=/code/wiki-analytics-perf-report.md \\
        docker compose -f docker-compose-test.yml run --rm api-tests \\
        pytest plane/tests/perf/test_page_analytics_perf.py --create-db

Plan §12.3, spec §21.

V3 workspace dashboard batch latency (RD-480): ``test_batch_12_card_dashboard``
(set ``DASHBOARD_V3_PERF=1``).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime

import pytz

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from django.db import connection
from django.utils import timezone

from plane.db.models import Page, PageCollection, PageCollectionPage, PageView, User, Workspace, WorkspaceMember
from plane.tests.fixtures.v3_dashboard_batch import build_v3_dashboard_batch_payload
from plane.tests.perf.dashboard_v3_fixtures import build_v3_perf_workspace

SHIPPED_INDEXES = [
    (
        "page_view_page_viewed_idx",
        'CREATE INDEX IF NOT EXISTS "page_view_page_viewed_idx" ON "page_views" ("page_id", "viewed_at")',
    ),
    (
        "page_view_coll_viewed_idx",
        'CREATE INDEX IF NOT EXISTS "page_view_coll_viewed_idx" ON "page_views" ("collection_id", "viewed_at")',
    ),
]

CANDIDATE_INDEX = (
    "page_view_ws_viewed_idx",
    'CREATE INDEX "page_view_ws_viewed_idx" ON "page_views" ("workspace_id", "viewed_at")',
)

PAGE_COUNT = 200
COLLECTION_COUNT = 50
PAGES_PER_COLLECTION = PAGE_COUNT // COLLECTION_COUNT
VIEWS_PER_PAGE = 3000  # 600k rows
SPAN_DAYS = 30
WINDOW_DAYS = 1


pytestmark = [
    pytest.mark.slow,
    pytest.mark.django_db(transaction=True),
]


def _explain(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}", params)
        plan = cursor.fetchone()[0]
    return plan[0] if isinstance(plan, list) else plan


def _summarize(plan):
    root = plan["Plan"]

    def walk(node):
        yield node
        for child in node.get("Plans", []):
            yield from walk(child)

    nodes = list(walk(root))
    return {
        "exec_ms": round(plan.get("Execution Time") or 0.0, 2),
        "planning_ms": round(plan.get("Planning Time") or 0.0, 2),
        "rows": root.get("Actual Rows"),
        "indexes": sorted({node.get("Index Name") for node in nodes if node.get("Index Name")}),
        "seq_scans": sorted(
            {
                node.get("Relation Name")
                for node in nodes
                if node.get("Node Type") == "Seq Scan" and node.get("Relation Name")
            }
        ),
    }


def _measure(label, sql, params):
    return {"label": label, "sql": sql.strip(), **(_summarize(_explain(sql, params)))}


def _build_dataset():
    owner = User.objects.create(email="analytics-perf@plane.so", username="analytics-perf", first_name="Perf")
    workspace = Workspace.objects.create(name="Analytics Perf", slug="analytics-perf", owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20)
    collections = [
        PageCollection(workspace_id=workspace.id, name=f"Handbook {index:02d}")
        for index in range(COLLECTION_COUNT)
    ]
    PageCollection.objects.bulk_create(collections, batch_size=500)

    pages = Page.objects.bulk_create(
        [
            Page(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                owned_by_id=owner.id,
                created_by_id=owner.id,
                name=f"Perf page {index:04d}",
                access=Page.PUBLIC_ACCESS,
                is_global=True,
                description_html="<p>perf</p>",
            )
            for index in range(PAGE_COUNT)
        ],
        batch_size=500,
    )
    # Each page belongs to exactly one Collection (spec §5.5: one page, one
    # Collection), so a Collection roll-up is selective.
    page_collection = {
        page.id: collections[index // PAGES_PER_COLLECTION].id for index, page in enumerate(pages)
    }
    PageCollectionPage.objects.bulk_create(
        [
            PageCollectionPage(
                workspace_id=workspace.id,
                collection_id=page_collection[page.id],
                page=page,
            )
            for page in pages
        ],
        batch_size=500,
    )

    now = timezone.now()
    step_seconds = (SPAN_DAYS * 86400) // VIEWS_PER_PAGE
    rows = []
    for page in pages:
        for offset in range(VIEWS_PER_PAGE):
            rows.append(
                PageView(
                    workspace_id=workspace.id,
                    page_id=page.id,
                    collection_id=page_collection[page.id],
                    viewer_id=owner.id,
                    viewed_at=now - timezone.timedelta(seconds=offset * step_seconds),
                )
            )
    PageView.objects.bulk_create(rows, batch_size=5000)
    _analyze()
    return workspace, collections[0], pages[0]


def _analyze():
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE page_views")


def _create_indexes(indexes):
    with connection.cursor() as cursor:
        for _, ddl in indexes:
            cursor.execute(ddl)
    _analyze()


def _drop_indexes(indexes):
    with connection.cursor() as cursor:
        for name, _ in indexes:
            cursor.execute(f"DROP INDEX IF EXISTS {name}")
    _analyze()


def _queries(workspace, collection, page):
    start = timezone.now() - timezone.timedelta(days=WINDOW_DAYS)
    return [
        (
            "page timeline (page_id + viewed_at range, GROUP BY day)",
            'SELECT DATE(viewed_at) AS day, COUNT(id) FROM "page_views" '
            'WHERE "page_views"."page_id" = %s AND "page_views"."workspace_id" = %s '
            'AND "page_views"."viewed_at" >= %s GROUP BY 1 ORDER BY 1',
            [str(page.id), str(workspace.id), start],
        ),
        (
            "page totals (page_id + viewed_at range aggregate)",
            'SELECT COUNT(id), COUNT(DISTINCT viewer_id), MIN(viewed_at), MAX(viewed_at) FROM "page_views" '
            'WHERE "page_views"."page_id" = %s AND "page_views"."workspace_id" = %s '
            'AND "page_views"."viewed_at" >= %s',
            [str(page.id), str(workspace.id), start],
        ),
        (
            "collection roll-up (collection_id + viewed_at range)",
            'SELECT COUNT(id), COUNT(DISTINCT viewer_id) FROM "page_views" '
            'WHERE "page_views"."collection_id" = %s AND "page_views"."workspace_id" = %s '
            'AND "page_views"."viewed_at" >= %s',
            [str(collection.id), str(workspace.id), start],
        ),
        (
            "workspace-wide export (workspace_id + viewed_at range, ordered)",
            'SELECT id FROM "page_views" WHERE "page_views"."workspace_id" = %s '
            'AND "page_views"."viewed_at" >= %s ORDER BY "page_views"."viewed_at"',
            [str(workspace.id), start],
        ),
    ]


def _render_report(indexed, baseline, candidate, rows):
    decisions = {
        "page timeline (page_id + viewed_at range, GROUP BY day)": "keep `page_view_page_viewed_idx`",
        "page totals (page_id + viewed_at range aggregate)": "covered by `page_view_page_viewed_idx`",
        "collection roll-up (collection_id + viewed_at range)": "keep `page_view_coll_viewed_idx`",
        "workspace-wide export (workspace_id + viewed_at range, ordered)": (
            "no endpoint issues this query — `page_view_ws_viewed_idx` rejected"
        ),
    }
    lines = [
        "# WIKI-09b — page/collection analytics measured indexes",
        "",
        "Generated by `apps/api/plane/tests/perf/test_page_analytics_perf.py` inside the "
        "`docker-compose-test.yml` stack (PostgreSQL 15.7, `ANALYZE` after load). Plans are "
        "`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; execution ms is the plan's `Execution Time`.",
        "",
        f"Dataset: {rows:,} `page_views` across {PAGE_COUNT} pages over {SPAN_DAYS} days; "
        f"{COLLECTION_COUNT} Collections of {PAGES_PER_COLLECTION} pages each. Query window: last {WINDOW_DAYS} day.",
        "",
        "| path | shipped ms | index chosen | no-index ms | candidate ws ms | decision |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, base, cand in zip(indexed, baseline, candidate):
        lines.append(
            "| {label} | {im} | {idx} | {bm} | {cm} | {decision} |".format(
                label=index["label"],
                im=index["exec_ms"],
                idx=", ".join(index["indexes"]) or "—",
                bm=base["exec_ms"],
                cm=cand["exec_ms"],
                decision=decisions.get(index["label"], ""),
            )
        )
    lines.append("")
    lines.append("## Captured plans (shipped indexes present)")
    lines.append("")
    for index in indexed:
        lines.append(f"### {index['label']}")
        lines.append("")
        lines.append(
            f"- indexes: `{index['indexes'] or '—'}`, seq scans: `{index['seq_scans'] or '—'}`, "
            f"exec: `{index['exec_ms']} ms`"
        )
        lines.append("")
        lines.append("```sql")
        lines.append(index["sql"])
        lines.append("```")
        lines.append("")
    lines.append("## No-index baseline plans")
    lines.append("")
    for base in baseline:
        lines.append(
            f"- {base['label']}: indexes `{base['indexes'] or '—'}`, "
            f"seq scans `{base['seq_scans'] or '—'}`, exec `{base['exec_ms']} ms`"
        )
    lines.append("")
    return "\n".join(lines)


@pytest.mark.skipif(
    not os.environ.get("WIKI_PERF"),
    reason="opt-in WIKI-09b analytics performance suite (set WIKI_PERF=1)",
)
def test_page_analytics_perf_report():
    workspace, collection, page = _build_dataset()

    _create_indexes(SHIPPED_INDEXES)
    indexed = [_measure(label, sql, params) for label, sql, params in _queries(workspace, collection, page)]

    _drop_indexes(SHIPPED_INDEXES)
    baseline = [_measure(label, sql, params) for label, sql, params in _queries(workspace, collection, page)]

    _create_indexes([CANDIDATE_INDEX])
    candidate = [_measure(label, sql, params) for label, sql, params in _queries(workspace, collection, page)]
    _drop_indexes([CANDIDATE_INDEX])

    _create_indexes(SHIPPED_INDEXES)

    rows = PageView.objects.count()
    report = _render_report(indexed, baseline, candidate, rows)
    report_path = os.environ.get("WIKI_PERF_REPORT")
    if report_path:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(report)
    else:
        print(report)

    # Evidence, not a gate: but the dataset must have been materialised.
    assert rows >= PAGE_COUNT * VIEWS_PER_PAGE


V3_BATCH_BUDGETS_MS = {
    "small": {"p50": 200.0, "p95": 400.0, "p99": 800.0},
    "medium": {"p50": 600.0, "p95": 1200.0, "p99": 2000.0},
    "large": {"p50": 2000.0, "p95": 4000.0, "p99": 6000.0},
}

V3_PERF_ITERATIONS = 21
FROZEN_V3_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=pytz.UTC)


def _percentile_ms(samples, percentile):
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _batch_url(slug):
    return f"/api/workspaces/{slug}/analytics/v2/batch/"


def _measure_v3_batch(client, slug, iterations=V3_PERF_ITERATIONS):
    payload = build_v3_dashboard_batch_payload()
    url = _batch_url(slug)
    timings = []
    with freeze_time(FROZEN_V3_NOW):
        for _ in range(2):
            client.post(url, payload, format="json")
        for _ in range(iterations):
            started = time.perf_counter()
            response = client.post(url, payload, format="json")
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            assert response.status_code == 200, response.data
            timings.append(elapsed_ms)
    return {
        "iterations": iterations,
        "p50_ms": round(_percentile_ms(timings, 50), 2),
        "p95_ms": round(_percentile_ms(timings, 95), 2),
        "p99_ms": round(_percentile_ms(timings, 99), 2),
        "samples_ms": [round(value, 2) for value in timings],
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("profile", ["small", "medium", "large"])
@pytest.mark.skipif(
    not os.environ.get("DASHBOARD_V3_PERF"),
    reason="opt-in v3 dashboard batch perf (set DASHBOARD_V3_PERF=1)",
)
def test_batch_12_card_dashboard(profile):
    workspace, owner, meta = build_v3_perf_workspace(profile)
    client = APIClient()
    client.force_authenticate(user=owner)
    measured = _measure_v3_batch(client, workspace.slug)
    budgets = V3_BATCH_BUDGETS_MS[profile]

    report = {
        "profile": profile,
        "workspace_slug": workspace.slug,
        "projects": meta["spec"]["projects"],
        "issues_per_project": meta["spec"]["issues_per_project"],
        "budgets_ms": budgets,
        "measured": measured,
        "within_budget": {
            "p50": measured["p50_ms"] <= budgets["p50"],
            "p95": measured["p95_ms"] <= budgets["p95"],
            "p99": measured["p99_ms"] <= budgets["p99"],
        },
        "recorded_at": timezone.now().isoformat(),
    }
    assert measured["iterations"] >= 10
    baseline_path = os.environ.get("DASHBOARD_V3_PERF_BASELINE")
    if baseline_path:
        with open(baseline_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    else:
        print(json.dumps(report, indent=2))
