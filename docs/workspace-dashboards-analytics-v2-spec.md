# Workspace Dashboards CE + Analytics V2 — Product & Implementation Spec

Status: Proposed / ready for implementation  
Target branch: master  
Scope: Community Edition fork  
Primary goal: Turn the existing Workspace Analytics / Customized Insights implementation into a reusable analytics engine and add workspace-scoped dashboards that can replace Plane Commercial Dashboards for the fork, while adding stronger workload-allocation and time-range analysis.

---

## 1. Problem

The current fork already has useful Workspace Analytics and Customized Insights primitives:

- workspace-level Analytics routes;
- project selection;
- Work items Overview and Work items analytics;
- Customized Insights with X-axis, metric, and optional group-by;
- chart + table rendering;
- CSV export;
- date-range state already present in the analytics store.

However, the current implementation is still an ad-hoc analytics page rather than a reusable dashboard system.

The main gaps are:

1. Customized Insights cannot express workload share cleanly, for example:
   - what percentage of Product A workload belongs to each assignee;
   - what percentage of a person's workload is spent on each product/label/project;
   - the same questions by work item count or estimate points.
2. The current duration selector is not active in the Workspace Analytics header.
3. Existing Analytics components carry selectedDuration but date_filter is commented out in current data requests.
4. Estimate point count exists in the type system but is currently hidden from the Customized Insights metric selector.
5. Customized Insights is effectively one bar-chart configuration, not a reusable saved query.
6. There is no workspace Dashboard object, widget grid, sharing model, widget-level filtering, saved layout, or dashboard templates.
7. Leaders cannot build reusable management views from analytics without repeatedly reconstructing filters.
8. Aggregated numbers need explicit ACL guarantees so private project data cannot leak through totals, percentages, CSV, filters, or published dashboards.

This feature should solve both problems together.

Do not build a second analytics backend only for dashboards.

The architecture must be:

~~~text
Work item / cycle / intake data
            |
            v
      Viewer ACL scope
            |
            v
      Analytics Engine V2
       /              \
      v                v
Customized Insights   Dashboards
(ad-hoc analysis)     (saved monitoring)
~~~

Customized Insights becomes the interactive query builder.

Dashboards become persisted compositions of the same query definitions.

---

## 2. Commercial reference and parity target

Reference reviewed: 2026-09-26

Official references:

- https://plane.so/dashboards
- https://docs.plane.so/dashboards

Plane Commercial currently documents:

- workspace-scoped dashboards;
- one or more source projects per dashboard;
- dashboard-level filters;
- dashboard-level PQL;
- widget-level filters;
- responsive drag/drop/resize grid;
- view mode and edit mode;
- public/workspace dashboards;
- private dashboards;
- member sharing with View/Edit access;
- published public URL;
- PDF export;
- favorites;
- basic/stacked/grouped bar;
- basic/multi-line line;
- basic/stacked/comparison area;
- donut basic/progress;
- pie;
- number;
- work item statistics;
- smart counter;
- smart gauge;
- two-dimensional table;
- work items table;
- Assigned to you;
- work item type progress;
- cycle progress;
- Intake accepted vs declined;
- average time to accept/decline;
- Intake breakdown;
- Intake ageing;
- grouping by State, State group, Project, Priority, Assignee, Created by, Label, Cycle, Module, Work item type, and date fields;
- metrics including Work item count, Estimate points, Pending, Completed, In-progress, Due today, Due this week, and Blocked.

The CE implementation should cover the useful Commercial behavior and intentionally extend it with:

- dashboard-wide time-range semantics;
- per-widget time-range override;
- percentage normalization;
- workload allocation;
- true two-dimension matrix tables;
- drill-down from aggregate to raw work items;
- previous-period comparisons as a reusable metric capability;
- templates for common management dashboards;
- an API schema suitable for plane-cli and external AI agents.

---

## 3. Product principles

### 3.1 One analytics engine

Customized Insights, dashboard widgets, CSV export, API consumers, plane-cli, and future agent integrations MUST use the same analytics query semantics.

Do not duplicate metric logic in React components or individual widget implementations.

### 3.2 Dashboards are read-only lenses

A dashboard never mutates work items.

It stores:

- source project scope;
- filters;
- time scope;
- widget definitions;
- layout;
- sharing metadata.

All displayed data is computed from the current source data.

### 3.3 ACL before aggregation

Permission filtering happens before:

- counting;
- grouping;
- normalization;
- comparison;
- percentages;
- table totals;
- filter facets;
- export;
- drill-down.

A hidden project must contribute exactly zero observable information to an unauthorized viewer.

### 3.4 Explainable aggregates

Every aggregate that represents work items should support drill-down to the matching work-item set when practical.

A leader seeing "42%" must be able to determine which work items produced that value.

### 3.5 Explicit metric semantics

Do not call calendar duration "workload".

Workload metrics are based on:

- allocated work-item count;
- estimate points;
- actual logged time when Time Tracking data exists.

Flow metrics are separate:

- cycle time;
- lead time;
- throughput;
- completion rate;
- overdue rate.

### 3.6 Backward compatibility

Existing Analytics pages and existing advance-analytics endpoints must keep working while Analytics V2 is introduced.

Do not require a flag-day rewrite.

### 3.7 Fork-friendly implementation

Keep the feature isolated enough that upstream Plane changes can still be merged/backported without rewriting unrelated project/work-item code.

---

## 4. Current CE baseline

Relevant current frontend files include:

