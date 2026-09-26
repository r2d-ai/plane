# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Analytics Engine V2.

A single canonical query engine that both Customized Insights and Dashboards
consume. The package is organised per §36 of
``docs/workspace-dashboards-analytics-v2-spec.md``::

    acl.py            - ACL-safe base queryset
    time_scope.py     - preset/custom time window resolution
    metrics.py        - metric registry
    dimensions.py     - dimension registry
    filters.py        - structured filter application
    allocation.py     - full_credit / split_equal contribution
    normalization.py  - percentage normalization modes
    comparison.py     - reference period resolution
    drilldown.py      - aggregate -> matching raw items
    serializer.py     - JSON schema for the public contract
    query.py          - the entry point that ties everything together

The engine is intentionally additive. The legacy ``advance-analytics``
endpoints remain untouched.
"""

from .query import AnalyticsEngineV2, AnalyticsQueryV2, AnalyticsResponseV2  # noqa: F401