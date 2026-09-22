/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane types
import { getButtonStyling } from "@plane/propel/button";
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG } from "@plane/constants";
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

const storeType = EPageStoreType.WORKSPACE;

/**
 * Company Wiki page detail shell (spec §29.1, §29.13).
 *
 * Resolves `COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG` and renders the
 * Workspace Wiki UI against that workspace. The canonical URL stays
 * `/company-wiki/:pageId` regardless of which workspace the user came
 * from. The editor PR (WIKI-03b) plugs into this shell.
 */
const CompanyWikiPageDetailsPage = observer(function CompanyWikiPageDetailsPage() {
  // router
  const router = useAppRouter();
  const { pageId } = useParams();
  // store hooks
  const { fetchPageDetails } = usePageStore(storeType);
  const { getWorkspaceBySlug } = useWorkspace();
  const page = usePage({
    pageId: pageId?.toString() ?? "",
    storeType,
  });
  // derived values
  const workspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;
  const workspace = workspaceSlug ? getWorkspaceBySlug(workspaceSlug) : undefined;
  const { canCurrentUserAccessPage, id, name } = page ?? {};
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

  useEffect(() => {
    if (page?.deleted_at && page?.id) {
      router.push("/company-wiki");
    }
  }, [page?.deleted_at, page?.id, router]);

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
        <Link href="/company-wiki" className={cn(getButtonStyling("secondary", "base"), "mt-5")}>
          View other Company Wiki pages
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
          <p className="mt-2 text-13 text-secondary">Company Wiki &middot; {workspace?.name ?? workspaceSlug}</p>
        </div>
        <p className="max-w-md text-center text-13 text-tertiary">
          The Company Wiki editor will be wired in the next PR. This shell verifies the canonical
          `/company-wiki/:pageId` route resolves the designated workspace and honours the access guard for non-members.
        </p>
      </div>
    </>
  );
});

export default CompanyWikiPageDetailsPage;