- apps/web/app/(all)/[workspaceSlug]/(projects)/analytics/[tabId]/page.tsx
- apps/web/core/components/analytics/analytics-filter-actions.tsx
- apps/web/core/components/analytics/work-items/customized-insights.tsx
- apps/web/core/components/analytics/work-items/priority-chart.tsx
- apps/web/core/components/analytics/work-items/workitems-insight-table.tsx
- apps/web/core/components/analytics/work-items/created-vs-resolved.tsx
- apps/web/core/components/analytics/select/analytics-params.tsx
- apps/web/core/services/analytics.service.ts
- apps/web/core/store/analytics.store.ts
- packages/types/src/analytics.ts
- packages/constants/src/analytics/common.ts

Important observations from the current fork:

1. BaseAnalyticsStore already has selectedDuration with default last_30_days.
2. ANALYTICS_DURATION_FILTER_OPTIONS already defines Yesterday, Last 7 days, Last 30 days, and Last 3 months.
3. AnalyticsFilterActions currently renders ProjectSelect but the DurationDropdown code is commented.
4. CreatedVsResolved, WorkItemsInsightTable, and PriorityChart include selectedDuration in their SWR cache keys, but date_filter is commented out in the actual API parameters.
5. ChartYAxisMetric already defines ESTIMATE_POINT_COUNT.
6. AnalyticsSelectParams currently hides ESTIMATE_POINT_COUNT from Customized Insights.
7. Customized Insights already supports:
   - x_axis;
   - y_axis;
   - optional group_by.
8. PriorityChart already renders:
   - bar chart;
   - stacked bars when group_by is set;
   - a data table;
   - CSV export.

Analytics V2 should reuse these foundations where sensible rather than discarding them.

---

## 5. User-facing information architecture

Keep Analytics and Dashboards separate.

~~~text
Workspace
├── Projects
├── Analytics
│   ├── Overview
│   └── Work items
├── Dashboards        NEW
├── Active cycles / Workspace cycles
├── Wiki
└── ...
~~~

Semantics:

- Analytics = explore, investigate, ad-hoc.
- Dashboards = save, monitor, share.

Customized Insights remains under Analytics.

A configured Customized Insight can be saved as a dashboard widget.

---

## 6. Dashboard list

Route:

~~~text
/:workspaceSlug/dashboards
~~~

Tabs:

- All
- Mine
- Shared
- Favorites

Each dashboard row/card should show:

- name;
- optional description;
- owner;
- visibility;
- source project count;
- updated time;
- favorite state;
- shared indicator where applicable.

Actions:

- Open
- Favorite / unfavorite
- Duplicate
- Rename
- Share
- Export
- Delete, subject to permission

Primary action:

- Add dashboard

Create flow:

1. Name.
2. Optional description.
3. Select one or more projects.
4. Optional dashboard filters.
5. Default time range.
6. Visibility.
7. Template or Blank.
8. Create.

---

## 7. Dashboard page

Route:

~~~text
/:workspaceSlug/dashboards/:dashboardId
~~~

Default mode is View.

Header:

~~~text
[Dashboard name] [Visibility]
[Projects] [Filters] [Time range] [Compare]
                                  [Edit] [Share] [...]
~~~

Edit mode enables:

- add widget;
- configure widget;
- drag;
- resize;
- delete widget;
- edit dashboard filters;
- edit source projects;
- edit default time range.

View mode disables all layout mutation.

All widgets use a responsive grid.

Desktop positions are persisted.

On narrow/mobile displays widgets stack while preserving a deterministic ordering.

---

## 8. Dashboard templates

Provide built-in templates so adoption does not depend on users understanding the full query builder.

### 8.1 Blank

No widgets.

### 8.2 Team overview

Suggested widgets:

- Open work items;
- Completed this period;
- Overdue;
- Blocked;
- Workload by assignee;
- Work by priority;
- Created vs completed trend;
- Due soon table.

### 8.3 Product workload

Designed for mono-project teams that use labels as products.

Suggested widgets:

- Workload by product label;
- Assignee x Product matrix;
- Completed by product;
- Overdue by product;
- Unassigned high-priority work.

### 8.4 Delivery

Suggested widgets:

- Throughput;
- Completion rate;
- Created vs completed;
- Average cycle time;
- Overdue;
- Work item progress by project/module.

### 8.5 Cycle health

Suggested widgets:

- Current cycle progress;
- Scope change;
- Blocked;
- State distribution;
- Remaining work;
- Due/overdue table.

Templates store query/layout defaults only.

They do not create or modify work items.

---

## 9. Global time range

Time filtering is mandatory for Analytics V2.

Supported presets:

- Today
- Yesterday
- This week
- Last week
- Last 7 days
- Last 30 days
- This month
- Last month
- This quarter
- Last quarter
- Last 90 days
- This year
- Custom range

The workspace timezone is authoritative for calendar boundaries.

Persist explicit timezone in resolved query metadata so exports and comparisons are reproducible.

### 9.1 Time basis

Supported basis:

- created_at;
- completed_at;
- start_date;
- target_date;
- lifecycle_overlap.

lifecycle_overlap means:

~~~text
work_item.created_at <= range.end
AND (
    work_item.completed_at IS NULL
    OR work_item.completed_at >= range.start
)
~~~

This means the work item existed as unfinished work during at least part of the period.

It does NOT mean a person actively worked on it for the entire interval.

### 9.2 Widget inheritance

Each dashboard has a default time scope.

Each widget may choose:

- Inherit dashboard time range;
- Custom time range;
- No time range, where the metric is a current-state snapshot.

The widget configuration UI must make this visible.

### 9.3 Date grouping

For date dimensions support:

- Day
- Week
- Month
- Quarter
- Year

Quarter is an intentional CE extension.

---

## 10. Comparison periods

Reusable comparison options:

- None
- Previous equivalent period
- Previous week
- Previous month
- Previous quarter
- Previous year

Example:

~~~text
Current: Sep 1-30
Previous equivalent period: Aug 2-31
~~~

For calendar presets prefer calendar-aligned comparison:

