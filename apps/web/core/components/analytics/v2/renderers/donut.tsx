/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { RadialChartRenderer, type RadialChartProps } from "./pie";

type Props = Omit<RadialChartProps, "donut">;

/** §12.2 — donut renderer; `style_config.donut_variant: "progress"` opts into the centre share. */
export function DonutRenderer(props: Props) {
  return <RadialChartRenderer {...props} donut progress={props.progress} />;
}
