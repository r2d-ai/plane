# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Record v3 dashboard batch perf baselines (RD-480 / 04-perf-plan.md)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from plane.tests.perf.test_page_analytics_perf import V3_BATCH_BUDGETS_MS


def _git_head(api_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(api_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _dataset_label(profile: str) -> str:
    labels = {
        "small": "5 projects x 200 issues (1k work items)",
        "medium": "25 projects x 2000 issues (50k work items)",
        "large": "100 projects x 5000 issues (500k work items)",
    }
    return labels[profile]


def _within_budget(measured: dict[str, Any], budgets: dict[str, float]) -> dict[str, bool]:
    return {
        "p50": measured["p50_ms"] <= budgets["p50"],
        "p95": measured["p95_ms"] <= budgets["p95"],
        "p99": measured["p99_ms"] <= budgets["p99"],
    }


class Command(BaseCommand):
    help = (
        "Run opt-in v3 dashboard batch perf tests and write "
        "plane/tests/perf/baselines/v3-batch-<date>.json"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile",
            choices=["small", "medium", "large", "all"],
            default="all",
            help="Workspace size profile to measure (default: all).",
        )
        parser.add_argument(
            "--output",
            dest="output_path",
            default="",
            help="Override baseline JSON path.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        profile = options["profile"]
        api_root = Path(__file__).resolve().parents[4]
        baselines_dir = api_root / "plane" / "tests" / "perf" / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)
        output_path = options["output_path"] or str(
            baselines_dir / f"v3-batch-{date.today().isoformat()}.json"
        )

        profiles = ["small", "medium", "large"] if profile == "all" else [profile]
        harness_commit = _git_head(api_root)
        fixture = "plane.tests.fixtures.v3_dashboard_batch.build_v3_dashboard_batch_payload"
        combined: dict[str, Any] = {
            "endpoint": "/api/workspaces/{slug}/analytics/v2/batch/",
            "query_count": 12,
            "note": "Global scope merged into each card query per v3_dashboard_batch fixture (not a 13th row).",
            "fixture": fixture,
            "harness_commit": harness_commit,
            "environment": "docker-compose-test.yml api-tests (DASHBOARD_V3_PERF=1)",
            "profiles": [],
        }

        for name in profiles:
            env = os.environ.copy()
            env["DASHBOARD_V3_PERF"] = "1"
            env["DASHBOARD_V3_PERF_BASELINE"] = f"{output_path}.{name}.partial"
            env["DASHBOARD_V3_PERF_HARNESS_COMMIT"] = harness_commit
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                "plane/tests/perf/test_page_analytics_perf.py",
                "-k",
                f"test_batch_12_card_dashboard[{name}]",
                "--create-db",
            ]
            self.stdout.write(f"Running v3 batch perf profile={name} …")
            subprocess.run(cmd, cwd=str(api_root), env=env, check=True)
            partial_path = Path(f"{output_path}.{name}.partial")
            measured = json.loads(partial_path.read_text(encoding="utf-8"))
            budgets = V3_BATCH_BUDGETS_MS[name]
            combined["profiles"].append(
                {
                    "profile": name,
                    "dataset": _dataset_label(name),
                    "fixture": fixture,
                    "harness_commit": harness_commit,
                    "iterations": measured["measured"]["iterations"],
                    "p50_ms": measured["measured"]["p50_ms"],
                    "p95_ms": measured["measured"]["p95_ms"],
                    "p99_ms": measured["measured"]["p99_ms"],
                    "budget_ms": budgets,
                    "within_budget": _within_budget(measured["measured"], budgets),
                }
            )
            partial_path.unlink(missing_ok=True)

        Path(output_path).write_text(json.dumps(combined, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote baseline {output_path}"))