~~~text
This month -> previous month
This quarter -> previous quarter
This year -> previous year
~~~

Number widgets can show:

~~~text
Completed
87
+14.5% vs previous period
~~~

Time-series widgets can render current and comparison series.

Comparison must be a query capability, not a special case limited to one chart renderer.

---

## 11. AnalyticsQuery V2

Introduce one versioned canonical query model.

Conceptual schema:

~~~json
{
  "version": 1,
  "source": "work_items",
  "project_ids": [],
  "metrics": [
    {
      "key": "estimate_points",
      "aggregation": "sum"
    }
  ],
  "dimensions": [
    {
      "key": "labels"
    },
    {
      "key": "assignees"
    }
  ],
  "filters": {},
  "pql": null,
  "time": {
    "preset": "this_quarter",
    "basis": "lifecycle_overlap",
    "timezone": "Asia/Ho_Chi_Minh"
  },
  "comparison": {
    "type": "none"
  },
  "normalization": "group_total",
  "allocation": "split_equal",
  "sort": [],
  "limit": 50
}
~~~

The persisted query stores presets/configuration.

The response includes resolved absolute start/end timestamps.

### 11.1 Sources

P0:

- work_items

P1:

- cycles
- work_item_progress
- time_tracking, only if data exists

P2:

- intake

Do not force Intake-specific metrics into the generic work-item source.

---

## 12. Dimensions

Work-item source dimensions:

- State
- State group
- Project
- Priority
- Assignee
- Created by
- Label
- Cycle
- Module
- Work item type
- Estimate point
- Created date
- Completed date
- Start date
- Due date
- Epic, where available

Date dimensions require date grouping.

Two dimensions are sufficient for P0 generic charts and matrices:

- primary dimension;
- breakdown/series dimension.

Future schema may support more dimensions but the UI must not expose arbitrary OLAP complexity in P0.

---

## 13. Metrics

### 13.1 Commercial-parity generic metrics

P0:

- Work item count
- Estimate points
- Pending work items
- Completed work items
- In-progress work items
- Due today
- Due this week
- Blocked work items

### 13.2 Additional management metrics

P0/P1:

- Backlog work items
- Unstarted work items
- Overdue work items
- Unassigned work items
- High/urgent unassigned work
- Completion rate
- Allocated work-item count
- Allocated estimate points

P1:

- Created throughput
- Completed throughput
- Reopened work items
- Average cycle time
- Median cycle time
- Average lead time
- Median lead time
- Logged time, only when Time Tracking is available
- Overdue rate

### 13.3 Metric categories

The engine must distinguish:

#### Current-state metrics

Examples:

- blocked;
- overdue;
- unassigned;
- pending;
- in progress.

These describe the current record state after the selected cohort/source filters.

#### Event metrics

Examples:

- created throughput;
- completed throughput;
- reopened.

These are counted by event time.

#### Interval metrics

Examples:

- cycle time;
- lead time.

These operate on items with the required start/end timestamps.

Do not silently apply identical date semantics to all three categories.

The API response must include metric_semantics metadata.

---

## 14. Workload semantics

### 14.1 Work-item count is not time

A task open for ten days is still one work item.

Do not infer ten days of effort.

### 14.2 Estimate points are estimated weight

Estimate points may be used as a better workload proxy than raw count when teams use estimates consistently.

The UI should label this as Estimate points, not Hours.

### 14.3 Logged time is actual effort only when available

Only Time Tracking worklogs may be reported as actual logged time.

Never derive actual hours from:

- start date;
- due date;
- completion date;
- calendar duration.

---

## 15. Multi-assignee allocation

Commercial-style grouping normally gives full membership credit to every assignee.

That is useful for membership analytics but can double-count workload.

Analytics V2 therefore defines explicit allocation modes.

### 15.1 Full credit

For a 10-point item with two assignees:

~~~text
Assignee A = 10
Assignee B = 10
~~~

Use for backward-compatible distribution/count views.

### 15.2 Split equally

For the same item:

~~~text
Assignee A = 5
Assignee B = 5
~~~

Use for workload allocation.

### 15.3 Defaults

Default rules:

- ordinary Work item count / Estimate points charts: full_credit;
- workload presets using Assignee as a dimension: split_equal;
- user can see and change Allocation in advanced widget configuration.

Never change an existing metric from full-credit to split silently.

Allocated metrics must be identifiable in exports/API metadata.

---

## 16. Multi-label and multi-membership semantics

A work item may belong to:

- multiple labels;
- multiple modules;
- multiple assignees.

For regular grouping, one work item appears in every matching group.

Therefore:

- totals across labels may exceed unique work item count;
- totals across assignees may exceed unique work item count in full-credit mode;
- assignee allocation percentages across labels may exceed 100% if the same work item is tagged with multiple product labels.

The UI must not imply otherwise.

When normalization by a multi-valued dimension could exceed 100%, show an info tooltip:

> Work items can belong to multiple values in this dimension. Shares across groups may exceed 100%.

P1 may add split-across-dimension allocation for explicitly mutually-exclusive reporting taxonomies, but this is not required for P0.

---

## 17. Percentage normalization

Customized Insights and applicable dashboard widgets support:

- None
- Group total
- Series/assignee total
- Grand total

### 17.1 Group total

Question:

> For Product A, who owns the workload?

For Label x Assignee:

~~~text
cell / SUM(all assignees for the same label)
~~~

Each row/category total is 100% when memberships are mutually compatible.

### 17.2 Series / assignee total

Question:

> Where is this person's workload allocated?

For Label x Assignee:

~~~text
cell / SUM(all labels for the same assignee)
~~~

With multi-label memberships this may exceed 100%; show the multi-membership notice.

### 17.3 Grand total

Question:

> What share of all selected workload does this cell/category represent?

