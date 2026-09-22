/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import useSWR from "swr";
// plane types
import { getButtonStyling } from "@plane/propel/button";
// plane ui
// plane utils
import { cn } from "@plane/utils";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { PageHead } from "@/components/core/page-title";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
import { useWorkspace } from "@/hooks/store/use-workspace";
// plane web hooks
import { EPageStoreType, usePage, usePageStore } from "@/hooks/store";
import type { Route } from "./+types/page";

const storeType = EPageStoreType.WORKSPACE;

/**
 * Workspace Wiki page detail shell (WIKI-03a).
 *
 * The editor PR (WIKI-03b) plugs into this shell with `PageRoot`,
 * `webhookConnectionParams` (`documentType: "workspace_page"`) and
 * workspace-scoped asset handling. Until then we render the page
 * metadata shell and the access guard so the route can load without
 * regressing existing Project Pages.
 */
function WikiPageDetailsPage({ params }: Route.ComponentProps) {
  // router
  const router = useAppRouter();
  const { workspaceSlug, pageId } = params;
  // store hooks
  const { fetchPageDetails } = usePageStore(storeType);
  const page = usePage({
    pageId,
    storeType,
  });
  const { getWorkspaceBySlug } = useWorkspace();
  // derived values
  const workspace = workspaceSlug ? getWorkspaceBySlug(workspaceSlug) : undefined;
  const { canCurrentUserAccessPage, id, name } = page ?? {};
  // fetch page details
  const { error: pageDetailsError } = useSWR(
    `WORKSPACE_PAGE_DETAILS_${pageId}`,
    () => fetchPageDetails(workspaceSlug, pageId),
    {
      revalidateIfStale: true,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  );

  useEffect(() => {
    if (page?.deleted_at && page?.id) {
      router.push(`/${workspaceSlug}/wiki`);
    }
  }, [page?.deleted_at, page?.id, router, workspaceSlug]);

  if ((!page || !id) && !pageDetailsError)
    return (
      <div className="grid size-full place-items-center">
        <LogoSpinner />
      </div>
    );

  if (pageDetailsError || !canCurrentUserAccessPage)
    return (
      <div className="flex h-full w-full flex-col items-center justify-center">
        <h3 className="text-center text-16 font-semibold">Page not found</h3>
        <p className="mt-3 text-center text-13 text-secondary">
          The page you are trying to access doesn{"'"}t exist or you don{"'"}t have permission to view it.
        </p>
        <Link href={`/${workspaceSlug}/wiki`} className={cn(getButtonStyling("secondary", "base"), "mt-5")}>
          View other Wiki pages
        </Link>
      </div>
    );

  if (!page) return null;

  return (
    <>
      <PageHead title={name} />
      <div className="flex h-full w-full flex-col items-center justify-center gap-4 p-page-x">
        <div className="text-center">
          <h2 className="text-20 font-semibold">{name}</h2>
          <p className="mt-2 text-13 text-secondary">{workspace?.name ?? workspaceSlug} &middot; Wiki</p>
        </div>
        <p className="max-w-md text-center text-13 text-tertiary">
          The wiki page editor will be wired in the next PR. This shell verifies the route, the workspace page store and
          the access guard work end-to-end.
        </p>
      </div>
    </>
  );
}

export default observer(WikiPageDetailsPage);
