# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""RD-486: evidence that ``visible_project_count`` is memoised per batch request."""

from __future__ import annotations

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from plane.analytics.v2.query import AnalyticsEngineV2, AnalyticsQueryV2, AnalyticsRequestScope
from plane.tests.fixtures.v3_dashboard_batch import build_v3_card_query
from plane.tests.perf.dashboard_v3_fixtures import build_v3_perf_workspace

pytestmark = pytest.mark.unit

_VISIBLE_PROJECT_SQL = re.compile(
    r'SELECT\s+DISTINCT\s+"issues"\."project_id"',
    re.IGNORECASE,
)


def _visible_project_count_queries(captured) -> int:
    return sum(1 for query in captured.captured_queries if _VISIBLE_PROJECT_SQL.search(query["sql"]))


@pytest.mark.django_db
def test_visible_project_count_sql_once_for_twelve_cards():
    """Shared request scope must not re-run the ACL visible-project DISTINCT per card."""
    workspace, owner, _meta = build_v3_perf_workspace("small")
    card_queries = [
        AnalyticsQueryV2.from_payload(build_v3_card_query(card_id)) for card_id in "ABCDEFGHIJKL"
    ]

    def distinct_project_sql_count(*, shared_scope: bool) -> int:
        if shared_scope:
            scope = AnalyticsRequestScope()
            engine = AnalyticsEngineV2(workspace=workspace, principal=owner, request_scope=scope)
            with CaptureQueriesContext(connection) as captured:
                for query in card_queries:
                    engine.execute(query)
        else:
            with CaptureQueriesContext(connection) as captured:
                for query in card_queries:
                    engine = AnalyticsEngineV2(workspace=workspace, principal=owner)
                    engine.execute(query)
        return _visible_project_count_queries(captured)

    per_card_scopes = distinct_project_sql_count(shared_scope=False)
    shared_scope = distinct_project_sql_count(shared_scope=True)

    assert per_card_scopes >= 12
    assert shared_scope < per_card_scopes
    assert shared_scope <= 2
