/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import {
  GANTT_LAYOUT_DISPLAY_PROPERTIES,
  isLegacyDefaultGanttDisplayProperties,
} from "@/components/gantt-chart/helpers/gantt-display-columns";
import type { IIssueDisplayFilterOptions, IIssueDisplayProperties } from "@plane/types";

type GanttLayoutDefaultsResult = {
  displayFilters: IIssueDisplayFilterOptions;
  displayProperties: IIssueDisplayProperties;
  didUpdateDisplayProperties: boolean;
};

export const applyGanttLayoutFilterDefaults = (
  displayFilters: IIssueDisplayFilterOptions,
  displayProperties: IIssueDisplayProperties,
  previousLayout: IIssueDisplayFilterOptions["layout"] | undefined
): GanttLayoutDefaultsResult => {
  if (displayFilters.layout !== "gantt_chart" || previousLayout === "gantt_chart") {
    return {
      displayFilters,
      displayProperties,
      didUpdateDisplayProperties: false,
    };
  }

  const shouldApplyDisplayPropertyDefaults = isLegacyDefaultGanttDisplayProperties(displayProperties);

  return {
    displayFilters: {
      ...displayFilters,
      group_by: null,
      sub_group_by: null,
    },
    displayProperties: shouldApplyDisplayPropertyDefaults
      ? {
          ...displayProperties,
          ...GANTT_LAYOUT_DISPLAY_PROPERTIES,
        }
      : displayProperties,
    didUpdateDisplayProperties: shouldApplyDisplayPropertyDefaults,
  };
};
