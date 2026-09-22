/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
// constants
import { EPageAccess } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// plane types
import { Button } from "@plane/propel/button";
import { PageIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TPage } from "@plane/types";
// plane ui
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
// hooks
// plane web imports
import { EPageStoreType, usePageStore } from "@/hooks/store";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { CommonWorkspaceBreadcrumbs } from "@/components/breadcrumbs/common";

const storeType = EPageStoreType.WORKSPACE;

export const WikiListHeader = observer(function WikiListHeader() {
  // states
  const [isCreatingPage, setIsCreatingPage] = useState(false);
  // i18n
  const { t } = useTranslation();
  // router
  const router = useRouter();
  const { workspaceSlug } = useParams();
  const searchParams = useSearchParams();
  const pageType = searchParams.get("type");
  // store hooks
  const { getWorkspaceBySlug } = useWorkspace();
  const { canCurrentUserCreatePage, createPage } = usePageStore(storeType);
  // derived values
  const workspace = workspaceSlug ? getWorkspaceBySlug(workspaceSlug.toString()) : undefined;

  const handleCreatePage = async () => {
    setIsCreatingPage(true);
    const payload: Partial<TPage> = {
      access: pageType === "private" ? EPageAccess.PRIVATE : EPageAccess.PUBLIC,
    };
    await createPage(payload)
      .then((res) => {
        const href = `/${workspaceSlug}/wiki/${res?.id}`;
        router.push(href);
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

  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <CommonWorkspaceBreadcrumbs workspaceSlug={workspaceSlug?.toString()} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("sidebar.wiki")}
                href={`/${workspaceSlug}/wiki/`}
                icon={<PageIcon className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {canCurrentUserCreatePage && workspace && (
        <Header.RightItem>
          <Button variant="primary" size="lg" onClick={handleCreatePage} loading={isCreatingPage}>
            {isCreatingPage ? t("common.adding") : t("wiki.actions.add_page")}
          </Button>
        </Header.RightItem>
      )}
    </Header>
  );
});