~~~text
cell / total selected metric
~~~

### 17.4 Display mode

- Value
- Percentage
- Value + percentage

Example cell:

~~~text
18 pts · 42.9%
~~~

CSV exports must include raw value and percentage as separate columns when percentage is enabled.

---

## 18. Customized Insights V2

Keep Customized Insights inside Workspace Analytics.

New control row:

~~~text
[Metric] [Dimension] [Breakdown] [Display] [Normalize] [Allocation]
~~~

Workspace Analytics header:

~~~text
[Projects] [Time range] [Date basis]
~~~

Optional advanced settings:

- date grouping;
- comparison;
- sort;
- Top N;
- include/exclude empty groups.

### 18.1 Required fixes to current implementation

1. Re-enable DurationDropdown in AnalyticsFilterActions.
2. Actually pass selected time filters to Analytics V2.
3. Re-enable Estimate points in the metric selector.
4. Add x-axis date grouping to the Customized Insights form.
5. Add display/normalization/allocation settings.
6. Keep CSV export.
7. Keep the table beneath the chart.
8. Add Save to dashboard.
9. Add drill-down from chart/table cells.

### 18.2 Save to dashboard

Action:

~~~text
Save to dashboard
  -> choose dashboard
  -> widget title
  -> choose visualization
  -> save
~~~

The saved widget stores the AnalyticsQuery V2 configuration.

It does not snapshot current results.

---

## 19. Widget system

A widget consists of:

- type;
- model;
- title;
- query;
- style configuration;
- layout;
- time inheritance;
- optional description.

### 19.1 Generic chart widgets

P0/P1:

- Number
- Bar
  - Basic
  - Stacked
  - Grouped
- Line
  - Basic
  - Multi-line
- Area
  - Basic
  - Stacked
  - Comparison
- Pie
- Donut
  - Basic
  - Progress

### 19.2 Analytical widgets

- Work item statistics
- Smart counter
- Smart gauge
- Matrix table
- Work items table
- Assigned to current user
- Progress by work item type
- Cycle progress
- Text / Markdown

### 19.3 Intake widgets

P2 parity:

- Accepted vs declined
- Average time to accept/decline
- Intake breakdown
- Intake ageing

These should use Intake data semantics, not fake them through work-item state queries.

---

## 20. Matrix table

The CE Matrix Table intentionally goes beyond Commercial's documented simple "two dimensional table".

It supports a true cross-tab.

Example:

~~~text
                 Game A         Game B         Game C        Total
Alex             12 · 31%       7 · 18%       20 · 51%      39
Anna              5 · 42%       7 · 58%        -            12
Nova             17 · 68%       3 · 12%        5 · 20%      25
Total            34             17             25            76
~~~

Configuration:

- Rows: one dimension
- Columns: second dimension
- Metric
- Display
- Normalize by row / column / grand total
- Allocation
- Show row totals
- Show column totals
- Heatmap
- Sort
- Max rows / max columns

Use cases:

- Assignee x Product label
- Assignee x Project
- Project x State
- Module x Priority
- Label x State

Cells support drill-down.

---

## 21. Work Items Table

A flat list of matching work items.

Always-visible columns:

- Identifier
- Name
- Project

Optional columns:

- State
- Priority
- Assignees
- Due date
- Start date
- Labels
- Cycle
- Modules
- Work item type
- Estimate points
- Created by
- Sub-work item count
- Attachment count
- Link count
- Releases, if available

P1/P2 may include:

- customer requests;
- customer;
- logged time;
- custom properties where practical.

Configuration:

- column chooser;
- sort;
- rows per page 1-100;
- widget filters;
- time scope.

Click row opens the work item.

---

## 22. Dynamic viewer filters

Support dynamic filter tokens:

- current_user as assignee;
- current_user as creator;
- current_user as subscriber, when supported.

The "Assigned to you" widget is implemented as a Work Items Table preset:

~~~text
assignee = current_user
~~~

This lets one shared dashboard render personal work for every signed-in viewer.

Dynamic viewer widgets return no user-specific rows to anonymous published viewers.

---

## 23. Progress widgets

### 23.1 Smart Gauge

Group by:

- Project
- Assignee
- Label
- Module
- Cycle
- Work item type
- State-compatible dimensions where meaningful

Metric:

- Work item count
- Estimate points

Progress:

~~~text
completed_metric / total_metric
~~~

Cancelled work treatment must be configurable:

- Exclude cancelled, default
- Count cancelled as completed

### 23.2 Work item type progress

Rows are work items of selected parent types, for example Epic.

Progress derives from direct sub-items.

Supports:

- work item count;
- estimate points;
- linear bar;
- state-group breakdown;
- show percentage;
- include/exclude empty parent items.

---

## 24. Cycle progress

Provide parity with Commercial Cycle Progress plus support for the fork's Workspace Cycles.

Cycle target:

- Specific project cycle
- Current project cycle
- Next project cycle
- Specific workspace cycle
- Current workspace cycle

Display:

- state-group distribution;
- completed share;
- total work items;
- scope change where the necessary historical data exists;
- blocked items;
- time elapsed;
- days left;
- cycle status.

Dynamic "Current cycle" is important so dashboards do not require manual edits every sprint/quarter.

Workspace-cycle metrics MUST reuse Workspace Cycle ACL semantics.

---

## 25. Drill-down

Applicable chart segments/cells are clickable.

Open a right-side drawer:

~~~text
Workload details
Label: Game A
Assignee: Alex
Metric: Allocated estimate points
Range: Q3 2026

12 matching work items
31 allocated estimate points

DES-421  Landing page
DES-432  Banner
DES-449  Store artwork
...
~~~

The drill-down query MUST be derived from the exact resolved aggregate query.

Do not rebuild filter logic independently in the client.

