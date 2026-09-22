/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { useParams, useRouter } from "next/navigation";
import { EUserPermissionsLevel, EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { EmptyStateDetailed } from "@plane/propel/empty-state";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPage, TPageNavigationTabs } from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
// components
import { PageLoader } from "@/components/pages/loaders/page-loader";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// plane web hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { EPageStoreType as EPageStoreTypeType } from "@/hooks/store";
import type { IProjectPageStore } from "@/store/pages/project-page.store";
import type { IWorkspacePageStore } from "@/store/pages/workspace-page.store";

type TEmptyStateVariant = "project" | "workspace_wiki" | "company_wiki";

type Props = {
  children: React.ReactNode;
  pageType: TPageNavigationTabs;
  storeType: EPageStoreTypeType;
  /**
   * Optional callback that builds the page redirect URL after a new page is created.
   * Defaults to the project-scoped URL `/${workspaceSlug}/projects/${projectId}/pages/${pageId}`.
   * Workspace Wiki callers should pass `${workspaceSlug}/wiki/${pageId}` (or
   * `/company-wiki/${pageId}` when running from the Company Wiki surface).
   */
  buildPageHref?: (params: { workspaceSlug: string; pageId: string }) => string;
  /**
   * Optional permission predicate that gates the empty-state create CTA.
   * Defaults to project ADMIN/MEMBER at the project level.
   */
  canCreatePage?: boolean;
  /**
   * Empty-state copy variant. Defaults to `project`. Wiki surfaces pick the
   * matching wiki variant so the title/description/cta labels stay accurate
   * without forking the layout.
   */
  emptyStateVariant?: TEmptyStateVariant;
};

export const PagesListMainContent = observer(function PagesListMainContent(props: Props) {
  const { children, pageType, storeType, buildPageHref, canCreatePage, emptyStateVariant = "project" } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { currentProjectDetails } = useProject();
  const isWorkspaceStore = storeType === EPageStoreType.WORKSPACE;
  const pageStore: IProjectPageStore | IWorkspacePageStore = usePageStore(storeType);
  const { isAnyPageAvailable, loader, createPage } = pageStore;
  const pageIds = isWorkspaceStore
    ? (pageStore as IWorkspacePageStore).getCurrentWorkspacePageIdsByTab(pageType)
    : (pageStore as IProjectPageStore).getCurrentProjectPageIdsByTab(pageType);
  const filteredPageIds = isWorkspaceStore
    ? (pageStore as IWorkspacePageStore).getCurrentWorkspaceFilteredPageIdsByTab(pageType)
    : (pageStore as IProjectPageStore).getCurrentProjectFilteredPageIdsByTab(pageType);
  const { allowPermissions } = useUserPermissions();
  // states
  const [isCreatingPage, setIsCreatingPage] = useState(false);
  // router
  const router = useRouter();
  const { workspaceSlug } = useParams();
  // derived values
  const defaultCanPerformEmptyStateActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT
  );
  const canPerformEmptyStateActions = canCreatePage ?? defaultCanPerformEmptyStateActions;

  const resolvePageHref = (pageId?: string): string | undefined => {
    if (!pageId) return undefined;
    if (buildPageHref) return buildPageHref({ workspaceSlug: workspaceSlug?.toString() ?? "", pageId });
    return `/${workspaceSlug}/projects/${currentProjectDetails?.id}/pages/${pageId}`;
  };

  // handle page create
  const handleCreatePage = async () => {
    setIsCreatingPage(true);

    const payload: Partial<TPage> = {
      access: pageType === "private" ? EPageAccess.PRIVATE : EPageAccess.PUBLIC,
    };

    await createPage(payload)
      .then((res) => {
        const href = resolvePageHref(res?.id);
        if (href) router.push(href);
      })
      .catch((err) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("common.error"),
          message: err?.data?.error || t("page_not_found.description"),
        });
      })
      .finally(() => setIsCreatingPage(false));
  };

  // resolve empty-state copy for the active variant + tab
  const resolveEmptyStateCopy = (tab: TPageNavigationTabs): { title: string; description: string; cta?: string } => {
    if (emptyStateVariant === "workspace_wiki") {
      if (tab === "archived") {
        return {
          title: t("settings_empty_state.wiki.archived.title"),
          description: t("settings_empty_state.wiki.archived.description"),
        };
      }
      const bucket = tab === "private" ? "private" : "public";
      return {
        title: t(`settings_empty_state.wiki.${bucket}.title`),
        description: t(`settings_empty_state.wiki.${bucket}.description`),
        cta: t(`settings_empty_state.wiki.${bucket}.cta_primary`),
      };
    }
    if (emptyStateVariant === "company_wiki") {
      if (tab === "archived") {
        return {
          title: t("settings_empty_state.wiki.company_wiki.archived.title"),
          description: t("settings_empty_state.wiki.company_wiki.archived.description"),
        };
      }
      const bucket = tab === "private" ? "private" : "public";
      return {
        title: t(`settings_empty_state.wiki.company_wiki.${bucket}.title`),
        description: t(`settings_empty_state.wiki.company_wiki.${bucket}.description`),
        cta: t(`settings_empty_state.wiki.company_wiki.${bucket}.cta_primary`),
      };
    }
    // project (default)
    if (tab === "archived") {
      return {
        title: t("project_empty_state.archive_pages.title"),
        description: t("project_empty_state.archive_pages.description"),
      };
    }
    return {
      title: t("project_empty_state.pages.title"),
      description: t("project_empty_state.pages.description"),
      cta: t("project_empty_state.pages.cta_primary"),
    };
  };

  if (loader === "init-loader") return <PageLoader />;
  // if no pages exist in the active page type
  if (!isAnyPageAvailable || pageIds?.length === 0) {
    const initialCopy = resolveEmptyStateCopy("public");
    if (!isAnyPageAvailable) {
      return (
        <EmptyStateDetailed
          assetKey="page"
          title={initialCopy.title}
          description={initialCopy.description}
          actions={
            initialCopy.cta
              ? [
                  {
                    label: initialCopy.cta,
                    onClick: () => {
                      handleCreatePage();
                    },
                    variant: "primary",
                    disabled: !canPerformEmptyStateActions || isCreatingPage,
                  },
                ]
              : undefined
          }
        />
      );
    }
    const tabCopy = resolveEmptyStateCopy(pageType);
    return (
      <EmptyStateDetailed
        assetKey="page"
        title={tabCopy.title}
        description={tabCopy.description}
        actions={
          tabCopy.cta
            ? [
                {
                  label: tabCopy.cta,
                  onClick: () => {
                    handleCreatePage();
                  },
                  variant: "primary",
                  disabled: !canPerformEmptyStateActions || isCreatingPage,
                },
              ]
            : undefined
        }
      />
    );
  }
  // if no pages match the filter criteria
  if (filteredPageIds?.length === 0)
    return (
      <EmptyStateDetailed
        assetKey="search"
        title={t("common_empty_state.search.title")}
        description={t("common_empty_state.search.description")}
      />
    );

  return <div className="h-full w-full overflow-hidden">{children}</div>;
});
