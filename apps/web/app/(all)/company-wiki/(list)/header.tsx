/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useRouter, useSearchParams } from "next/navigation";
// constants
import { COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG, EPageAccess } from "@plane/constants";
// plane types
import { Button } from "@plane/propel/button";
import { WikiIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPage } from "@plane/types";
// plane ui
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
// plane web imports
import { EPageStoreType, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

export const CompanyWikiListHeader = observer(function CompanyWikiListHeader() {
  // states
  const [isCreatingPage, setIsCreatingPage] = useState(false);
  // router
  const router = useRouter();
  const searchParams = useSearchParams();
  const pageType = searchParams.get("type");
  // store hooks
  const { canCurrentUserCreatePage, createPage } = usePageStore(storeType);
  // derived values
  const designatedWorkspaceSlug = COMPANY_WIKI_DESIGNATED_WORKSPACE_SLUG;

  const handleCreatePage = async () => {
    setIsCreatingPage(true);
    const payload: Partial<TPage> = {
      access: pageType === "private" ? EPageAccess.PRIVATE : EPageAccess.PUBLIC,
    };
    await createPage(payload)
      .then((res) => {
        const href = `/company-wiki/${res?.id}`;
        router.push(href);
      })
      .catch((err) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error!",
          message: err?.data?.error || "Page could not be created. Please try again.",
        });
      })
      .finally(() => setIsCreatingPage(false));
  };

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label="Company Wiki"
                href="/company-wiki/"
                icon={<WikiIcon className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {canCurrentUserCreatePage && designatedWorkspaceSlug && (
        <Header.RightItem>
          <Button variant="primary" size="lg" onClick={handleCreatePage} loading={isCreatingPage}>
            {isCreatingPage ? "Adding" : "Add page"}
          </Button>
        </Header.RightItem>
      )}
    </Header>
  );
});
