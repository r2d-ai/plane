# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Registry validation tests for Analytics V2 (spec §49.1).

* every metric is in the registry;
* every dimension is in the registry;
* validation raises on unknown keys.
"""

from __future__ import annotations

import pytest

from plane.analytics.v2 import dimensions, metrics


@pytest.mark.unit
class TestMetricRegistry:
    def test_p0_metrics_are_registered(self):
        # §13.1 — Commercial-parity P0 metrics
        expected_p0 = {
            "work_item_count",
            "estimate_points",
            "pending_work_items",
            "completed_work_items",
            "in_progress_work_items",
            "due_today",
            "due_this_week",
            "blocked_work_items",
        }
        # §13.2 — additional P0/P1 metrics
        expected_p0_p1 = expected_p0 | {
            "overdue_work_items",
            "unassigned_work_items",
            "allocated_work_item_count",
            "allocated_estimate_points",
        }
        assert expected_p0_p1.issubset(set(metrics.REGISTRY))

    def test_each_metric_has_a_category(self):
        from plane.analytics.v2.metrics import (
            SEMANTIC_CURRENT_STATE,
            SEMANTIC_EVENT,
            SEMANTIC_INTERVAL,
        )
        valid_categories = {SEMANTIC_CURRENT_STATE, SEMANTIC_EVENT, SEMANTIC_INTERVAL}
        for spec in metrics.REGISTRY.values():
            assert spec.category in valid_categories

    def test_validation_passes_for_known_keys(self):
        metrics.validate_metric_keys(["work_item_count", "estimate_points"])

    def test_validation_raises_for_unknown_keys(self):
        with pytest.raises(ValueError):
            metrics.validate_metric_keys(["bogus_metric"])


@pytest.mark.unit
class TestDimensionRegistry:
    def test_p0_dimensions_are_registered(self):
        expected = {
            "state",
            "state_group",
            "project",
            "priority",
            "assignees",
            "created_by",
            "labels",
            "cycle",
            "module",
            "work_item_type",
            "estimate_point",
            "created_date",
            "completed_date",
            "start_date",
            "due_date",
        }
        assert expected.issubset(set(dimensions.REGISTRY))

    def test_multi_valued_dimensions_are_marked(self):
        for key in ("assignees", "labels", "cycle", "module"):
            assert dimensions.REGISTRY[key].multi_valued is True

    def test_date_dimensions_are_flagged(self):
        for key in ("created_date", "completed_date", "start_date", "due_date"):
            assert dimensions.REGISTRY[key].is_date is True

    def test_validation_passes_for_known_keys(self):
        dimensions.validate_dimension_keys(["state", "labels"])

    def test_validation_raises_for_unknown_keys(self):
        with pytest.raises(ValueError):
            dimensions.validate_dimension_keys(["not_a_dimension"])