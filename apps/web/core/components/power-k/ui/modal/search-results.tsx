/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Command } from "cmdk";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { FileText } from "lucide-react";
// plane imports
import type { IWorkspaceSearchResults, TWikiSearchResult } from "@plane/types";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
// helpers
import { PowerKModalCommandItem } from "./command-item";
import { POWER_K_SEARCH_RESULTS_GROUPS_MAP } from "./search-results-map";
import { wikiSearchResultPath, wikiSearchResultValue } from "./wiki-search-map";

type Props = {
  closePalette: () => void;
  results: IWorkspaceSearchResults;
  wikiResults?: TWikiSearchResult[];
};

export const PowerKModalSearchResults = observer(function PowerKModalSearchResults(props: Props) {
  const { closePalette, results, wikiResults } = props;
  // router
  const router = useAppRouter();
  const { projectId: routerProjectId } = useParams();
  // derived values
  const projectId = routerProjectId?.toString();

  if (wikiResults) {
    if (wikiResults.length === 0) return null;
    return (
      <Command.Group heading="Pages">
        {wikiResults.map((item) => (
          <PowerKModalCommandItem
            key={`${item.workspace_slug}:${item.page_id}`}
            value={wikiSearchResultValue(item)}
            label={
              <span className="flex min-w-0 flex-col">
                <span className="truncate">{item.page_name}</span>
                <span className="truncate text-11 text-tertiary">{item.workspace_name}</span>
              </span>
            }
            icon={FileText}
            onSelect={() => {
              closePalette();
              router.push(wikiSearchResultPath(item));
            }}
          />
        ))}
      </Command.Group>
    );
  }

  return (
    <>
      {Object.keys(results.results).map((key) => {
        const section = results.results[key as keyof typeof results.results];
        const currentSection = POWER_K_SEARCH_RESULTS_GROUPS_MAP[key as keyof typeof POWER_K_SEARCH_RESULTS_GROUPS_MAP];

        if (!currentSection) return null;
        if (section.length <= 0) return null;

        return (
          <Command.Group key={key} heading={currentSection.title}>
            {section.map((item) => {
              let value = `${key}-${item?.id}-${item.name}`;

              if ("project__identifier" in item) {
                value = `${value}-${item.project__identifier}`;
              }

              if ("sequence_id" in item) {
                value = `${value}-${item.sequence_id}`;
              }

              return (
                <PowerKModalCommandItem
                  key={item.id}
                  label={currentSection.itemName(item)}
                  icon={currentSection.icon}
                  onSelect={() => {
                    closePalette();
                    router.push(currentSection.path(item, projectId));
                    // const itemProjectId =
                    //   item?.project_id ||
                    //   (Array.isArray(item?.project_ids) && item?.project_ids?.length > 0
                    //     ? item?.project_ids[0]
                    //     : undefined);
                    // if (itemProjectId) openProjectAndScrollToSidebar(itemProjectId);
                  }}
                  value={value}
                />
              );
            })}
          </Command.Group>
        );
      })}
    </>
  );
});
