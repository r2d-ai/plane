/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane web components
import { observer } from "mobx-react";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
import { useProject } from "@/hooks/store/use-project";
// components
import DateBasisDropdown from "./select/date-basis";
import DurationDropdown from "./select/duration";
import { ProjectSelect } from "./select/project";

const AnalyticsFilterActions = observer(function AnalyticsFilterActions() {
  const {
    selectedProjects,
    updateSelectedProjects,
    selectedDuration,
    updateSelectedDuration,
    selectedDateBasis,
    updateSelectedDateBasis,
  } = useAnalytics();
  const { joinedProjectIds } = useProject();
  return (
    <div className="flex items-center justify-end gap-2">
      <ProjectSelect
        value={selectedProjects}
        onChange={(val) => {
          updateSelectedProjects(val ?? []);
        }}
        projectIds={joinedProjectIds}
      />
      <DurationDropdown
        buttonVariant="border-with-text"
        value={selectedDuration}
        onChange={(val) => {
          updateSelectedDuration(val);
        }}
        dropdownArrow
      />
      <DateBasisDropdown
        buttonVariant="border-with-text"
        value={selectedDateBasis}
        onChange={(val) => {
          updateSelectedDateBasis(val);
        }}
        dropdownArrow
      />
    </div>
  );
});

export default AnalyticsFilterActions;
