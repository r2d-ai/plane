# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Structured filters for Analytics V2 (spec §26.1).

Filters are a small dict of ``{field: [values, ...]}`` mapping allowlisted
fields to value lists. The engine never accepts an arbitrary DB field name
from the client — every filter key is resolved against a strict allowlist
that maps to a safe ORM expression.

This is intentionally NOT a generic DSL. PQL is a separate concern handled
by the existing Plane PQL evaluator; this module covers the structured
filter path that dashboard widgets use.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.db.models import Q, QuerySet


# Allowlist: ``filter_key -> ORM lookup expression``. All values MUST be
# parameterised — never use raw user input as a lookup key.
FILTER_KEYS = frozenset(
    {
        "state_id",
        "state_group",
        "priority",
        "assignee_id",
        "label_id",
        "project_id",
        "cycle_id",
        "module_id",
        "created_by",
        "work_item_type",
    }
)

# Backwards-compatibility alias used elsewhere in the spec.
FILTER_KEY_ALIASES = {
    "state": "state_id",
    "assignees": "assignee_id",
    "labels": "label_id",
    "projects": "project_id",
    "cycles": "cycle_id",
    "modules": "module_id",
    "created_by_id": "created_by",
    "type": "work_item_type",
}


def _normalise_keys(raw: Dict[str, Any]) -> Dict[str, List[Any]]:
    if not raw:
        return {}
    out: Dict[str, List[Any]] = {}
    for k, v in raw.items():
        canonical = FILTER_KEY_ALIASES.get(k, k)
        if canonical not in FILTER_KEYS:
            raise ValueError(f"Unknown filter key: {k!r}")
        if v is None:
            continue
        if not isinstance(v, (list, tuple)):
            v = [v]
        out[canonical] = [x for x in v if x is not None and x != ""]
    return out


def apply_structured_filters(
    queryset: QuerySet, filters: Optional[Dict[str, Any]]
) -> QuerySet:
    """Apply a structured-filter dict to ``queryset``.

    Values are restricted to ``__in``/equality filters against allowlisted
    ORM fields. Unknown keys raise. The ACL scope (caller's project list) is
    NOT modified by this function.
    """
    if not filters:
        return queryset

    normalised = _normalise_keys(filters)
    qs = queryset
    for key, values in normalised.items():
        if not values:
            continue
        if key == "state_group":
            # ``state__group__in`` lookup
            qs = qs.filter(state__group__in=values)
        elif key == "created_by":
            qs = qs.filter(created_by_id__in=values)
        else:
            qs = qs.filter(**{f"{key}__in": values})
    return qs