/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import type { Control, UseFormSetValue } from "react-hook-form";
import { Controller } from "react-hook-form";
import { AlignLeft, Percent, CalendarRange, Scale, SlidersHorizontal } from "lucide-react";
// plane package imports
import {
  ANALYTICS_ALLOCATION_OPTIONS,
  ANALYTICS_DATE_GROUPING_OPTIONS,
  ANALYTICS_DISPLAY_OPTIONS,
  ANALYTICS_NORMALIZATION_OPTIONS,
  ANALYTICS_X_AXIS_VALUES,
  ANALYTICS_Y_AXIS_VALUES,
  CHART_X_AXIS_DATE_PROPERTIES,
} from "@plane/constants";
import { CalendarLayoutIcon } from "@plane/propel/icons";
import type { IAnalyticsParams } from "@plane/types";
import { ChartYAxisMetric } from "@plane/types";
import { cn } from "@plane/utils";
import { CustomSelect } from "@plane/ui";
// plane web components
import { SelectXAxis } from "./select-x-axis";
import { SelectYAxis } from "./select-y-axis";

type Props = {
  control: Control<IAnalyticsParams, unknown>;
  setValue: UseFormSetValue<IAnalyticsParams>;
  params: IAnalyticsParams;
  workspaceSlug: string;
  classNames?: string;
  isEpic?: boolean;
};

type TOption<T extends string> = { value: T; label: string };

/**
 * A compact label-style select used by the Customized Insights V2 control row
 * (§18: `[Metric] [Dimension] [Breakdown] [Display] [Normalize] [Allocation]`).
 */
function InsightSelect<T extends string>(props: {
  value: T | undefined;
  onChange: (value: T) => void;
  options: TOption<T>[];
  icon: React.ReactNode;
  placeholder: string;
}) {
  const { value, onChange, options, icon, placeholder } = props;
  return (
    <CustomSelect
      value={value}
      label={
        <div className="flex items-center gap-2">
          {icon}
          <span className={cn("text-secondary", value && "text-primary")}>
            {options.find((option) => option.value === value)?.label || placeholder}
          </span>
        </div>
      }
      onChange={(val: T) => onChange(val)}
      maxHeight="lg"
    >
      {options.map((option) => (
        <CustomSelect.Option key={option.value} value={option.value}>
          {option.label}
        </CustomSelect.Option>
      ))}
    </CustomSelect>
  );
}

export const AnalyticsSelectParams = observer(function AnalyticsSelectParams(props: Props) {
  const { control, setValue, params, classNames, isEpic } = props;
  const xAxisOptions = useMemo(
    () => ANALYTICS_X_AXIS_VALUES.filter((option) => option.value !== params.group_by),
    [params.group_by]
  );
  const groupByOptions = useMemo(
    () => ANALYTICS_X_AXIS_VALUES.filter((option) => option.value !== params.x_axis),
    [params.x_axis]
  );
  const showDateGrouping = useMemo(() => CHART_X_AXIS_DATE_PROPERTIES.includes(params.x_axis), [params.x_axis]);

  return (
    <div className={cn("flex w-full flex-wrap items-center justify-between gap-3", classNames)}>
      <div className="flex flex-wrap items-center gap-2">
        <Controller
          name="y_axis"
          control={control}
          render={({ field: { value, onChange } }) => (
            <SelectYAxis
              value={value}
              onChange={(val: ChartYAxisMetric | null) => {
                onChange(val);
              }}
              options={ANALYTICS_Y_AXIS_VALUES}
              hiddenOptions={[isEpic ? ChartYAxisMetric.WORK_ITEM_COUNT : ChartYAxisMetric.EPIC_WORK_ITEM_COUNT]}
            />
          )}
        />
        <Controller
          name="x_axis"
          control={control}
          render={({ field: { value, onChange } }) => (
            <SelectXAxis
              value={value}
              onChange={(val) => {
                onChange(val);
              }}
              label={
                <div className="flex items-center gap-2">
                  <CalendarLayoutIcon className="h-3 w-3" />
                  <span className={cn("text-secondary", value && "text-primary")}>
                    {xAxisOptions.find((v) => v.value === value)?.label || "Add Property"}
                  </span>
                </div>
              }
              options={xAxisOptions}
            />
          )}
        />
        <Controller
          name="group_by"
          control={control}
          render={({ field: { value, onChange } }) => (
            <SelectXAxis
              value={value}
              onChange={(val) => {
                onChange(val);
              }}
              label={
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="h-3 w-3" />
                  <span className={cn("text-secondary", value && "text-primary")}>
                    {groupByOptions.find((v) => v.value === value)?.label || "Add Property"}
                  </span>
                </div>
              }
              options={groupByOptions}
              placeholder="Breakdown"
              allowNoValue
            />
          )}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Controller
          name="display"
          control={control}
          render={({ field: { value, onChange } }) => (
            <InsightSelect
              value={value}
              onChange={(next) => {
                onChange(next);
                // §17 + §17.4: a percentage display needs a normalisation base.
                if (next !== "value" && (params.normalization ?? "none") === "none") {
                  setValue("normalization", "grand_total");
                }
              }}
              options={ANALYTICS_DISPLAY_OPTIONS}
              icon={<AlignLeft className="h-3 w-3" />}
              placeholder="Display"
            />
          )}
        />
        <Controller
          name="normalization"
          control={control}
          render={({ field: { value, onChange } }) => (
            <InsightSelect
              value={value}
              onChange={(next) => {
                onChange(next);
                // Without a base there is nothing to show as a percentage.
                if (next === "none" && (params.display ?? "value") !== "value") {
                  setValue("display", "value");
                }
              }}
              options={ANALYTICS_NORMALIZATION_OPTIONS}
              icon={<Percent className="h-3 w-3" />}
              placeholder="Normalize"
            />
          )}
        />
        <Controller
          name="allocation"
          control={control}
          render={({ field: { value, onChange } }) => (
            <InsightSelect
              value={value}
              onChange={onChange}
              options={ANALYTICS_ALLOCATION_OPTIONS}
              icon={<Scale className="h-3 w-3" />}
              placeholder="Allocation"
            />
          )}
        />
        {showDateGrouping && (
          <Controller
            name="date_grouping"
            control={control}
            render={({ field: { value, onChange } }) => (
              <InsightSelect
                value={value}
                onChange={onChange}
                options={ANALYTICS_DATE_GROUPING_OPTIONS}
                icon={<CalendarRange className="h-3 w-3" />}
                placeholder="Date grouping"
              />
            )}
          />
        )}
      </div>
    </div>
  );
});
