# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Percentage normalisation (spec §17).

Three modes, applied after every metric has been aggregated and ACL-filtered:

* :data:`NORMALIZATION_NONE`        — no percentages, just values.
* :data:`NORMALIZATION_GROUP_TOTAL` — per primary-dimension group, the cell
  is ``cell / SUM(all cells in the same row group)``. Answers "for Product A,
  who owns the workload?".
* :data:`NORMALIZATION_SERIES_TOTAL` — per secondary/series, the cell is
  ``cell / SUM(all cells in the same series column)``. Answers "where is
  this assignee's workload allocated?".
* :data:`NORMALIZATION_GRAND_TOTAL` — ``cell / total selected metric``.
  Answers "what share of all selected workload does this cell represent?".

In addition to the *normalisation mode*, the caller picks a *display mode*:

* :data:`DISPLAY_VALUE`        — only the raw value.
* :data:`DISPLAY_PERCENTAGE`   — only the percentage.
* :data:`DISPLAY_VALUE_AND_PCT` — both, e.g. ``"18 pts · 42.9%"``.

This module holds the math. It is pure and has no Django/ORM coupling so it
is trivial to unit-test (§49.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


NORMALIZATION_NONE = "none"
NORMALIZATION_GROUP_TOTAL = "group_total"
NORMALIZATION_SERIES_TOTAL = "series_total"
NORMALIZATION_GRAND_TOTAL = "grand_total"

VALID_NORMALIZATIONS = frozenset(
    {
        NORMALIZATION_NONE,
        NORMALIZATION_GROUP_TOTAL,
        NORMALIZATION_SERIES_TOTAL,
        NORMALIZATION_GRAND_TOTAL,
    }
)

DISPLAY_VALUE = "value"
DISPLAY_PERCENTAGE = "percentage"
DISPLAY_VALUE_AND_PCT = "value_and_percentage"

VALID_DISPLAYS = frozenset({DISPLAY_VALUE, DISPLAY_PERCENTAGE, DISPLAY_VALUE_AND_PCT})


@dataclass(frozen=True)
class Cell:
    """A single (group, series, value) triple in normalised output.

    The ``value`` is the raw, ACL-filtered aggregate — already protected from
    hidden projects. The ``percentage`` is ``None`` when normalisation is
    disabled or the denominator was zero.
    """

    group: object
    series: object
    value: float
    percentage: Optional[float]


def _safe_div(num: float, denom: float) -> Optional[float]:
    if denom <= 0:
        return None
    return num / denom


def normalize(
    cells: Iterable[Tuple[object, object, float]],
    *,
    mode: str,
    groups: Optional[Sequence[object]] = None,
    series: Optional[Sequence[object]] = None,
) -> List[Cell]:
    """Apply the chosen normalisation mode to ``cells``.

    ``cells`` is ``[(group, series, raw_value), ...]``. The function returns a
    list of :class:`Cell` objects with ``value`` and ``percentage`` set. The
    output preserves the input order.
    """
    if mode not in VALID_NORMALIZATIONS:
        raise ValueError(f"Unknown normalization mode: {mode!r}")

    rows = [(g, s, float(v)) for g, s, v in cells]
    if not rows or mode == NORMALIZATION_NONE:
        return [Cell(g, s, v, None) for g, s, v in rows]

    if mode == NORMALIZATION_GRAND_TOTAL:
        total = sum(v for _, _, v in rows)
        return [Cell(g, s, v, _safe_div(v, total)) for g, s, v in rows]

    if mode == NORMALIZATION_GROUP_TOTAL:
        # group denominator = SUM(all rows in the same group)
        denom_by_group: Dict[object, float] = {}
        for g, _, v in rows:
            denom_by_group[g] = denom_by_group.get(g, 0.0) + v
        return [Cell(g, s, v, _safe_div(v, denom_by_group[g])) for g, s, v in rows]

    if mode == NORMALIZATION_SERIES_TOTAL:
        # series denominator = SUM(all rows in the same series column)
        denom_by_series: Dict[object, float] = {}
        for _, s, v in rows:
            denom_by_series[s] = denom_by_series.get(s, 0.0) + v
        return [Cell(g, s, v, _safe_div(v, denom_by_series[s])) for g, s, v in rows]

    raise ValueError(f"Unknown normalization mode: {mode!r}")  # pragma: no cover


def format_display(cell: Cell, mode: str, *, unit: str = "") -> str:
    """Format a :class:`Cell` for human display, per §17.4."""
    if mode not in VALID_DISPLAYS:
        raise ValueError(f"Unknown display mode: {mode!r}")
    if mode == DISPLAY_VALUE:
        return f"{_fmt_number(cell.value)}{unit}"
    if mode == DISPLAY_PERCENTAGE:
        if cell.percentage is None:
            return "—"
        return _fmt_percentage(cell.percentage)
    # DISPLAY_VALUE_AND_PCT
    pct = _fmt_percentage(cell.percentage) if cell.percentage is not None else "—"
    return f"{_fmt_number(cell.value)}{unit} · {pct}"


def _fmt_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def _fmt_percentage(pct: float) -> str:
    return f"{pct * 100:.1f}%"