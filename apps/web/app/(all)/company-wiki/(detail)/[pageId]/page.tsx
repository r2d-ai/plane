/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane types
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
import { getButtonStyling } from "@plane/propel/button";
import { useTranslation } from "@plane/i18n";
import type { TSearchEntityRequestPayload, TSearchResponse, TWebhookConnectionQueryParams } from "@plane/types";
import { EFileAssetType } from "@plane/types";
// plane utils
import { cn } from "@plane/utils";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { PageHead } from "@/components/core/page-title";
import { CompanyWikiRouteScope } from "@/components/pages/company-wiki-route-scope";
import type { TPageRootConfig, TPageRootHandlers } from "@/components/pages/editor/page-root";
import { PageRoot } from "@/components/pages/editor/page-root";
// hooks
import { useEditorConfig } from "@/hooks/editor";
import { useEditorAsset } from "@/hooks/store/use-editor-asset";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useAppRouter } from "@/hooks/use-app-router";
// plane web hooks
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";
// plane web services
import { WorkspaceService } from "@/services/workspace.service";
// services
import { WorkspacePageService, WorkspacePageVersionService } from "@/services/page";

const workspaceService = new WorkspaceService();
const workspacePageService = new WorkspacePageService();
const workspacePageVersionService = new WorkspacePageVersionService();

const storeType = EPageStoreType.WORKSPACE;

/**
 * Company Wiki page detail (spec §29.1, §29.13).
 *
 * Renders the shared `PageRoot` against the designated workspace. The
 * canonical URL stays `/company-wiki/:pageId` regardless of the user's
 * current workspace, and the workspace slug the editor / services use is
 * always `COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG`. The store/entity read
 * the slug from `router.workspaceSlug`; `CompanyWikiRouteScope` overrides
 * the router query for as long as this surface is mounted so the existing
 * `WorkspacePageStore` / `WorkspacePage` keep working without forking.
 */
const CompanyWikiPageDetailsPage = observer(function CompanyWikiPageDetailsPage() {
  // router
  const router = useAppRouter();
  const { pageId } = useParams();
  // i18n
  const { t } = useTranslation();
  // store hooks
  const { createPage, fetchPageDetails } = usePageStore(storeType);
  const { getWorkspaceBySlug } = useWorkspace();
  const { uploadEditorAsset, duplicateEditorAsset } = useEditorAsset();
  const page = usePage({
    pageId: pageId?.toString() ?? "",
    storeType,
  });
  // derived values
  const workspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;
  const workspaceId = workspaceSlug ? (getWorkspaceBySlug(workspaceSlug)?.id ?? "") : "";
  const { canCurrentUserAccessPage, id, name, updateDescription } = page ?? {};
  // entity search handler — workspace-scoped, no project id for Company Wiki
  const fetchEntityCallback = useCallback(
    async (payload: TSearchEntityRequestPayload): Promise<TSearchResponse> => {
      if (!workspaceSlug) return {};
      return await workspaceService.searchEntity(workspaceSlug, payload);
    },
    [workspaceSlug]
  );
  // editor config
  const { getEditorFileHandlers } = useEditorConfig();
  // fetch page details
  const { error: pageDetailsError } = useSWR(
    workspaceSlug && pageId ? `WORKSPACE_PAGE_DETAILS_${pageId}` : null,
    workspaceSlug && pageId ? () => fetchPageDetails(workspaceSlug, pageId.toString()) : null,
    {
      revalidateIfStale: true,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );
  // page root handlers
  const pageRootHandlers: TPageRootHandlers = useMemo(
    () => ({
      create: createPage,
      fetchAllVersions: async (pageId) =>
        workspaceSlug ? await workspacePageVersionService.fetchAllVersions(workspaceSlug, pageId) : undefined,
      fetchDescriptionBinary: async () => {
        if (!id || !workspaceSlug) return new ArrayBuffer(0);
        return await workspacePageService.fetchDescriptionBinary(workspaceSlug, id);
      },
      fetchEntity: fetchEntityCallback,
      fetchVersionDetails: async (pageId, versionId) =>
        workspaceSlug
          ? await workspacePageVersionService.fetchVersionById(workspaceSlug, pageId, versionId)
          : undefined,
      restoreVersion: async (pageId, versionId) =>
        workspaceSlug ? await workspacePageVersionService.restoreVersion(workspaceSlug, pageId, versionId) : undefined,
      getRedirectionLink: (pageId) => {
        if (pageId) {
          return `/company-wiki/${pageId}`;
        } else {
          return "/company-wiki";
        }
      },
      updateDescription: updateDescription ?? (async () => {}),
    }),
    [createPage, fetchEntityCallback, id, updateDescription, workspaceSlug]
  );
  // page root config — workspace-scoped assets; project id is null per §29.6, §29.8, §29.9
  const pageRootConfig: TPageRootConfig = useMemo(
    () => ({
      fileHandler: getEditorFileHandlers({
        uploadFile: async (blockId, file) => {
          if (!workspaceSlug) throw new Error("Company Wiki designated workspace slug is not configured.");
          const { asset_id } = await uploadEditorAsset({
            blockId,
            data: {
              entity_identifier: id ?? "",
              entity_type: EFileAssetType.PAGE_DESCRIPTION,
            },
            file,
            workspaceSlug,
          });
          return asset_id;
        },
        duplicateFile: async (assetId: string) => {
          if (!workspaceSlug) throw new Error("Company Wiki designated workspace slug is not configured.");
          const { asset_id } = await duplicateEditorAsset({
            assetId,
            entityId: id,
            entityType: EFileAssetType.PAGE_DESCRIPTION,
            workspaceSlug,
          });
          return asset_id;
        },
        workspaceId,
        workspaceSlug: workspaceSlug ?? "",
      }),
    }),
    [getEditorFileHandlers, workspaceId, workspaceSlug, uploadEditorAsset, id, duplicateEditorAsset]
  );

  const webhookConnectionParams: TWebhookConnectionQueryParams = useMemo(
    () => ({
      documentType: "workspace_page",
      workspaceSlug,
    }),
    [workspaceSlug]
  );

  useEffect(() => {
    if (page?.deleted_at && page?.id) {
      router.push(pageRootHandlers.getRedirectionLink());
    }
  }, [page?.deleted_at, page?.id, router, pageRootHandlers]);

  if ((!page || !id) && !pageDetailsError)
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );

  if (pageDetailsError || !canCurrentUserAccessPage)
    return (
      <div className="flex h-full w-full flex-col items-center justify-center">
        <h3 className="text-center text-16 font-semibold">{t("page_not_found.title")}</h3>
        <p className="mt-3 text-center text-13 text-secondary">{t("page_not_found.description")}</p>
        <Link href="/company-wiki" className={cn(getButtonStyling("secondary", "base"), "mt-5")}>
          {t("page_not_found.cta_other_company_wiki")}
        </Link>
      </div>
    );

  if (!page) return null;

  return (
    <>
      <PageHead title={name} />
      <CompanyWikiRouteScope />
      <div className="flex h-full flex-col justify-between">
        <div className="relative flex h-full w-full flex-shrink-0 flex-col overflow-hidden">
          <PageRoot
            config={pageRootConfig}
            handlers={pageRootHandlers}
            storeType={storeType}
            page={page}
            webhookConnectionParams={webhookConnectionParams}
            workspaceSlug={workspaceSlug ?? ""}
          />
        </div>
      </div>
    </>
  );
});

export default CompanyWikiPageDetailsPage;
