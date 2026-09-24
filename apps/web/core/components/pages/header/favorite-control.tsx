/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Star } from "lucide-react";
// ui
import { IconButton } from "@plane/propel/icon-button";
import { useTranslation } from "@plane/i18n";
// hooks
import { usePageOperations } from "@/hooks/use-page-operations";
// store
import type { TPageInstance } from "@/store/pages/base-page";

type Props = {
  page: TPageInstance;
};

export const PageFavoriteControl = observer(function PageFavoriteControl({ page }: Props) {
  const { t } = useTranslation();
  // derived values
  const { is_favorite, canCurrentUserFavoritePage } = page;
  // page operations
  const { pageOperations } = usePageOperations({
    page,
  });

  if (!canCurrentUserFavoritePage) return null;

  return (
    <IconButton
      variant="ghost"
      size="lg"
      icon={Star}
      onClick={() => {
        pageOperations.toggleFavorite();
      }}
      aria-label={t(is_favorite ? "page_controls.remove_favorite" : "add_to_favorites")}
      className={
        is_favorite ? "[&_svg]:fill-(--color-label-yellow-icon) [&_svg]:stroke-(--color-label-yellow-icon)" : ""
      }
    />
  );
});
