# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""WIKI-04b: measured performance suite for the Workspace / Company Wiki paths.

This module is opt-in — it is skipped unless ``WIKI_PERF=1`` is set — because it
materialises 1k/5k/deep/wide datasets and captures ``EXPLAIN (ANALYZE)`` plans.
It is the evidence behind the index migration: every index shipped in
``0123_page_wiki_access_indexes`` must be justified by a plan below.

Run inside the repository-supported test stack:

    WIKI_PERF=1 WIKI_PERF_REPORT=/code/wiki-perf-report.md \\
        docker compose -f docker-compose-test.yml run --rm api-tests \\
        pytest plane/tests/perf/test_wiki_perf.py --create-db

Spec: ``docs/wiki-ce-spec.md`` §7.8. Plan: ``docs/wiki-ce-implementation-plan.md``
§7.8 and §16.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import Page, User, Workspace, WorkspaceMember

from . import wiki_fixtures as fx


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("WIKI_PERF"),
        reason="opt-in WIKI-04b performance suite (set WIKI_PERF=1)",
    ),
]


# ---------------------------------------------------------------------------
# dataset construction
# ---------------------------------------------------------------------------


def _make_user(email):
    return User.objects.create(
        email=email,
        username=email.split("@")[0],
        first_name="Perf",
        last_name="User",
    )


def _make_workspace(name, slug, owner, role):
    workspace = Workspace.objects.create(name=name, slug=slug, owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=role)
    return workspace


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _pages_url(slug):
    return f"/api/workspaces/{slug}/pages/"


def _page_url(slug, page_id):
    return f"/api/workspaces/{slug}/pages/{page_id}/"


# ---------------------------------------------------------------------------
# query capture + plans
# ---------------------------------------------------------------------------


class QueryCapture:
    """Capture ``(sql, params)`` for every statement a request executes."""

    def __init__(self):
        self.queries = []

    def __enter__(self):
        self._wrapper = connection.execute_wrapper(self._record)
        self._wrapper.__enter__()
        return self

    def __exit__(self, *exc):
        return self._wrapper.__exit__(*exc)

    def _record(self, execute, sql, params, many, context):
        self.queries.append((sql, params))
        return execute(sql, params, many, context)

    def pages_selects(self):
        """Only SELECTs that read the ``pages`` table are plan-relevant here."""
        import re

        pattern = re.compile(r'from\s+"pages"|join\s+"pages"', re.IGNORECASE)
        return [
            (sql, params)
            for sql, params in self.queries
            if sql.lstrip().upper().startswith(("SELECT", "WITH")) and pattern.search(sql)
        ]


def _explain(sql, params):
    """Return the ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` plan for a query."""
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}", params)
        plan = cursor.fetchone()[0]
    return plan[0] if isinstance(plan, list) else plan


def _plan_summary(plan):
    """Flatten a JSON plan into the facts the report needs."""
    root = plan["Plan"]

    def walk(node, depth=0):
        yield depth, node
        for child in node.get("Plans", []):
            yield from walk(child, depth + 1)

    flat = list(walk(root))
    nodes = [node for _, node in flat]
    seq_scans = [node for node in nodes if node.get("Node Type") == "Seq Scan"]

    def is_pages_seq(node):
        return node.get("Relation Name") == "pages"

    tree_lines = []
    for depth, node in flat:
        target = node.get("Index Name") or node.get("Relation Name") or ""
        tree_lines.append(
            "{indent}{node_type}{target}  (rows={rows}, cost={cost:.1f}, time={time:.2f}ms)".format(
                indent="  " * depth,
                node_type=node.get("Node Type"),
                target=f" [{target}]" if target else "",
                rows=node.get("Actual Rows"),
                cost=node.get("Total Cost") or 0.0,
                time=node.get("Actual Total Time") or 0.0,
            )
        )

    return {
        "top_node": root.get("Node Type"),
        "seq_scan_pages": any(is_pages_seq(node) for node in seq_scans),
        "seq_scan_relations": sorted({node.get("Relation Name") for node in seq_scans if node.get("Relation Name")}),
        "index_names": sorted({node.get("Index Name") for node in nodes if node.get("Index Name")}),
        "planning_ms": plan.get("Planning Time"),
        "execution_ms": plan.get("Execution Time"),
        "total_cost": root.get("Total Cost"),
        "rows": root.get("Actual Rows"),
        "tree": tree_lines,
    }


