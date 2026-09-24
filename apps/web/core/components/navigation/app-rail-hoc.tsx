/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// hoc/withDockItems.tsx
import React from "react";
import { observer } from "mobx-react";
import { usePathname } from "next/navigation";
// plane imports
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { PlaneNewIcon, WikiIcon } from "@plane/propel/icons";
// components
import type { AppSidebarItemData } from "@/components/sidebar/sidebar-item";
// hooks
import { useUserSettings } from "@/hooks/store/user";
// local imports
import { buildAppRailItems, type AppRailItemKey } from "./app-rail-items";

type WithDockItemsProps = {
  dockItems: (AppSidebarItemData & { shouldRender: boolean })[];
};

const APP_RAIL_ICONS: Record<AppRailItemKey, React.ReactNode> = {
  work: <PlaneNewIcon className="size-5" />,
  wiki: <WikiIcon className="size-5" />,
};

const APP_RAIL_LABEL_TRANSLATION_KEYS: Record<AppRailItemKey, string> = {
  work: "sidebar.work",
  wiki: "sidebar.wiki",
};

/**
 * Resolves the workspace the Work app points at, from the user's last/fallback
 * workspace rather than the active route parameter (which belongs to the Wiki
 * app on `/wiki/:workspaceSlug` routes).
 */
export const useWorkWorkspaceSlug = (): string => {
  const { data: userSettings } = useUserSettings();
  return userSettings.workspace.last_workspace_slug || userSettings.workspace.fallback_workspace_slug || "";
};

export function withDockItems<P extends WithDockItemsProps>(WrappedComponent: React.ComponentType<P>) {
  const ComponentWithDockItems = observer(function ComponentWithDockItems(props: Omit<P, keyof WithDockItemsProps>) {
    const pathname = usePathname();
    const { t } = useTranslation();
    const workWorkspaceSlug = useWorkWorkspaceSlug();

    const dockItems: (AppSidebarItemData & { shouldRender: boolean })[] = buildAppRailItems({
      workWorkspaceSlug,
      wikiWorkspaceSlug: COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG,
      pathname,
    }).map((item) => ({
      label: t(APP_RAIL_LABEL_TRANSLATION_KEYS[item.key]),
      icon: APP_RAIL_ICONS[item.key],
      href: item.href,
      isActive: item.isActive,
      shouldRender: item.key !== "work" || workWorkspaceSlug !== "",
    }));

    return <WrappedComponent {...(props as P)} dockItems={dockItems} />;
  });

  return ComponentWithDockItems;
}
