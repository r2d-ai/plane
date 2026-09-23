/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Search } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
// hooks
import { usePowerK } from "@/hooks/store/use-power-k";

/**
 * Routes wiki search through the primary top-nav search bar (Power K)
 * instead of rendering a duplicate wiki-only search field.
 */
export function WikiGlobalSearchTrigger() {
  const { t } = useTranslation();
  const { topNavInputRef } = usePowerK();

  const handleClick = () => {
    const input = topNavInputRef?.current;
    if (!input) return;
    input.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    input.focus();
  };

  return (
    <Button
      variant="secondary"
      size="lg"
      onClick={handleClick}
      className="hidden h-8 gap-2 px-3 text-13 md:inline-flex"
      data-testid="wiki-global-search-trigger"
    >
      <Search className="h-3.5 w-3.5 text-tertiary" />
      <span className="text-secondary">{t("wiki.search_unified_label")}</span>
      <kbd className="rounded border border-subtle bg-layer-2 px-1.5 py-0.5 text-11 text-tertiary">⌘F</kbd>
    </Button>
  );
}