def _measure(label, client, url, share, *, repeat=1):
    """Run one API path, time it and capture the plan of every pages SELECT."""
    capture = QueryCapture()
    started = time.perf_counter()
    with capture:
        status = None
        for _ in range(repeat):
            status = client.get(url).status_code
    wall_ms = (time.perf_counter() - started) * 1000.0

    plans = []
    for sql, params in capture.pages_selects():
        summary = _plan_summary(_explain(sql, params))
        plans.append({"sql": sql, "params": params, **summary})

    result = {
        "label": label,
        "url": url,
        "status": status,
        "wall_ms": wall_ms,
        "query_count": len(capture.queries),
        "plans": plans,
    }
    share.append(result)
    return result


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _render_report(datasets):
    lines = []
    lines.append("# WIKI-04b — Wiki performance measurement")
    lines.append("")
    lines.append(
        "Generated by `apps/api/plane/tests/perf/test_wiki_perf.py` inside the "
        "`docker-compose-test.yml` stack (PostgreSQL 15.7, `ANALYZE` after load). "
        "Plans are `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. Times are wall-clock "
        "for the whole HTTP round-trip, single run."
    )
    lines.append("")

    for dataset in datasets:
        lines.append(f"## {dataset['name']}")
        lines.append("")
        lines.append("| path | status | wall ms | queries | pages seq scan | index used | exec ms (plan) |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in dataset["measurements"]:
            for plan in row["plans"] or [{"seq_scan_pages": None, "index_names": [], "execution_ms": None}]:
                lines.append(
                    "| {label} | {status} | {wall:.1f} | {queries} | {seq} | {idx} | {exec_ms} |".format(
                        label=row["label"],
                        status=row["status"],
                        wall=row["wall_ms"],
                        queries=row["query_count"],
                        seq="yes" if plan["seq_scan_pages"] else ("no" if plan["seq_scan_pages"] is False else "n/a"),
                        idx=", ".join(plan["index_names"]) or "—",
                        exec_ms=round(plan["execution_ms"], 2) if plan["execution_ms"] is not None else "n/a",
                    )
                )
        lines.append("")

        lines.append("### Captured plans")
        lines.append("")
        for row in dataset["measurements"]:
            lines.append(f"#### {row['label']} — `{row['url']}`")
            lines.append("")
            for plan in row["plans"]:
                lines.append(
                    f"- top node `{plan['top_node']}`, pages seq scan: "
                    f"`{plan['seq_scan_pages']}`, relations seq-scanned: "
                    f"`{plan['seq_scan_relations']}`, indexes: "
                    f"`{plan['index_names'] or '—'}`, exec: `{plan['execution_ms']} ms`, "
                    f"rows: `{plan['rows']}`"
                )
                lines.append("")
                lines.append("```")
                lines.extend(plan.get("tree", []))
                lines.append("```")
                lines.append("")
                lines.append("```sql")
                lines.append(plan["sql"].strip())
                lines.append("```")
                lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the measurement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_wiki_perf_report():
    owner = _make_user("perf-owner@plane.so")
    other = _make_user("perf-other@plane.so")
    admin_role = 20

    datasets = []

    # ---- 1,000 flat pages -------------------------------------------------
    ws_1k = _make_workspace("Perf 1k", "perf-1k", owner, admin_role)
    WorkspaceMember.objects.create(workspace=ws_1k, member=other, role=15)
    ids_1k = fx.build_flat(ws_1k, owner, 1000, prefix="Perf 1k")
    fx.build_favorites(ws_1k, owner, ids_1k[:50])
    # Model the real shared `pages` table: project pages coexist with Wiki pages.
    fx.build_project_scope_noise(ws_1k, owner, 4000)

    # ---- 5,000 flat pages -------------------------------------------------
    ws_5k = _make_workspace("Perf 5k", "perf-5k", owner, admin_role)
    WorkspaceMember.objects.create(workspace=ws_5k, member=other, role=15)
    ids_5k = fx.build_flat(ws_5k, owner, 5000, prefix="Perf 5k")
    fx.build_favorites(ws_5k, owner, ids_5k[:200])
    fx.build_project_scope_noise(ws_5k, owner, 20000)

    # ---- deep hierarchy (depth 200) --------------------------------------
    ws_deep = _make_workspace("Perf deep", "perf-deep", owner, admin_role)
    WorkspaceMember.objects.create(workspace=ws_deep, member=other, role=15)
    deep = fx.build_deep(ws_deep, owner, 200)

    # ---- wide hierarchy (1 root + 2,000 children) ------------------------
    ws_wide = _make_workspace("Perf wide", "perf-wide", owner, admin_role)
    WorkspaceMember.objects.create(workspace=ws_wide, member=other, role=15)
    wide = fx.build_wide(ws_wide, owner, 2000)

    fx.stagger_created_at()
    # Archive a small slice of the 1k/5k pages so the Archived navigation
    # section (WIKI-04a) is measured against a selective predicate.
    archived = timezone.now().date()
    Page.objects.filter(id__in=ids_1k[:20]).update(archived_at=archived)
    Page.objects.filter(id__in=ids_5k[:100]).update(archived_at=archived)
    fx.analyze_table()

    owner_client = _client_for(owner)
    other_client = _client_for(other)

    def dataset(name, rows, slug, *, parent=None, page_id=None, search_term="runbook"):
        measurements = []
        _measure("first wiki load", owner_client, _pages_url(slug), measurements)
        _measure("permission-filtered list", other_client, _pages_url(slug), measurements)
        _measure("archived list", owner_client, f"{_pages_url(slug)}?archived=true", measurements)
        if parent is not None:
            parent_param = "" if parent == "root-level" else parent
            label = "tree expansion (root level)" if parent == "root-level" else "tree expansion (parent)"
            _measure(label, owner_client, f"{_pages_url(slug)}?parent={parent_param}", measurements)
        _measure(
            "search",
            owner_client,
            f"/api/workspaces/{slug}/entity-search/?query={search_term}&query_type=page&count=20",
            measurements,
        )
        if page_id is not None:
            _measure("page open", owner_client, _page_url(slug, page_id), measurements)
        datasets.append({"name": name, "measurements": measurements, "rows": rows})

    dataset("1,000 pages — flat", 1000, ws_1k.slug, parent="root-level", page_id=ids_1k[100])
    dataset("5,000 pages — flat", 5000, ws_5k.slug, parent="root-level", page_id=ids_5k[100])
    dataset("deep hierarchy (depth 200)", 200, ws_deep.slug, parent=deep["root"], page_id=deep["leaf"])
    dataset(
        "wide hierarchy (1 root + 2,000 children)",
        2001,
        ws_wide.slug,
        parent=wide["root"],
        page_id=wide["children"][0],
    )

    report = _render_report(datasets)
    report_path = os.environ.get("WIKI_PERF_REPORT")
    if report_path:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(report)
    else:
        print(report)

    # The suite is evidence, not an assertion gate: it must still prove it
    # actually exercised the endpoints.
    for dataset_result in datasets:
        for row in dataset_result["measurements"]:
            assert row["status"] == 200, f"{dataset_result['name']} / {row['label']} returned {row['status']}"


# ---------------------------------------------------------------------------
# candidate index evaluation (spec §21 "evaluate with EXPLAIN, not blindly")
# ---------------------------------------------------------------------------


def _measure_exec(client, url):
    capture = QueryCapture()
    with capture:
        status = client.get(url).status_code
    rows = []
    for sql, params in capture.pages_selects():
        summary = _plan_summary(_explain(sql, params))
        rows.append({"exec_ms": summary["execution_ms"], "indexes": summary["index_names"]})
    execs = [row["exec_ms"] for row in rows if row["exec_ms"] is not None]
    indexes = sorted({name for row in rows for name in row["indexes"]})
    return {
        "status": status,
        "exec_ms": round(max(execs), 2) if execs else None,
        "indexes": indexes,
    }


def _with_index(ddl, fn):
    """Create a candidate index, measure, then drop it so the run stays clean."""
    with connection.cursor() as cursor:
        cursor.execute(ddl)
    fx.analyze_table()
    try:
        return fn()
    finally:
        name = ddl.split(" ON ")[0].split()[-1]
        with connection.cursor() as cursor:
            cursor.execute(f"DROP INDEX IF EXISTS {name}")
        fx.analyze_table()


@pytest.mark.django_db(transaction=True)
def test_wiki_index_candidates(request):
    """A/B the spec §21 candidate indexes against the measured hot paths."""
    from plane.db.models import PageVersion

    owner = _make_user("perf-cand@plane.so")
    ws = _make_workspace("Perf candidates", "perf-cand", owner, 20)
    ids = fx.build_flat(ws, owner, 5000, prefix="Cand")
    fx.build_favorites(ws, owner, ids[:200])
    # A real workspace shares `pages` between project pages and Wiki pages, so
    # `is_global = true` is selective. Model that with project-scope rows.
    fx.build_project_scope_noise(ws, owner, 20000)

    wide_ws = _make_workspace("Perf cand wide", "perf-cand-wide", owner, 20)
    wide = fx.build_wide(wide_ws, owner, 2000)

    # Version history dataset: 300 versions on one Wiki page.
    now = timezone.now()
    PageVersion.objects.bulk_create(
        [
            PageVersion(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                page_id=ids[10],
                owned_by_id=owner.id,
                last_saved_at=now,
                description_html=f"<p>version {index}</p>",
                description_stripped=f"version {index}",
            )
            for index in range(300)
        ],
        batch_size=500,
    )

    fx.stagger_created_at()
    # Archive a small slice so the "Archived" navigation section is selective.
    archived_ids = ids[:100]
    Page.objects.filter(id__in=archived_ids).update(archived_at=timezone.now().date())
    fx.analyze_table()
    fx.analyze_table("page_versions")

    # The winning candidate *is* the shipped index, so evaluate from a clean
    # slate (drop it for this run) and always restore it afterwards.
    with connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS pages_wiki_scope_idx")
    fx.analyze_table()

    def _restore_shipped_index():
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS pages_wiki_scope_idx " "ON pages (workspace_id, is_global, archived_at)"
            )
        fx.analyze_table()

    request.addfinalizer(_restore_shipped_index)

    client = _client_for(owner)

    list_url = _pages_url(ws.slug)
    archived_url = f"{_pages_url(ws.slug)}?archived=true"
    tree_url = f"{_pages_url(wide_ws.slug)}?parent={wide['root']}"
    versions_url = f"/api/workspaces/{ws.slug}/pages/{ids[10]}/versions/"

    # Warm the caches before recording a baseline.
    _measure_exec(client, list_url)
    _measure_exec(client, archived_url)
    _measure_exec(client, tree_url)
    _measure_exec(client, versions_url)

    baseline = {
        "first wiki load": _measure_exec(client, list_url),
        "archived list": _measure_exec(client, archived_url),
        "tree expansion (wide)": _measure_exec(client, tree_url),
        "version history": _measure_exec(client, versions_url),
    }

    experiments = [
        (
            "first wiki load",
            "cand_pages_ws_scope_idx",
            "(workspace_id, is_global, archived_at)",
            "CREATE INDEX cand_pages_ws_scope_idx ON pages (workspace_id, is_global, archived_at)",
            list_url,
        ),
        (
            "first wiki load",
            "pages_ws_scope_soft_idx",
            "(workspace_id, is_global, deleted_at, archived_at)",
            "CREATE INDEX pages_ws_scope_soft_idx ON pages (workspace_id, is_global, deleted_at, archived_at)",
            list_url,
        ),
        (
            "first wiki load",
            "pages_wiki_list_partial_idx",
            "(workspace_id, created_at DESC) WHERE is_global AND deleted_at IS NULL AND archived_at IS NULL",
            "CREATE INDEX pages_wiki_list_partial_idx ON pages (workspace_id, created_at DESC) "
            "WHERE is_global AND deleted_at IS NULL AND archived_at IS NULL",
            list_url,
        ),
        (
            "archived list",
            "pages_wiki_archived_spec_idx",
            "(workspace_id, is_global, archived_at)",
            "CREATE INDEX pages_wiki_archived_spec_idx ON pages (workspace_id, is_global, archived_at)",
            archived_url,
        ),
        (
            "archived list",
            "pages_wiki_archived_partial_idx",
            "(workspace_id, is_global, archived_at) WHERE archived_at IS NOT NULL",
            "CREATE INDEX pages_wiki_archived_partial_idx ON pages (workspace_id, is_global, archived_at) "
            "WHERE archived_at IS NOT NULL",
            archived_url,
        ),
        (
            "tree expansion (wide)",
            "pages_parent_scope_idx",
            "(workspace_id, is_global, parent_id, sort_order)",
            "CREATE INDEX pages_parent_scope_idx ON pages (workspace_id, is_global, parent_id, sort_order)",
            tree_url,
        ),
        (
            "version history",
            "page_version_page_saved_idx",
            "(page_id, last_saved_at DESC)",
            "CREATE INDEX page_version_page_saved_idx ON page_versions (page_id, last_saved_at DESC)",
            versions_url,
        ),
        (
            "version history",
            "page_version_page_created_idx",
            "(page_id, created_at DESC)",
            "CREATE INDEX page_version_page_created_idx ON page_versions (page_id, created_at DESC)",
            versions_url,
        ),
    ]

    lines = [
        "# WIKI-04b — candidate index evaluation",
        "",
        "Each candidate from spec §21 is created, measured (`EXPLAIN (ANALYZE)` on the "
        "hot-path SQL) and dropped. A candidate is kept only if the planner uses it "
        "**and** measured execution improves beyond noise.",
        "",
        "| path | candidate | baseline exec ms | indexed exec ms | planner used candidate |",
        "| --- | --- | --- | --- | --- |",
    ]

    for path, index_name, candidate, ddl, url in experiments:
        try:
            measured = _with_index(ddl, lambda url=url: _measure_exec(client, url))
        except Exception as exc:  # noqa: BLE001 - surface the failure in the report
            lines.append(f"| {path} | `{candidate}` | {baseline[path]['exec_ms']} | error | {exc} |")
            continue
        used = index_name in measured["indexes"]
        lines.append(
            f"| {path} | `{candidate}` | {baseline[path]['exec_ms']} | {measured['exec_ms']} | "
            f"{'yes' if used else 'no'} ({', '.join(measured['indexes']) or '—'}) |"
        )

    # Combined: the curated set as it would actually ship (indexes coexist).
    combined_ddl = [
        "CREATE INDEX pages_wiki_list_idx ON pages (workspace_id, is_global, deleted_at, archived_at)",
        "CREATE INDEX pages_wiki_archived_idx ON pages (workspace_id, is_global, archived_at)",
    ]
    try:
        with connection.cursor() as cursor:
            for ddl in combined_ddl:
                cursor.execute(ddl)
        fx.analyze_table()
        combined_list = _measure_exec(client, list_url)
        combined_archived = _measure_exec(client, archived_url)
        lines.append("")
        lines.append("## Combined curated index set")
        lines.append("")
        lines.append("| path | baseline exec ms | with both indexes | indexes used |")
        lines.append("| --- | --- | --- | --- |")
        lines.append(
            f"| first wiki load | {baseline['first wiki load']['exec_ms']} | {combined_list['exec_ms']} | "
            f"{', '.join(combined_list['indexes']) or '—'} |"
        )
        lines.append(
            f"| archived list | {baseline['archived list']['exec_ms']} | {combined_archived['exec_ms']} | "
            f"{', '.join(combined_archived['indexes']) or '—'} |"
        )
    finally:
        with connection.cursor() as cursor:
            for ddl in combined_ddl:
                name = ddl.split(" ON ")[0].split()[-1]
                cursor.execute(f"DROP INDEX IF EXISTS {name}")
        fx.analyze_table()

    report = "\n".join(lines) + "\n"
    report_path = os.environ.get("WIKI_PERF_INDEX_REPORT")
    if report_path:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(report)
    else:
        print(report)

    for row in baseline.values():
        assert row["status"] == 200
