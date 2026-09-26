/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { formatValue } from "../cells";

/** §20 cross-tab model, shaped structurally so any producer can feed the renderer. */
export type MatrixRendererModel = {
  rowKeys: string[];
  colKeys: string[];
  cells: Record<string, Record<string, { raw: number; display: string }>>;
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  grandTotal: number;
};

type Props = {
  model: MatrixRendererModel;
  resolveRow: (key: string) => string;
  resolveCol: (key: string) => string;
  onCellClick?: (row: string, col: string) => void;
  canDrilldown: boolean;
};

/** §12.2 — matrix renderer: cross-tab with row/column/grand totals. */
export function MatrixRenderer({ model, resolveRow, resolveCol, onCellClick, canDrilldown }: Props) {
  return (
    <table className="w-full border-collapse text-12">
      <thead>
        <tr className="border-b border-subtle text-tertiary">
          <th className="px-2 py-1 text-left" />
          {model.colKeys.map((col) => (
            <th key={col} className="px-2 py-1 text-right">
              {resolveCol(col)}
            </th>
          ))}
          <th className="px-2 py-1 text-right font-medium">Total</th>
        </tr>
      </thead>
      <tbody>
        {model.rowKeys.map((row) => (
          <tr key={row} className="border-b border-subtle">
            <td className="px-2 py-1 text-left font-medium">{resolveRow(row)}</td>
            {model.colKeys.map((col) => {
              const cell = model.cells[row]?.[col];
              return (
                <td key={col} className="px-2 py-1 text-right">
                  {canDrilldown ? (
                    <button
                      type="button"
                      className="w-full rounded-sm hover:bg-layer-1"
                      onClick={() => onCellClick?.(row, col)}
                    >
                      {cell?.display ?? "—"}
                    </button>
                  ) : (
                    (cell?.display ?? "—")
                  )}
                </td>
              );
            })}
            <td className="px-2 py-1 text-right font-medium">{formatValue(model.rowTotals[row] ?? 0)}</td>
          </tr>
        ))}
        <tr className="font-medium">
          <td className="px-2 py-1 text-left">Total</td>
          {model.colKeys.map((col) => (
            <td key={col} className="px-2 py-1 text-right">
              {formatValue(model.colTotals[col] ?? 0)}
            </td>
          ))}
          <td className="px-2 py-1 text-right">{formatValue(model.grandTotal)}</td>
        </tr>
      </tbody>
    </table>
  );
}
