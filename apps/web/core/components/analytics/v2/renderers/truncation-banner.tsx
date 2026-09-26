/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Info } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TAnalyticsWarning } from "@plane/types";
import { findTruncationWarning } from "../warnings";

type Props = {
  warnings?: TAnalyticsWarning[];
};

/** §12.2 — the on-screen `RESULT_TRUNCATED` notice every renderer shares. */
export function WidgetTruncationBanner({ warnings }: Props) {
  const { t } = useTranslation();
  const warning = findTruncationWarning(warnings);
  if (!warning) return null;

  return (
    <div
      className="flex items-start gap-2 rounded-md border border-subtle bg-surface-1 px-2 py-1.5 text-12 text-secondary"
      data-testid="widget-truncation-banner"
    >
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tertiary" />
      <span>{warning.message || t("dashboard_shell.widget.truncated")}</span>
    </div>
  );
}
