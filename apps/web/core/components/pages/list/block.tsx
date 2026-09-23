/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
// plane imports
import { getPageName } from "@plane/utils";
// components
import { ListItem } from "@/components/core/list";
import { BlockItemAction } from "@/components/pages/list/block-item-action";
// hooks
import { useLabel } from "@/hooks/store/use-label";
import { usePlatformOS } from "@/hooks/use-platform-os";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePage } from "@/hooks/store";

type TPageListBlock = {
  pageId: string;
  storeType: EPageStoreType;
};

export const PageListBlock = observer(function PageListBlock(props: TPageListBlock) {
  const { pageId, storeType } = props;
  // refs
  const parentRef = useRef(null);
  // hooks
  const page = usePage({
    pageId,
    storeType,
  });
  const { isMobile } = usePlatformOS();
  const { getLabelById } = useLabel();
  // handle page check
  if (!page) return null;
  // derived values
  const { name, logo_props, label_ids, getRedirectionLink } = page;
  const pageLabels = label_ids?.slice(0, 3) ?? [];

  return (
    <ListItem
      prependTitleElement={
        <>
          {logo_props?.in_use ? (
            <Logo logo={logo_props} size={16} type="lucide" />
          ) : (
            <PageIcon className="h-4 w-4 text-tertiary" />
          )}
        </>
      }
      appendTitleElement={
        pageLabels.length > 0 ? (
          <div className="flex items-center gap-1">
            {pageLabels.map((labelId) => {
              const label = getLabelById(labelId);
              if (!label) return null;
              return (
                <span
                  key={labelId}
                  className="flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-10 font-medium"
                  style={{ backgroundColor: `${label.color}20`, color: label.color }}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: label.color }} />
                  {label.name}
                </span>
              );
            })}
            {(label_ids?.length ?? 0) > 3 && (
              <span className="text-10 text-tertiary">+{(label_ids?.length ?? 0) - 3}</span>
            )}
          </div>
        ) : undefined
      }
      title={getPageName(name)}
      itemLink={getRedirectionLink()}
      actionableItems={<BlockItemAction page={page} parentRef={parentRef} storeType={storeType} />}
      isMobile={isMobile}
      parentRef={parentRef}
    />
  );
});
