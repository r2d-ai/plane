/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";

export const WorkspaceDashboardsHeader = observer(function WorkspaceDashboardsHeader() {
  const { t } = useTranslation();
  return (
    <div className="flex h-full items-center px-5">
      <span className="text-16 font-medium text-primary">{t("dashboard_shell.title")}</span>
    </div>
  );
});
