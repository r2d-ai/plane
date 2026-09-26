/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Loader2 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TDashboardBatchWidgetResult, TWorkspaceDashboardWidget } from "@plane/types";
import { Button } from "@plane/ui";
import { isStaticWidgetType } from "../time-scope";
import { MarkdownPlaceholderWidget } from "./markdown-placeholder";

type Props = {
  widget: TWorkspaceDashboardWidget;
  batch?: TDashboardBatchWidgetResult;
  loading: boolean;
  onRetry?: () => void;
};

export function DashboardWidgetShell({ widget, batch, loading, onRetry }: Props) {
  const { t } = useTranslation();

  if (isStaticWidgetType(widget.widget_type)) {
    const body = typeof widget.style_config?.body === "string" ? widget.style_config.body : widget.description;
    return <MarkdownPlaceholderWidget title={widget.title} body={body} />;
  }

  if (loading && !batch) {
    return (
      <div className="flex h-full items-center justify-center gap-2 p-4 text-tertiary">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-13">{t("dashboard_shell.widget.loading")}</span>
      </div>
    );
  }

  if (batch?.status === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center">
        <p className="text-danger text-13">{batch.error?.message ?? t("dashboard_shell.widget.error")}</p>
        {onRetry ? (
          <Button variant="neutral-primary" size="sm" onClick={onRetry}>
            {t("dashboard_shell.widget.retry")}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-2 p-3">
      <h3 className="text-13 font-medium text-primary">{widget.title}</h3>
      <p className="text-12 text-tertiary">{t("dashboard_shell.widget.renderer_pending")}</p>
    </div>
  );
}