The drill-down response should include:

- resolved query metadata;
- total matching rows;
- paginated work items;
- raw metric contribution where meaningful.

---

## 26. Dashboard filters and PQL

Filter order:

~~~text
Viewer ACL
  ∩ dashboard source projects
  ∩ dashboard filters
  ∩ dashboard PQL
  ∩ dashboard time scope
  ∩ widget filters
  ∩ widget time override
  ∩ dynamic viewer filter
~~~

A widget may only narrow the dashboard base dataset.

It cannot use a project that is outside the dashboard's configured project set.

### 26.1 Filters

Use Plane's existing work-item filter model where possible.

Avoid inventing a separate filter DSL.

### 26.2 PQL

If the existing PQL parser/evaluator is available in the CE code path, reuse it.

PQL errors must:

- fail the affected dashboard/widget cleanly;
- display a useful validation message;
- never fall back to an unfiltered query.

---

## 27. Dashboard data model

Use dedicated dashboard models.

Do not encode dashboards into generic Pages or Views.

Recommended models follow.

### 27.1 Dashboard

Fields:

- id
- workspace_id
- name
- description
- owner_id
- visibility: workspace | private
- filters JSON
- pql nullable text
- default_time_scope JSON
- comparison JSON
- created_at
- updated_at
- deleted_at

Project scope uses a join table rather than a JSON array.

### 27.2 DashboardProject

Fields:

- dashboard_id
- project_id

Unique:

~~~text
(dashboard_id, project_id)
~~~

### 27.3 DashboardWidget

Fields:

- id
- dashboard_id
- title
- description
- widget_type
- widget_model
- query_config JSON
- style_config JSON
- layout_config JSON
- inherit_time_scope boolean
- custom_time_scope JSON nullable
- sort_order
- created_at
- updated_at
- deleted_at

query_config MUST include a schema version.

### 27.4 DashboardMemberAccess

Fields:

- dashboard_id
- member_id
- access: view | edit

Unique:

~~~text
(dashboard_id, member_id)
~~~

### 27.5 DashboardFavorite

Per-user relation:

- dashboard_id
- member_id

### 27.6 DashboardPublishLink

P2:

- dashboard_id
- token_hash
- is_active
- published_by
- created_at
- regenerated_at
- optional expires_at, CE extension

Do not store the plaintext share token after creation if avoidable.

---

## 28. Permissions

### 28.1 Workspace-visible dashboard

Readable by active workspace members, subject to source-data ACL.

Editable by:

- dashboard owner;
- workspace admin/owner.

### 28.2 Private dashboard

Readable by:

- dashboard owner;
- explicitly shared View/Edit members;
- workspace admin/owner only if existing workspace governance semantics intentionally grant this. Do not assume bypass without checking current Plane permission patterns.

Editable by:

- owner;
- shared Edit members.

Only owner can:

- delete;
- change visibility;
- manage sharing;
- publish/unpublish.

### 28.3 Data ACL is independent of dashboard access

Being allowed to open a dashboard does NOT grant access to its projects.

Example:

~~~text
Dashboard configured projects: A, B, C
Viewer can access: A, C
Resolved source projects: A, C
~~~

All totals, legends, facets, percentages, exports, and drill-downs use only A + C.

Do not show "1 hidden project" because even that leaks metadata.

---

## 29. Public publishing

P2, default disabled for the fork.

Workspace/instance setting:

~~~text
Allow anonymous dashboard publishing: OFF
~~~

When disabled, no Publish tab/action exists.

When enabled:

- only dashboard owner may publish;
- workspace administrators can revoke published links;
- public dashboard is read-only;
- current_user widgets render empty/not-applicable;
- the link can be regenerated;
- old token becomes invalid immediately.

Recommended CE safety extensions beyond Commercial:

- optional expiry;
- optional password in a later phase;
- audit event for publish/unpublish/regenerate;
- admin-level kill switch.

Publishing private project data is an intentional disclosure action and must display a warning.

---

## 30. Export

### 30.1 Widget export

P0:

- CSV for table/statistical data;
- copy data.

P1:

- PNG for chart widgets.

### 30.2 Dashboard export

P1:

- PDF;
- portrait / landscape;
- charts rendered as images;
- tables exported as structured content where practical;
- preserve desktop widget order/layout.

Exports MUST use the same viewer ACL and resolved query as the on-screen dashboard.

No privileged server-side export scope.

---

## 31. Favorites and duplication

Favorites are per-user.

Duplicate dashboard:

- copies dashboard configuration;
- copies project selections;
- copies widget definitions/layout;
- does not copy sharing;
- does not copy publish token;
- new owner is the duplicating user.

---

## 32. Analytics API V2

Recommended base:

~~~text
/api/workspaces/{workspace_slug}/analytics/v2/
~~~

### 32.1 Query

~~~text
POST /query
~~~

Request:

- AnalyticsQuery V2

Response:

~~~json
{
  "query": {},
  "resolved": {
    "start": "...",
    "end": "...",
    "timezone": "...",
    "visible_project_count": 5
  },
  "schema": {},
  "data": [],
  "totals": {},
  "warnings": []
}
~~~

Do not return inaccessible project identifiers in metadata.

### 32.2 Drill-down

~~~text
POST /drilldown
~~~

Input:

- original query;
- selected dimension values;
- pagination.

### 32.3 Dashboard batch data

Recommended:

~~~text
POST /dashboards/{dashboard_id}/data
~~~

The server resolves:

1. dashboard access;
2. viewer project ACL;
3. dashboard filters once;
4. widget queries.

Response returns independent widget results:

~~~json
{
  "dashboard_id": "...",
  "resolved_time": {},
  "widgets": {
    "widget-id-1": {
      "status": "ok",
      "data": []
    },
    "widget-id-2": {
      "status": "error",
      "error": {
        "code": "INVALID_QUERY"
      }
    }
  }
}
~~~

