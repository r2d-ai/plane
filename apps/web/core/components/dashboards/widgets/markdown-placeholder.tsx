/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * FROZEN -- legacy dashboard-builder surface, scheduled for deletion in Phase D of RD-475.
 * Product spec: docs/workspace-dashboards-analytics-v2-spec.md
 * Do not add features, extend behaviour, or wire up new consumers here. The fixed
 * Workspace Dashboard replaces this surface; see RD-475 for the migration table.
 */

import ReactMarkdown from "react-markdown";
import { useTranslation } from "@plane/i18n";

type Props = {
  title: string;
  body?: string;
};

export function MarkdownPlaceholderWidget({ title, body }: Props) {
  const { t } = useTranslation();
  const content = body?.trim() || t("dashboard_shell.widget.markdown_placeholder");

  return (
    <div className="flex h-full flex-col gap-2 p-3">
      <h3 className="text-13 font-medium text-primary">{title}</h3>
      <div className="prose-sm max-w-none text-secondary prose">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
