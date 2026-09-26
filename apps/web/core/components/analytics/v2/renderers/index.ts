/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Generic Analytics V2 presentation components (spec §12.1).
 *
 * One module per renderer kind so a card shell can mount — or lazily import —
 * exactly the renderer its query shape supports, with no dashboard-builder
 * dependency in the dependency graph.
 */

export { NumberRenderer } from "./number";
export { AggregateTableRenderer } from "./aggregate-table";
export { GaugeRenderer } from "./gauge";
export { BarRenderer } from "./bar";
export { LineRenderer } from "./line";
export { PieRenderer, RadialChartRenderer, type RadialChartProps } from "./pie";
export { DonutRenderer } from "./donut";
export { MatrixRenderer, type MatrixRendererModel } from "./matrix";
export { WorkItemTableRenderer } from "./work-item-table";
export { WidgetTruncationBanner } from "./truncation-banner";
