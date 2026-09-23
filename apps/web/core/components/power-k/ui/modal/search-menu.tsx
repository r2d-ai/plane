/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useEffect } from "react";
import { useParams, usePathname } from "next/navigation";
// plane imports
import { WORKSPACE_DEFAULT_SEARCH_RESULT } from "@plane/constants";
import type { IWorkspaceSearchResults, TWikiSearchResult } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { usePowerK } from "@/hooks/store/use-power-k";
import useDebounce from "@/hooks/use-debounce";
import { WorkspaceService } from "@/services/workspace.service";
import { WikiService } from "@/services/wiki.service";
// local imports
import type { TPowerKContext, TPowerKPageType } from "../../core/types";
import { PowerKModalNoSearchResultsCommand } from "./no-results-command";
import { PowerKModalSearchResults } from "./search-results";
import { isWikiPath } from "./wiki-search-map";
// services init
const workspaceService = new WorkspaceService();
const wikiService = new WikiService();

type Props = {
  activePage: TPowerKPageType | null;
  context: TPowerKContext;
  isWorkspaceLevel: boolean;
  searchTerm: string;
  updateSearchTerm: (value: string) => void;
  handleSearchMenuClose?: () => void;
};

export function PowerKModalSearchMenu(props: Props) {
  const { activePage, context, isWorkspaceLevel, searchTerm, updateSearchTerm, handleSearchMenuClose } = props;
  // states
  const [resultsCount, setResultsCount] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<IWorkspaceSearchResults>(WORKSPACE_DEFAULT_SEARCH_RESULT);
  const [wikiResults, setWikiResults] = useState<TWikiSearchResult[]>([]);
  const debouncedSearchTerm = useDebounce(searchTerm, 500);
  // navigation
  const { workspaceSlug, projectId } = useParams();
  const pathname = usePathname();
  const isWiki = isWikiPath(pathname ?? "");
  // store hooks
  const { togglePowerKModal } = usePowerK();

  useEffect(() => {
    if (activePage || (!workspaceSlug && !isWiki)) return;
    if (!debouncedSearchTerm) {
      setResults(WORKSPACE_DEFAULT_SEARCH_RESULT);
      setWikiResults([]);
      setResultsCount(0);
      setIsSearching(false);
      return;
    }
    let cancelled = false;
    setIsSearching(true);
    void (async () => {
      try {
        if (isWiki) {
          const searchResponse = await wikiService.search(debouncedSearchTerm, 100);
          if (cancelled) return;
          setWikiResults(searchResponse.results);
          setResultsCount(searchResponse.results.length);
        } else {
          const searchResponse = await workspaceService.searchWorkspace(workspaceSlug?.toString() ?? "", {
            ...(projectId ? { project_id: projectId.toString() } : {}),
            search: debouncedSearchTerm,
            workspace_search: !projectId ? true : isWorkspaceLevel,
          });
          if (cancelled) return;
          setResults(searchResponse);
          const count = Object.values(searchResponse.results).reduce((total, section) => total + section.length, 0);
          setResultsCount(count);
        }
      } catch {
        if (cancelled) return;
        setWikiResults([]);
        setResults(WORKSPACE_DEFAULT_SEARCH_RESULT);
        setResultsCount(0);
      } finally {
        if (!cancelled) setIsSearching(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debouncedSearchTerm, isWorkspaceLevel, projectId, workspaceSlug, activePage, isWiki]);

  if (activePage) return null;

  const handleClosePalette = () => {
    handleSearchMenuClose?.();
    togglePowerKModal(false);
  };

  return (
    <>
      {searchTerm.trim() !== "" && (
        <div className="mt-4 flex items-center justify-between gap-2 px-4">
          <h5
            className={cn("text-11 text-primary", {
              "animate-pulse": isSearching,
            })}
          >
            Search results for{" "}
            <span className="font-medium">
              {'"'}
              {searchTerm}
              {'"'}
            </span>{" "}
            in {isWiki ? "Wiki" : isWorkspaceLevel ? "workspace" : "project"}:
          </h5>
        </div>
      )}

      {/* Show empty state only when not loading and no results */}
      {!isSearching && resultsCount === 0 && searchTerm.trim() !== "" && debouncedSearchTerm.trim() !== "" && (
        <PowerKModalNoSearchResultsCommand
          context={context}
          searchTerm={searchTerm}
          updateSearchTerm={updateSearchTerm}
        />
      )}

      {searchTerm.trim() !== "" && (
        <PowerKModalSearchResults
          closePalette={handleClosePalette}
          results={results}
          wikiResults={isWiki ? wikiResults : undefined}
        />
      )}
    </>
  );
}