One broken widget must not blank the entire dashboard.

---

## 33. Dashboard CRUD API

Recommended routes:

~~~text
GET    /api/workspaces/{slug}/dashboards
POST   /api/workspaces/{slug}/dashboards
GET    /api/workspaces/{slug}/dashboards/{id}
PATCH  /api/workspaces/{slug}/dashboards/{id}
DELETE /api/workspaces/{slug}/dashboards/{id}

POST   /api/workspaces/{slug}/dashboards/{id}/duplicate

POST   /api/workspaces/{slug}/dashboards/{id}/widgets
PATCH  /api/workspaces/{slug}/dashboards/{id}/widgets/{widget_id}
DELETE /api/workspaces/{slug}/dashboards/{id}/widgets/{widget_id}

POST   /api/workspaces/{slug}/dashboards/{id}/layout
POST   /api/workspaces/{slug}/dashboards/{id}/favorite
DELETE /api/workspaces/{slug}/dashboards/{id}/favorite

GET    /api/workspaces/{slug}/dashboards/{id}/members
POST   /api/workspaces/{slug}/dashboards/{id}/members
PATCH  /api/workspaces/{slug}/dashboards/{id}/members/{member_id}
DELETE /api/workspaces/{slug}/dashboards/{id}/members/{member_id}
~~~

P2:

~~~text
POST   /api/workspaces/{slug}/dashboards/{id}/publish
DELETE /api/workspaces/{slug}/dashboards/{id}/publish
POST   /api/workspaces/{slug}/dashboards/{id}/publish/regenerate
~~~

---

## 34. Frontend architecture

Recommended new feature area:

~~~text
apps/web/core/components/dashboards/
apps/web/core/services/dashboard.service.ts
apps/web/core/store/dashboard.store.ts
~~~

Add routes in:

~~~text
apps/web/app/routes/core.ts
~~~

Suggested component split:

~~~text
dashboards/
├── list/
├── detail/
├── grid/
├── widgets/
│   ├── number/
│   ├── bar/
│   ├── line/
│   ├── area/
│   ├── pie/
│   ├── donut/
│   ├── matrix-table/
│   ├── work-items-table/
│   ├── statistics/
│   ├── counter/
│   ├── gauge/
│   ├── progress/
│   ├── cycle-progress/
│   └── markdown/
├── config/
├── filters/
├── share/
└── templates/
~~~

Generic chart renderers should reuse @plane/propel chart components where practical.

Do not fork chart libraries unnecessarily.

---

## 35. Analytics frontend refactor

Introduce shared Analytics V2 types in packages/types.

Suggested concepts:

- TAnalyticsQueryV2
- TAnalyticsMetric
- TAnalyticsDimension
- TAnalyticsTimeScope
- TAnalyticsComparison
- TAnalyticsNormalization
- TAnalyticsAllocation
- TAnalyticsQueryResponse
- TAnalyticsDrilldownRequest

The existing Customized Insights form should be migrated to these types.

Legacy ChartXAxisProperty and ChartYAxisMetric may remain as compatibility adapters until all existing Analytics components migrate.

---

## 36. Backend query engine

Create a centralized analytics-query service rather than per-widget ORM code.

Conceptual modules:

~~~text
analytics/
├── acl.py
├── query.py
├── metrics.py
├── dimensions.py
├── filters.py
├── time_scope.py
├── normalization.py
├── allocation.py
├── comparison.py
├── serializer.py
└── drilldown.py
~~~

Responsibilities:

### acl.py

Resolve visible project/work-item base scope.

### dimensions.py

Map stable dimension keys to ORM expressions/join strategies.

### metrics.py

Map metric keys to aggregation semantics.

### filters.py

Apply structured filters/PQL.

### time_scope.py

Resolve preset and custom time windows using workspace timezone.

### allocation.py

Handle full-credit vs split-equal contribution.

### normalization.py

Calculate percentages from already ACL-filtered aggregates.

### comparison.py

Resolve reference period and execute compatible comparison query.

### drilldown.py

Convert aggregate selection into matching raw item query.

Do not accept arbitrary client-provided database field names.

Every metric/dimension must come from a server-side registry.

---

## 37. ACL safety requirements

This section is mandatory.

### 37.1 Resolve visible projects first

Conceptually:

~~~python
visible_project_ids = get_accessible_project_ids(
    principal=request.user_or_service_principal,
    workspace=workspace,
)

base_issue_qs = Issue.objects.filter(
    workspace=workspace,
    project_id__in=visible_project_ids,
)
~~~

Every analytics source starts from an equivalent authorized set.

### 37.2 No side channels

Do not leak hidden data through:

- total counts;
- chart stack totals;
- percentages;
- "Other";
- labels;
- assignee names;
- filter options;
- project count;
- matrix totals;
- pagination totals;
- exports;
- comparison deltas;
- public links;
- cache hits;
- errors.

### 37.3 Query validation

If a query references a project outside dashboard scope or viewer ACL:

- ignore/remove it from the effective source set;
- do not reveal whether it exists.

### 37.4 Service tokens

When Analytics V2 is called by the fork's workspace/instance service tokens, use the centralized service-principal permission resolver.

Do not special-case service tokens to bypass project/workspace boundaries.

---

## 38. Query correctness and timezone

All preset boundaries must be resolved in workspace timezone.

Persist timestamps in UTC.

API response includes resolved local timezone and UTC boundaries.

Tests must cover:

- DST timezone;
- non-DST timezone;
- month boundary;
- quarter boundary;
- year boundary;
- exact start inclusive;
- exact end exclusive.

Recommended interval convention:

~~~text
[start, end)
~~~

This avoids double-counting adjacent periods.

