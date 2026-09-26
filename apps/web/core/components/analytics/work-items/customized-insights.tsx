/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
// plane package imports
import { useTranslation } from "@plane/i18n";
import type { IAnalyticsParams } from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";
import { cn } from "@plane/utils";
// plane web components
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import { AnalyticsSelectParams } from "../select/analytics-params";
import { useAnalytics } from "@/hooks/store/use-analytics";
import InsightChart from "./insight-chart";
import { buildInsightQuery } from "../v2";

const CustomizedInsights = observer(function CustomizedInsights({
  peekView,
  isEpic,
}: {
  peekView?: boolean;
  isEpic?: boolean;
}) {
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const { selectedDuration, selectedDateBasis, selectedProjects, selectedCycle, selectedModule } = useAnalytics();

  const { control, watch, setValue } = useForm<IAnalyticsParams>({
    defaultValues: {
      x_axis: ChartXAxisProperty.PRIORITY,
      y_axis: isEpic ? ChartYAxisMetric.EPIC_WORK_ITEM_COUNT : ChartYAxisMetric.WORK_ITEM_COUNT,
      date_grouping: "day",
      display: "value",
      normalization: "none",
      allocation: "full_credit",
    },
  });

  const params = {
    x_axis: watch("x_axis"),
    y_axis: watch("y_axis"),
    group_by: watch("group_by"),
    date_grouping: watch("date_grouping"),
    display: watch("display") ?? "value",
    normalization: watch("normalization") ?? "none",
    allocation: watch("allocation") ?? "full_credit",
  };

  const query = useMemo(
    () =>
      buildInsightQuery({
        xAxis: params.x_axis,
        yAxis: params.y_axis,
        groupBy: params.group_by,
        dateGrouping: params.date_grouping,
        display: params.display,
        normalization: params.normalization,
        allocation: params.allocation,
        duration: selectedDuration,
        dateBasis: selectedDateBasis,
        projectIds: selectedProjects,
        cycleId: selectedCycle,
        moduleId: selectedModule,
      }),
    [
      params.allocation,
      params.date_grouping,
      params.display,
      params.group_by,
      params.normalization,
      params.x_axis,
      params.y_axis,
      selectedCycle,
      selectedDateBasis,
      selectedDuration,
      selectedModule,
      selectedProjects,
    ]
  );

  return (
    <AnalyticsSectionWrapper
      title={t("workspace_analytics.customized_insights")}
      className="col-span-1"
      headerClassName={cn(peekView ? "flex-col items-start" : "")}
      actions={
        <AnalyticsSelectParams
          control={control}
          setValue={setValue}
          params={params}
          workspaceSlug={workspaceSlug.toString()}
          isEpic={isEpic}
          classNames="w-full"
        />
      }
    >
      <InsightChart
        query={query}
        x_axis={params.x_axis}
        y_axis={params.y_axis}
        group_by={params.group_by}
        date_grouping={params.date_grouping}
        display={params.display}
      />
    </AnalyticsSectionWrapper>
  );
});

export default CustomizedInsights;
