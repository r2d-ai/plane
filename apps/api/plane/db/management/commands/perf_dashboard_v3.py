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
        combined: dict[str, Any] = {"profiles": {}}

        for name in profiles:
            env = os.environ.copy()
            env["DASHBOARD_V3_PERF"] = "1"
            env["DASHBOARD_V3_PERF_BASELINE"] = f"{output_path}.{name}.partial"
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
            combined["profiles"][name] = json.loads(partial_path.read_text(encoding="utf-8"))
            partial_path.unlink(missing_ok=True)

        Path(output_path).write_text(json.dumps(combined, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote baseline {output_path}"))
