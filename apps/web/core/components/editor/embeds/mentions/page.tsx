/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams, usePathname } from "next/navigation";
import { Link } from "react-router";
// plane imports
import { buildWikiPageMentionPath } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

type Props = {
  id: string;
};

export const EditorPageMention = observer(function EditorPageMention(props: Props) {
  const { id } = props;
  const pathname = usePathname();
  const { workspaceSlug, projectId } = useParams();
  const { t } = useTranslation();
  const { getPageById } = usePageStore(EPageStoreType.WORKSPACE);
  const page = getPageById(id);
  const isCompanyWikiSurface = pathname.includes("/company-wiki");

  const href = buildWikiPageMentionPath(
    {
      id,
      workspace__slug: (workspaceSlug?.toString() || page?.workspace) ?? "",
      projects__id: page?.project_ids ?? [],
    },
    {
      companyWikiSurface: isCompanyWikiSurface,
      projectId: projectId?.toString(),
    }
  );

  const title = page?.name?.trim() || t("wiki.untitled");

  return (
    <span className="not-prose inline-flex items-center gap-1 rounded-sm bg-layer-1 px-1 py-0.5 text-primary no-underline">
      <Link to={href} className="inline-flex items-center gap-1 hover:underline">
        {page?.logo_props?.in_use ? (
          <Logo logo={page.logo_props} size={14} type="lucide" />
        ) : (
          <PageIcon className="h-3.5 w-3.5 text-tertiary" />
        )}
        <span>{title}</span>
      </Link>
    </span>
  );
});
