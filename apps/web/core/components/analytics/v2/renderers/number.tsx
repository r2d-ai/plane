/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { formatValue } from "../cells";

type Props = {
  value: number;
  unit?: string;
};

/** §12.2 — single-number renderer for `number` / `counter` cards. */
export function NumberRenderer({ value, unit }: Props) {
  return (
    <div className="flex h-full items-center justify-center">
      <span className="text-32 font-semibold text-primary">{formatValue(value, unit)}</span>
    </div>
  );
}
