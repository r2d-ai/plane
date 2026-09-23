/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo } from "react";
import { useParams, usePathname } from "next/navigation";
// plane editor
import type { TMentionSection } from "@plane/editor";
import { buildWikiPageMentionPath, isWorkspaceWikiPage } from "@plane/editor";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/propel/emoji-icon-picker";
import { PageIcon } from "@plane/propel/icons";
// plane types
import type { TPageSearchResponse, TSearchEntities, TSearchResponse } from "@plane/types";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

export type TUseAdditionalEditorMentionArgs = {
  enableAdvancedMentions: boolean;
};

export type TAdditionalEditorMentionHandlerArgs = {
  response: TSearchResponse;
};

export type TAdditionalEditorMentionHandlerReturnType = {
  sections: TMentionSection[];
};

export type TAdditionalParseEditorContentArgs = {
  id: string;
  entityType: TSearchEntities;
};

export type TAdditionalParseEditorContentReturnType =
  | {
      redirectionPath: string;
      textContent: string;
    }
  | undefined;

export const useAdditionalEditorMention = (_args: TUseAdditionalEditorMentionArgs) => {
  const { t } = useTranslation();
  const pathname = usePathname();
  const { workspaceSlug, projectId } = useParams();
  const { getPageById } = usePageStore(EPageStoreType.WORKSPACE);
  const isCompanyWikiSurface = pathname.includes("/company-wiki");

  const updateAdditionalSections = useCallback(
    ({ response }: TAdditionalEditorMentionHandlerArgs): TAdditionalEditorMentionHandlerReturnType => {
      const wikiPages = (response.page ?? []).filter(isWorkspaceWikiPage);
      if (!wikiPages.length) return { sections: [] };

      const items = wikiPages.map((page: TPageSearchResponse) => ({
        id: page.id ?? "",
        entity_identifier: page.id ?? "",
        entity_name: "page" as TSearchEntities,
        title: page.name?.trim() || t("wiki.untitled"),
        subTitle: page.description_stripped?.slice(0, 80) || undefined,
        icon: page.logo_props?.in_use ? (
          <Logo logo={page.logo_props} size={16} type="lucide" />
        ) : (
          <PageIcon className="h-4 w-4 text-tertiary" />
        ),
      }));

      return {
        sections: [
          {
            key: "wiki-pages",
            title: t("wiki.mentions.section_title"),
            items,
          },
        ],
      };
    },
    [t]
  );

  const parseAdditionalEditorContent = useCallback(
    ({ id, entityType }: TAdditionalParseEditorContentArgs): TAdditionalParseEditorContentReturnType => {
      if (entityType !== "page") return undefined;

      const page = getPageById(id);
      const path = buildWikiPageMentionPath(
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

      return {
        redirectionPath: path.replace(/^\//, ""),
        textContent: page?.name?.trim() || t("wiki.untitled"),
      };
    },
    [getPageById, isCompanyWikiSurface, projectId, t, workspaceSlug]
  );

  const editorMentionTypes: TSearchEntities[] = useMemo(() => ["user_mention", "page"], []);

  return {
    updateAdditionalSections,
    parseAdditionalEditorContent,
    editorMentionTypes,
  };
};