---

## 39. Created/completed trend

Migrate the existing CreatedVsResolved chart to Analytics V2.

Current behavior should remain recognizable, but time filtering becomes real.

Query concept:

- metric A: created events in bucket;
- metric B: completed events in bucket;
- dimension: date bucket;
- dashboard/analytics time scope.

A period with no events should render zero for count series where appropriate.

---

## 40. Performance

P0 must be safe on a normal PostgreSQL Plane deployment.

Do not add ClickHouse or another analytical database.

### 40.1 Query caps

Defaults:

- max groups: 20
- configurable max rows: 100
- max matrix rows: 50
- max matrix columns: 30
- work item table page size: max 100

### 40.2 Batch dashboard loading

Prefer one dashboard-data batch request rather than one network request per widget.

The backend may still execute widget queries independently, but it should reuse:

- resolved ACL project IDs;
- dashboard base filters;
- resolved time range.

### 40.3 Database indexes

Before implementation is merged, inspect actual query plans and add only justified indexes.

Likely hot fields:

- workspace_id;
- project_id;
- state_id;
- created_at;
- completed_at;
- start_date;
- target_date;
- assignee join;
- label join;
- cycle join;
- module join;
- relation type for blocked.

Do not add speculative duplicate indexes.

### 40.4 Caching

P0 recommendation:

- no cross-user aggregate cache;
- optional short-lived per-principal/query-hash cache only after correctness is established.

Never cache dashboard data only by dashboard_id.

Viewer ACL changes must not reuse another viewer's aggregate result.

---

## 41. Failure behavior

Dashboard load should be resilient.

If one widget fails:

- render that widget's error state;
- keep other widgets usable;
- expose Retry;
- log structured query error.

Invalid filter/PQL:

- do not fall back to broader data;
- show Invalid filter/query.

Unavailable source feature:

Example: Estimate points requested for projects without point estimates.

Return:

- zero contribution where this matches existing Plane semantics;
- a warning in response metadata when useful.

---

## 42. Empty states

Dashboard list:

- no dashboards -> explain purpose + Create dashboard.

Dashboard detail:

- no widgets -> Add widget / choose template.

Widget:

- valid query, zero results -> No matching data.
- insufficient configuration -> Configure widget.
- missing permission/source after ACL -> No accessible data, without revealing hidden objects.

---

## 43. i18n

All new user-visible strings use Plane i18n.

Do not ship English-only control labels such as:

- Normalize
- Allocation
- Compare
- Previous quarter
- Save to dashboard
- Matrix
- Drill down
- Public link warning

Reuse existing common strings where possible.

---

## 44. Migration and rollout

### 44.1 Database migration

Add dashboard tables.

No existing work-item data migration.

No dashboard backfill required.

### 44.2 Analytics compatibility

Keep legacy endpoints active during migration.

Introduce V2 alongside them.

Suggested sequence:

1. Analytics V2 query engine and tests.
2. Customized Insights V2.
3. Enable actual time-range filtering.
4. Dashboard models/API.
5. Dashboard UI.
6. Specialized widgets.
7. Export/sharing/publishing.
8. Migrate legacy analytics charts opportunistically.

### 44.3 Feature flag

Recommended during development:

~~~text
WORKSPACE_DASHBOARDS
~~~

Default off until P0 acceptance criteria pass.

Customized Insights time-range fixes may ship independently if backward compatible.

---

## 45. P0 implementation scope

P0 should already be useful enough to replace most day-to-day Commercial dashboard usage for internal teams.

### Analytics Engine

- canonical AnalyticsQuery V2;
- viewer ACL;
- multi-project scope;
- structured filters;
- time presets/custom range;
- date basis;
- date grouping incl. quarter;
- Work item count;
- Estimate points;
- Pending;
- Completed;
- In progress;
- Due today;
- Due this week;
- Blocked;
- Overdue;
- Unassigned;
- normalization;
- full-credit/split-equal allocation;
- drill-down;
- batch dashboard data endpoint.

### Customized Insights

- activate time range;
- re-enable Estimate points;
- display Value / % / Value+%;
- normalization;
- allocation;
- date grouping;
- save to dashboard.

### Dashboard

- list/create/update/delete;
- multi-project source;
- dashboard filters;
- private/workspace visibility;
- grid;
- drag/drop;
- resize;
- view/edit mode;
- built-in templates;
- favorite;
- duplicate.

### P0 widgets

- Number
- Bar basic/stacked/grouped
- Line basic/multi-line
- Pie
- Donut basic/progress
- Work item statistics
- Smart counter
- Smart gauge
- Matrix table
- Work Items Table
- Assigned to current user
- Text/Markdown

### Export

- CSV per applicable widget.

---

## 46. P1 implementation scope

- Area basic/stacked/comparison;
- reusable previous-period comparison;
- completion rate;
- throughput;
- average/median cycle time;
- average/median lead time;
- progress by work item type;
- project cycle progress;
- workspace cycle progress;
- member sharing View/Edit;
- chart PNG export;
- dashboard PDF export;
- logged-time metrics where Time Tracking is available;
- additional dashboard templates.

---

## 47. P2 implementation scope

Commercial/Enterprise parity extras and optional extensions:

- Intake accepted vs declined;
- average time to accept/decline;
- Intake breakdown;
- Intake ageing;
- anonymous publish link;
- link regeneration;
- optional link expiry;
- publish audit events;
- advanced style/color controls;
- custom dashboard template management;
- richer API for external agents;
- agent-created dashboards;
- custom-property dimensions after performance validation.

---

## 48. Agent/API readiness

Do not embed an LLM dependency in dashboard core.

The dashboard API must be declarative enough that an external agent can create a dashboard by generating valid config.

Example future flow:

