# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Response serialiser for Analytics V2 (spec §32.1).

Pure-JSON-friendly representation of the :class:`AnalyticsResponseV2`
envelope. Centralised so the wire shape stays stable across endpoints.
"""

from __future__ import annotations

from typing import Any, Dict

from .query import AnalyticsResponseV2


def serialise_response(response: AnalyticsResponseV2) -> Dict[str, Any]:
    """Return a plain ``dict`` representation safe for JSON serialisation."""
    return {
        "query": dict(response.query),
        "resolved": dict(response.resolved),
        "schema": dict(response.schema),
        "data": list(response.data),
        "totals": {k: float(v) for k, v in response.totals.items()},
        "warnings": list(response.warnings),
    }


CAPS_METADATA = {
    "max_groups": 20,
    "max_rows": 100,
    "max_matrix_rows": 50,
    "max_matrix_cols": 30,
    "max_work_item_table_page_size": 100,
}