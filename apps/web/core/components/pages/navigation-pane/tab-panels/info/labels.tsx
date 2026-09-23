/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useCallback, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Combobox } from "@headlessui/react";
import useSWR from "swr";
import { PlusIcon } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { CheckIcon, SearchIcon } from "@plane/propel/icons";
// store
import { useLabel } from "@/hooks/store/use-label";
import type { TPageInstance } from "@/store/pages/base-page";

type Props = {
  page: TPageInstance;
};

export const PageNavigationPaneInfoTabLabels = observer(function PageNavigationPaneInfoTabLabels(props: Props) {
  const { page } = props;
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { fetchWorkspaceLabels, getWorkspaceLabels, getLabelById } = useLabel();

  const [query, setQuery] = useState("");

  const workspaceSlugStr = workspaceSlug?.toString() ?? "";
  const { isLoading } = useSWR(
    workspaceSlugStr ? `WORKSPACE_LABELS_${workspaceSlugStr}` : null,
    workspaceSlugStr ? () => fetchWorkspaceLabels(workspaceSlugStr) : null
  );

  const workspaceLabels = getWorkspaceLabels(workspaceSlugStr) ?? [];
  const selectedLabelIds = page.label_ids ?? [];

  const options = workspaceLabels.map((label) => ({
    value: label.id,
    query: label.name,
    content: (
      <div className="flex items-center justify-start gap-2 overflow-hidden">
        <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ backgroundColor: label.color }} />
        <div className="line-clamp-1 inline-block truncate">{label.name}</div>
      </div>
    ),
  }));

  const filteredOptions =
    query === "" ? options : options.filter((option) => option.query.toLowerCase().includes(query.toLowerCase()));

  const handleSelect = useCallback(
    (value: string[]) => {
      page.update({ label_ids: value });
    },
    [page]
  );

  const handleToggleLabel = useCallback(
    (labelId: string) => {
      const current = page.label_ids ?? [];
      const next = current.includes(labelId) ? current.filter((id) => id !== labelId) : [...current, labelId];
      handleSelect(next);
    },
    [page, handleSelect]
  );

  return (
    <div>
      <p className="text-11 font-medium text-secondary">{t("common.labels")}</p>
      <div className="mt-2">
        {/* Selected labels */}
        {selectedLabelIds.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1">
            {selectedLabelIds.map((labelId) => {
              const label = getLabelById(labelId);
              if (!label) return null;
              return (
                <button
                  key={labelId}
                  type="button"
                  onClick={() => handleToggleLabel(labelId)}
                  className="flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-10 font-medium transition-colors hover:opacity-80"
                  style={{ backgroundColor: `${label.color}20`, color: label.color }}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: label.color }} />
                  {label.name}
                </button>
              );
            })}
          </div>
        )}

        {/* Label selector */}
        <Combobox as="div" value={selectedLabelIds} onChange={handleSelect} multiple>
          <Combobox.Button as={Fragment}>
            <Button type="button" variant="tertiary" size="sm" prependIcon={<PlusIcon />} className="w-full">
              <span className="text-11 text-placeholder">{t("label.select")}</span>
            </Button>
          </Combobox.Button>
          <Combobox.Options className="fixed z-10">
            <div className="z-10 my-1 w-48 rounded-sm border border-strong bg-surface-1 py-2.5 text-11 whitespace-nowrap shadow-raised-200 focus:outline-none">
              <div className="px-2">
                <div className="flex w-full items-center justify-start rounded-sm border border-subtle bg-surface-2 px-2">
                  <SearchIcon className="h-3.5 w-3.5 text-tertiary" />
                  <Combobox.Input
                    className="w-full bg-transparent px-2 py-1 text-11 text-secondary placeholder:text-placeholder focus:outline-none"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t("common.search.label")}
                    displayValue={() => ""}
                  />
                </div>
              </div>
              <div className="vertical-scrollbar mt-2 scrollbar-sm max-h-48 space-y-1 overflow-y-scroll px-2 pr-0">
                {isLoading ? (
                  <p className="text-center text-secondary">{t("common.loading")}</p>
                ) : filteredOptions.length > 0 ? (
                  filteredOptions.map((option) => (
                    <Combobox.Option
                      key={option.value}
                      value={option.value}
                      className={({ selected }) =>
                        `flex cursor-pointer items-center justify-between gap-2 truncate rounded-sm px-1 py-1.5 select-none hover:bg-layer-1 ${
                          selected ? "text-primary" : "text-secondary"
                        }`
                      }
                    >
                      {({ selected }) => (
                        <>
                          {option.content}
                          {selected && (
                            <div className="flex-shrink-0">
                              <CheckIcon className="h-3.5 w-3.5" />
                            </div>
                          )}
                        </>
                      )}
                    </Combobox.Option>
                  ))
                ) : (
                  <p className="text-left text-secondary">{t("common.search.no_matching_results")}</p>
                )}
              </div>
            </div>
          </Combobox.Options>
        </Combobox>
      </div>
    </div>
  );
});