~~~text
User:
"Create a Design workload dashboard for this quarter,
group products by label and split estimate points by assignee."

GoClaw / agent
    -> generate AnalyticsQuery/widget configs
    -> POST dashboard
    -> POST widgets
~~~

No OpenAI-specific provider dependency is needed inside Plane.

Service tokens may use these endpoints subject to their scopes and ACL model.

---

## 49. Testing requirements

### 49.1 Unit tests

- time preset resolution;
- quarter boundaries;
- normalization math;
- split allocation;
- full-credit allocation;
- multi-assignee;
- multi-label warning;
- comparison period resolution;
- metric registry validation;
- dimension registry validation.

### 49.2 API tests

- dashboard CRUD;
- widget CRUD;
- favorite;
- duplicate;
- private/workspace visibility;
- sharing;
- ACL intersection;
- batch partial failure;
- drill-down parity with aggregate;
- export ACL.

### 49.3 ACL regression tests

Construct:

- public project A;
- private project B;
- private project C;
- User X sees A+B;
- User Y sees A+C.

For the same dashboard:

- X totals derive only from A+B;
- Y totals derive only from A+C;
- neither response reveals the hidden project in schema, totals, percentages, labels, facets, drill-down, CSV, or error metadata.

### 49.4 Workload tests

10-point issue assigned to A+B:

Full credit:

~~~text
A = 10
B = 10
~~~

Split equal:

~~~text
A = 5
B = 5
~~~

The raw issue remains one issue in drill-down.

### 49.5 Time tests

An item:

~~~text
created_at   = Jul 10
completed_at = Sep 12
~~~

For September:

- created_at basis -> excluded;
- completed_at basis -> included;
- lifecycle_overlap -> included.

### 49.6 Frontend tests

- edit/view mode;
- drag/resize persistence;
- time range inheritance;
- widget override;
- percentage display;
- matrix row/column totals;
- save insight to dashboard;
- current-user dynamic filter;
- mobile stacking;
- empty/error states.

---

## 50. Acceptance criteria

P0 is complete when all of the following are true:

1. A workspace user can create a dashboard from one or more projects.
2. The same dashboard renders only data the current viewer can access.
3. A user can select This quarter or a custom time range and see all inheriting widgets update.
4. Customized Insights can show Label x Assignee.
5. Metric can be Work item count or Estimate points.
6. Display can be Value, Percentage, or Value + Percentage.
7. Normalization can answer both:
   - "Who contributes to this product?"
   - "Where is this assignee's workload allocated?"
8. Split-equal allocation correctly handles multi-assignee work.
9. A configured Customized Insight can be saved as a dashboard widget.
10. Dashboard widgets can be dragged and resized.
11. Dashboard supports Number, bar/stacked/grouped, line, pie/donut, matrix, statistics/counter/gauge, and work-item table.
12. Aggregate cells/chart segments support drill-down to matching work items.
13. Dashboard and widget filters compose by intersection.
14. CSV export uses the exact same ACL-filtered values displayed on screen.
15. Existing Workspace Analytics continues to function during migration.
16. No tested ACL side channel exposes hidden project information.

---

## 51. Recommended implementation order

### Phase A — Analytics correctness

1. Add Analytics V2 types.
2. Implement ACL-safe base queryset.
3. Implement time-scope resolver.
4. Implement metric registry.
5. Implement dimension registry.
6. Implement aggregation.
7. Implement allocation.
8. Implement normalization.
9. Implement drill-down.
10. Add API tests.

### Phase B — Customized Insights

1. Re-enable duration selector.
2. Move Customized Insights to V2.
3. Re-enable Estimate points.
4. Add percentage/normalization.
5. Add allocation selector.
6. Add date grouping.
7. Add drill-down.
8. Add Save to dashboard.

### Phase C — Dashboard core

1. Models/migrations.
2. CRUD API.
3. dashboard list route.
4. dashboard detail route.
5. responsive grid.
6. edit/view mode.
7. project/filter/time header.
8. widget CRUD/layout persistence.
9. batch data endpoint.

### Phase D — Widgets

1. Number.
2. Bar.
3. Line.
4. Pie/Donut.
5. Matrix.
6. Work Items Table.
7. Statistics.
8. Smart Counter.
9. Smart Gauge.
10. Assigned to current user.
11. Markdown.

### Phase E — Management features

1. Templates.
2. Favorites.
3. Duplicate.
4. Comparison.
5. Progress widgets.
6. Cycle widgets.
7. Sharing.
8. PDF/PNG export.

### Phase F — Commercial parity extras

1. Intake widgets.
2. Anonymous publishing.
3. Advanced styling.
4. Agent/API polish.

---

## 52. Explicit non-goals for P0

P0 does not require:

- a separate OLAP database;
- ClickHouse;
- Elasticsearch;
- arbitrary SQL;
- user-defined formulas;
- custom dashboard JavaScript;
- LLM-generated insights;
- forecasting;
- employee performance scoring;
- inferred work hours;
- historical snapshot reconstruction that Plane does not have source data to support.

The design should leave room for these where appropriate without blocking P0.

---

## 53. Key product decisions

The implementation should treat these as resolved unless new source-code constraints require revision:

1. Dashboards are a new workspace feature, not a renamed Analytics tab.
2. Customized Insights is the ad-hoc builder and can save to dashboards.
3. One Analytics V2 engine serves both.
4. Time range is first-class.
5. Workload and duration are separate concepts.
6. Estimate points are supported.
7. Multi-assignee workload can be split equally.
8. Percentage normalization is first-class.
9. Matrix/cross-tab is first-class.
10. Drill-down is required for trust/explainability.
11. ACL filtering happens before every aggregation.
12. Public anonymous publishing is not enabled by default in the CE fork.
13. AI is external/optional; dashboard core stays deterministic.
