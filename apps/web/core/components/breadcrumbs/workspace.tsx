/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Breadcrumbs } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { useWorkspace } from "@/hooks/store/use-workspace";

type TCommonWorkspaceBreadcrumbProps = {
  workspaceSlug: string | undefined;
  label?: string;
  href?: string;
};

export const CommonWorkspaceBreadcrumbs = observer(function CommonWorkspaceBreadcrumbs(
  props: TCommonWorkspaceBreadcrumbProps
) {
  const { workspaceSlug } = props;
  const params = useParams();
  const routerWorkspaceSlug = params?.workspaceSlug?.toString();
  const slug = workspaceSlug ?? routerWorkspaceSlug;
  const { getWorkspaceBySlug } = useWorkspace();
  const workspace = slug ? getWorkspaceBySlug(slug) : undefined;

  if (!slug) return null;

  return (
    <Breadcrumbs.Item
      component={
        <BreadcrumbLink
          label={workspace?.name || slug}
          href={`/${slug}`}
          icon={<span className="text-13 font-medium text-tertiary">@</span>}
        />
      }
    />
  );
});
