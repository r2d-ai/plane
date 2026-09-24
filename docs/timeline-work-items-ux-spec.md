# Timeline / Gantt UX Improvements Specification

**Status:** Approved for implementation  
**Target branch:** `preview`  
**Scope:** Work Items Timeline / Gantt UX  
**Priority:** P0 first  
**Last updated:** 2026-09-25

---

## 1. Objective

Improve Plane CE Timeline so it is practical for day-to-day production planning, not only high-level roadmap viewing.

The implementation must keep the existing Plane visual language and reuse the current filters, grouping metadata, work-item stores, Gantt drag/resize logic, and date model wherever possible.

The P0 outcome must provide:

1. Canvas-style **drag-to-pan** for the timeline.
2. **One scroll owner only** for the Gantt body; remove the current nested-scroll UX.
3. Timeline scales: **Day / Week / Month / Quarter**.
4. Existing task move/resize interactions preserved and date-snapped.
5. **Single-select Group by** with multiple supported dimensions.
6. Configurable left-side properties/columns.
7. Assignee avatar/name visible on timeline bars.
8. Stable sticky header/sidebar behavior while panning and scrolling.

This spec is intentionally focused on Timeline/Gantt. It does not redesign List, Kanban, Spreadsheet, or Calendar.

---

## 2. Current baseline and problems

Relevant current implementation on `preview`:

- `apps/web/core/components/issues/issue-layouts/gantt/base-gantt-root.tsx`
  - fetches work items using `canGroup: false`
  - flattens the Timeline to `ALL_ISSUES`
- `apps/web/core/components/gantt-chart/chart/main-content.tsx`
  - `#gantt-container` is already an `overflow-auto` container
  - owns horizontal and vertical Gantt scrolling
- project layout body also uses an overflowed container, causing nested scrolling in Gantt
- `apps/web/core/components/gantt-chart/chart/timeline-drag-helper.tsx`
  - currently supports DnD auto-scroll only
  - it is **not** canvas drag-to-pan
- `apps/web/core/components/gantt-chart/sidebar/root.tsx`
  - left header is effectively hard-coded to Work Items + Duration
- current timeline helpers expose only:
  - Week
  - Month
  - Quarter
- `apps/web/core/components/issues/issue-layouts/utils.tsx` already contains group metadata for:
  - project
  - cycle
  - module
  - state
  - state group
  - priority
  - labels
  - assignees
  - created by

The implementation should reuse this infrastructure instead of introducing a parallel grouping system.

### UX problems to solve

1. Users must currently rely on scrollbars to navigate a large timeline.
2. Nested scroll containers make the two scrollbars difficult to use.
3. The lowest zoom level is not sufficient for short 1–5 day production tasks.
4. Timeline rows provide too little task metadata.
5. Timeline cannot be visually grouped by the dimensions teams already use in Plane.

---

# 3. P0 requirements

## P0.1 — Drag-to-pan Timeline

**This is a mandatory P0 feature.**

The user must be able to click/press on unused chart space and drag the timeline like a canvas/map.

### Required interactions

| Gesture | Result |
|---|---|
| Primary-button drag on empty timeline area | Pan timeline horizontally and vertically |
| `Space + primary-button drag` anywhere inside chart | Force pan mode, including when pointer starts on a task |
| Trackpad two-axis scroll | Preserve native horizontal + vertical scrolling |
| Mouse wheel | Vertical scroll |
| Shift + mouse wheel | Horizontal scroll |
| Drag task body | Move task dates; must not pan |
| Drag task left/right resize handle | Resize dates; must not pan |
| Drag sidebar splitter | Resize left properties pane; must not pan |

### Pointer interaction priority

Highest priority wins:

```text
task resize handle
    >
sidebar splitter
    >
Space + drag (force pan)
    >
task body drag
    >
empty chart drag (pan)
```

`Space + drag` intentionally overrides task-body move so a user can pan even when a long task covers most of the visible chart.

### Pan behavior

On pan start, capture:

```ts
startPointerX
startPointerY
startScrollLeft
startScrollTop
```

During movement:

```ts
scrollLeft = startScrollLeft - deltaX
scrollTop  = startScrollTop  - deltaY
```

Implementation requirements:

- use Pointer Events
- use pointer capture during active pan
- use a small movement threshold (recommended 3–5 px) before entering dragging state
- after threshold, prevent accidental text selection/click activation
- update scrolling directly or through `requestAnimationFrame`; no CSS transform-based fake scrolling
- `cursor: grab` over pannable chart background
- `cursor: grabbing` while panning
- release state on `pointerup`, `pointercancel`, lost pointer capture, and component unmount
- do not hijack browser-level Ctrl/Cmd + wheel zoom
- do not block native trackpad scrolling

### Acceptance criteria

- A user can navigate a multi-month timeline without touching the horizontal scrollbar.
- Panning feels 1:1 with pointer movement and does not visibly lag.
- Panning does not move or resize tasks.
- Moving/resizing tasks does not accidentally pan.
- Holding Space always provides a reliable escape hatch into pan mode.
- Panning near generated timeline boundaries continues to work as the range expands.

---

## P0.2 — Single scroll owner

There must be exactly **one scroll owner for the Gantt body**.

### Required structure

```text
Project/Work Item layout
└── Gantt layout wrapper       overflow: hidden
    └── #gantt-container      overflow: auto   <-- only Gantt body scroll owner
        ├── sticky properties/sidebar
        └── timeline
```

For non-Gantt layouts, existing overflow behavior can remain unchanged.

### Requirements

- do not create a second horizontal scrollbar for the left properties pane
- do not create a second vertical scrollbar for the sidebar
- sidebar and timeline use the same vertical scroll position
- time header stays sticky while scrolling vertically
- left properties pane stays sticky while scrolling horizontally
- top-left properties header remains visually aligned with the time header
- scrollbar remains available for accessibility and conventional navigation, but is no longer the primary navigation mechanism
- use `overscroll-behavior` as appropriate so Gantt scrolling does not unexpectedly chain to the page

### Expected layout behavior

```text
                         horizontal pan/scroll →
┌──────────────────────────────┬────────────────────────────────────
│ Work item  Status  Assignee  │ Sep 14  15  16  17  18  19 ...
├──────────────────────────────┼────────────────────────────────────
│ ▼ VHT2026                    │
│ ART-5 ...     Doing  [A]     │       ███████████
│ ART-18 ...    Todo   [B]     │             █████████████
│ ART-15 ...    Done   [C]     │                       ███
└──────────────────────────────┴────────────────────────────────────
       sticky left                       scrollable
```

---

## P0.3 — Day / Week / Month / Quarter scale

The Timeline scale selector must support:

```text
Day
Week
Month
Quarter
```

### Day is mandatory

"Day" means **calendar-day resolution**, not hourly scheduling.

Plane work items currently use date-only `start_date` and `target_date`; P0 must keep this model.

### Scale semantics

| Scale | Intended use | Visual density |
|---|---|---|
| Day | daily production scheduling, 1–5 day tasks | large day cells |
| Week | several weeks of execution planning | medium day cells grouped by week |
| Month | 1–3 month planning | compact days grouped by month |
| Quarter | longer roadmap | compact week/month-oriented rendering |

Recommended Day cell width: approximately 100–140 px, responsive to implementation constraints.

### Required common behavior

- Today is clearly highlighted.
- Saturday/Sunday receive a subtle distinct background.
- `Today` action centers the current date.
- time header remains sticky.
- task positions stay stable when switching scale.
- task move and resize remain **one-calendar-day snapped** on every scale.
- no fractional dates are introduced.

### Code direction

Current helper mapping:

```ts
{
  week,
  month,
  quarter
}
```

must become conceptually:

```ts
{
  day,
  week,
  month,
  quarter
}
```

Do not duplicate all date-position logic four times if avoidable. Extract/share common scale logic for:

- date → x position
- x position → date
- snap interval
- generated visible range
- header grouping
- cell width
- prepend/append range behavior

Update all `TGanttViews`-related types/constants/UI/i18n.

---

## P0.4 — Existing task drag and resize must remain first-class

Existing Gantt task movement and resizing must be preserved.

### Task body drag

Dragging a scheduled task horizontally changes dates while preserving its duration.

Example:

```text
Before: 12 Oct → 16 Oct
drag +3 days
After:  15 Oct → 19 Oct
```

### Edge resize

- left edge changes `start_date`
- right edge changes `target_date`
- minimum duration remains valid according to current Plane semantics
- result snaps to calendar day boundaries

### Auto-scroll while manipulating a task

Existing DnD auto-scroll behavior should remain, but it must work with the new single-scroll-owner structure.

Dragging a task near left/right/top/bottom edges should auto-scroll the Gantt container without requiring scrollbar interaction.

### Do not conflate two concepts

- **pan** = move viewport
- **task drag** = modify task dates

Keep these as separate hooks/interaction states.

The current `TimelineDragHelper` is an auto-scroll helper for task DnD. Prefer keeping that responsibility and adding a separate hook/component such as `useTimelinePan()` rather than overloading the existing helper.

---

# 4. P0 grouping

## 4.1 Single active group dimension

Timeline can be grouped by **one and only one** dimension at a time.

P0 does not implement sub-grouping.

### Required options

At project level:

```text
None
Module
Cycle
Label
Assignee
Status
Priority
```

At workspace-level timelines, `Project` may additionally be exposed when applicable.

Availability should respect project features where relevant:

- Module only when module functionality/data is applicable
- Cycle only when cycle functionality/data is applicable

### UI

Recommended control:

```text
Group: Module ▾
```

Menu:

```text
Group by
──────────────
● None
○ Module
○ Cycle
○ Label
○ Assignee
○ Status
○ Priority
```

The setting should reuse Plane's existing `display_filters.group_by` model where possible.

Do not add a separate incompatible grouping state if the existing filter/view infrastructure can represent it.

---

## 4.2 Group rendering

Example, grouped by Module:

```text
▼ VHT2026                                      12
  ART-5   Vượt Ải Thẻ Bài
  ART-18  Hộp Quà May Mắn
  ART-15  Hóa Thân Otama

▶ M3                                            6

▶ EP11 - HTMN                                   4

▼ No module                                     2
  ...
```

### Requirements

- group header spans both left properties area and timeline area
- group header shows:
  - expand/collapse affordance
  - group label
  - item count
- collapsed group removes its work-item rows from both panes
- row alignment between properties pane and timeline must remain exact
- group headers are presentation rows, **not fake work items**
- empty groups should not create visual noise; honor existing `show_empty_groups` behavior if it is already exposed and usable, otherwise default Timeline behavior should hide empty groups

---

## 4.3 Multi-value group semantics

Plane allows multi-value relationships such as:

- labels
- assignees
- modules through `ModuleIssue`

A work item belonging to multiple values appears in every matching visual group.

Example:

```text
Task A
labels = [UI, Event]
```

renders:

```text
UI
  Task A

Event
  Task A
```

This is **presentation duplication only**. There remains exactly one underlying work item.

### Ungrouped value

Items without a value render under:

- No module
- No cycle
- No label
- Unassigned
- etc.

Use terminology appropriate to the property and existing i18n conventions.

### Dragging across groups

P0 must **not** infer mutation semantics from vertical drag between multi-value groups.

For example, dragging a task from Module A to Module B is ambiguous:

- remove Module A and add Module B?
- keep Module A and add Module B?

Therefore:

- horizontal task drag continues to change dates
- cross-group property mutation by vertical drag is **out of P0**
- do not silently change module/label/assignee membership from row movement

A later phase can add explicit "Move to" / "Add to" semantics where safe.

---

# 5. Presentation row model

The current Gantt flow is heavily based on `blockIds[]`. Grouping, collapse, and multi-value grouping require a separate presentation-row identity.

Introduce a conceptual row model similar to:

```ts
type TimelineGroupRow = {
  type: "group";
  rowId: string;
  groupId: string;
  label: string;
  count: number;
  collapsed: boolean;
};

type TimelineIssueRow = {
  type: "issue";
  rowId: string;
  issueId: string;
  groupId?: string;
};

type TimelineRow = TimelineGroupRow | TimelineIssueRow;
```

### Important identity rule

`rowId` and `issueId` are not interchangeable.

For a multi-value grouped issue:

```ts
{ rowId: "label-ui:issue-123", issueId: "issue-123" }
{ rowId: "label-event:issue-123", issueId: "issue-123" }
```

Both rows mutate the same issue.

### Requirements

- React keys use `rowId`
- DOM ids must remain unique; do not generate duplicate `id="gantt-block-issue-123"` for duplicated presentation rows
- update/move/resize operations use `issueId`
- timeline store can continue to keep entity/block data keyed by the underlying issue where practical
- group rows must not be inserted into the work-item block store as fake entities
- duplicated visual rows must not result in duplicated API mutations

### Dependency behavior

Existing dependency features must not crash when an issue has multiple presentation rows.

P0 does not require redesigned cross-group dependency visualization. If unique dependency handle semantics cannot be guaranteed for duplicated rows, dependency handles/connectors may be suppressed for duplicate occurrences while preserving normal behavior in ungrouped/single-occurrence cases.

---

# 6. Left properties pane / configurable columns

Replace the current conceptual:

```text
Work items                       Duration
```

with a configurable Timeline properties table.

### Required P0 properties

- Work item — always visible
- Status
- Assignee
- Duration
- Priority
- Module
- Labels
- Start date
- Due date / Target date
- Estimate, when available

Recommended default:

```text
Work item | Status | Assignee | Duration
```

### Requirements

- Work item column cannot be hidden
- user can show/hide optional columns through a `Columns` or `Display` control
- reuse existing issue-property renderers where practical
- values truncate cleanly with tooltip/details on demand
- no separate horizontal scrollbar inside the properties pane
- overall properties pane is resizable with a splitter
- use sane min/max width, recommended approximately:
  - min: 320 px
  - default: 420–480 px after extra properties are enabled
  - max: 720 px
- table must stay aligned 1:1 with Timeline rows
- group row spans/represents the group across the properties section

Column reorder and advanced per-column sizing are useful but are not required to block P0 unless implementation naturally supports them.

---

# 7. Assignee on Timeline task bars

Timeline bars should expose ownership without opening a work item.

### Adaptive rendering

Recommended behavior:

| Available bar width | Assignee rendering |
|---|---|
| very narrow | avatar only |
| medium | avatar + short/display name if space allows |
| wide | task title + avatar + display name |
| multiple assignees | up to 2 avatars, then `+N` |

### Requirements

- do not let assignee rendering make the task title completely unusable
- keep title priority on normal/wide bars
- full assignee information available by tooltip/popover
- use existing Plane avatar/member components
- preserve current work-item preview/click behavior
- status does not need extra text on the bar if current state color already communicates it; avoid visual noise

Example:

```text
████ EP00 - UI Event Login                    [avatar] Tiến
```

---

# 8. Toolbar / controls

Keep the toolbar compact and consistent with Plane.

Recommended conceptual layout:

```text
Timeline     Today    ‹  ›    [ Day ▾ ]

Group: Module ▾      Columns ▾      Filter ▾
```

Do not expose every setting as a separate top-level button.

A `Display` menu is also acceptable if it better matches the current Plane UI:

```text
Display
  Scale        Day >
  Group by     Module >
  Columns      4 shown >
```

Existing Filter behavior must remain intact.

---

# 9. Sticky and scrolling behavior

Required:

- left properties pane: `position: sticky; left: 0`
- time header inside Gantt: sticky vertically
- top-left properties header stays above body rows
- z-index layering must prevent bars/grid from painting over the sticky sidebar
- group headers must align across panes
- opening popovers/dropdowns must not be clipped by the single scroll container

Be especially careful with stacking contexts introduced by transforms; avoid transforms on large sticky ancestors when possible.

---

# 10. Timeline range extension while panning

The current chart extends generated ranges when scrolling near left/right edges.

This behavior must continue to work with drag-to-pan.

### Requirements

- panning left/right can trigger range generation
- prepend must preserve the user's perceived viewport position; no visible "jump" after adding earlier dates
- append/prepend calls must be guarded against repeated firing while a previous expansion is being applied
- no infinite render/update loop when user holds the pointer near an edge
- switching Day/Week/Month/Quarter must recalculate a sensible generated range around the current focal date

A direction lock or in-flight guard for left/right expansion is recommended.

---

# 11. State and persistence

Prefer existing Plane view/filter persistence.

### Group

Reuse:

```text
display_filters.group_by
```

where compatible.

Gantt P0 uses one group value and ignores sub-grouping.

### Visible properties

Reuse existing `displayProperties` booleans where possible.

### Gantt-specific UI preferences

Potential preferences:

- scale: day/week/month/quarter
- properties pane width
- visible columns not represented by current display properties
- optional collapse state

Prefer an optional Gantt-specific JSON sub-object inside existing user/view preference storage rather than a new relational schema.

A relational database migration should **not** be introduced merely for UI preferences unless existing persistence APIs make JSON extension impossible.

Collapse state may remain session/client state in P0 if persistent collapse materially complicates the implementation.

---

# 12. Recommended component architecture

Conceptual target:

```text
BaseGanttRoot
│
├── filters/view settings
├── grouping adapter
│    └── TimelineRow[]
│
└── GanttChartRoot
     │
     ├── toolbar
     │
     └── GanttChartMainContent
          │
          └── #gantt-container   <-- sole scroll owner
               │
               ├── TimelinePropertiesPane
               │    ├── header
               │    ├── group row
               │    └── issue row
               │
               └── TimelineCanvas
                    ├── time header
                    ├── grid
                    ├── group row
                    └── issue bars
```

Recommended hooks/responsibilities:

```text
useTimelinePan()
  - background pointer pan
  - Space override
  - pointer capture/lifecycle

TimelineDragHelper / existing auto-scroll helper
  - task DnD edge auto-scroll only

timeline scale helpers
  - date/position calculations

grouping adapter
  - group data -> TimelineRow[]
```

Do not couple viewport panning to task mutation state more than necessary.

---

# 13. Primary code touchpoints

Expected files/areas to inspect or modify:

### Layout / scroll ownership

- `apps/web/core/components/issues/issue-layouts/roots/project-layout-root.tsx`
- other roots that host Gantt and may wrap it in `overflow-auto`

### Gantt issue root / grouping

- `apps/web/core/components/issues/issue-layouts/gantt/base-gantt-root.tsx`
- `apps/web/core/components/issues/issue-layouts/utils.tsx`
- issue filter stores and display-filter helpers

### Gantt chart

- `apps/web/core/components/gantt-chart/root.tsx`
- `apps/web/core/components/gantt-chart/chart/root.tsx`
- `apps/web/core/components/gantt-chart/chart/main-content.tsx`
- `apps/web/core/components/gantt-chart/chart/timeline-drag-helper.tsx`
- `apps/web/core/components/gantt-chart/sidebar/root.tsx`
- `apps/web/core/components/gantt-chart/sidebar/issues/*`
- `apps/web/core/components/gantt-chart/blocks/*`
- `apps/web/core/components/gantt-chart/views/*`
- `apps/web/core/components/gantt-chart/constants.ts`

### Issue bar/sidebar rendering

- `apps/web/core/components/issues/issue-layouts/gantt/blocks.tsx`

### Types/i18n

- `TGanttViews` and related type definitions
- scale constants
- locale strings for Day, grouping labels, columns, no-value groups, and pan-related UI text if any

This list is a starting point, not a requirement to force all changes into these files.

---

# 14. P0 implementation sequence

Implement in this order to reduce interaction regressions.

## Phase 0A — Scroll and pan foundation

1. Make `#gantt-container` the sole Gantt body scroll owner.
2. Remove outer nested Gantt scrolling.
3. Verify sticky sidebar + sticky time header.
4. Implement `useTimelinePan()`.
5. Implement empty-area pan and `Space + drag`.
6. Verify native wheel/trackpad behavior.
7. Verify task drag/resize and current DnD auto-scroll still work.

**Do not proceed to complex grouping until this is stable.**

## Phase 0B — Day scale

1. Add Day to types/constants.
2. Add Day scale generator/view.
3. Extract shared date-position logic where useful.
4. Verify Today, prepend/append, move, resize, dependencies, and pan on Day.
5. Regression test Week/Month/Quarter.

## Phase 0C — Grouping row model

1. Introduce presentation `TimelineRow`.
2. Add single-select group state using existing display filters.
3. Reuse existing group metadata.
4. Implement group headers/collapse.
5. Implement multi-value visual duplication using unique `rowId`.
6. Verify no duplicate API mutation.

## Phase 0D — Properties and assignee presentation

1. Replace hard-coded Duration header with column configuration.
2. Add default Status / Assignee / Duration columns.
3. Add optional properties.
4. Add properties-pane splitter.
5. Add adaptive assignee rendering on bars.
6. Verify tooltip/popover/peek behavior.

## Phase 0E — Persistence and polish

1. Persist scale/group/visible columns using existing preferences.
2. Ensure i18n.
3. Keyboard/pointer accessibility pass.
4. Performance/regression pass.

---

# 15. P0 acceptance test matrix

## Navigation

- [ ] Gantt body exposes only one effective scroll container.
- [ ] No nested horizontal scrollbar is required to use Timeline.
- [ ] Empty-space drag pans horizontally.
- [ ] Empty-space drag pans vertically.
- [ ] Space + drag pans when starting on a task.
- [ ] Trackpad scroll remains native.
- [ ] Shift + wheel can navigate horizontally.
- [ ] Sticky sidebar remains visible during horizontal pan.
- [ ] Time header remains visible during vertical scroll.

## Time scale

- [ ] Day option exists.
- [ ] Week option remains functional.
- [ ] Month option remains functional.
- [ ] Quarter option remains functional.
- [ ] Today centers correctly in every scale.
- [ ] Weekend styling is correct.
- [ ] Scale switch does not mutate task dates.
- [ ] No fractional date values are produced.

## Task manipulation

- [ ] Task body drag moves dates.
- [ ] Left resize changes start date.
- [ ] Right resize changes target date.
- [ ] Drag/resize snaps to calendar day.
- [ ] DnD auto-scroll still works.
- [ ] Pan never silently mutates task dates.
- [ ] Task drag never unintentionally pans.

## Grouping

- [ ] Group = None works.
- [ ] Group by Module works.
- [ ] Group by Cycle works.
- [ ] Group by Label works.
- [ ] Group by Assignee works.
- [ ] Group by Status works.
- [ ] Group by Priority works.
- [ ] Only one group dimension is active.
- [ ] No-value group is rendered correctly.
- [ ] Multi-label item appears in every matching label group.
- [ ] Multi-assignee item appears in every matching assignee group.
- [ ] Multi-module item appears in every matching module group.
- [ ] Duplicate presentation rows still reference one underlying issue.
- [ ] Group collapse keeps sidebar/chart row alignment exact.

## Properties

- [ ] Work Item is always visible.
- [ ] Status can be shown.
- [ ] Assignee can be shown.
- [ ] Duration can be shown.
- [ ] Priority can be shown.
- [ ] Module can be shown.
- [ ] Labels can be shown.
- [ ] Start/Target dates can be shown.
- [ ] Properties pane can be resized.
- [ ] Properties pane does not introduce another scrollbar.

## Timeline bar

- [ ] Assignee avatar is visible when space allows.
- [ ] Name is visible on wider bars.
- [ ] Multiple assignees render compactly.
- [ ] Narrow bars remain readable/clickable.
- [ ] Existing preview/peek action still works.

## Performance / stability

- [ ] 100+ loaded work items remain usable while panning.
- [ ] Pan does not cause React state update per pixel unless required.
- [ ] Repeated range extension is guarded.
- [ ] No viewport jump when prepending dates.
- [ ] No duplicate DOM ids from multi-group presentation rows.
- [ ] No duplicate update API calls caused by duplicated rows.

---

# 16. Accessibility and keyboard behavior

P0 must not make Timeline mouse-only.

- scrollbar/native scrolling remains available
- task controls keep keyboard accessibility already provided by Plane
- Space-to-pan shortcut only applies while the Gantt region is focused/active and must not intercept typing in inputs, textareas, editors, or popovers
- cursor changes are supplemental, not the only state indicator
- column/group controls use normal focusable controls
- collapsed group headers expose expanded/collapsed state to assistive technology where practical

---

# 17. Performance constraints

- avoid recomputing all group rows on every pointer move
- pan should primarily mutate container scroll position, not global MobX state
- memoize/group row derivation based on issue/group data
- maintain existing visibility virtualization (`RenderIfVisible`) where possible
- duplicated presentation rows must not duplicate work-item data objects unnecessarily
- do not create a large global event listener per row
- one Gantt-level pointer-pan listener/hook is preferred

---

# 18. Explicit non-goals for P0

The following should **not** delay P0:

- Group + Sub-group
- arbitrary multi-level grouping
- hourly timeline
- cross-group drag that mutates module/label/assignee
- custom-field grouping
- complete dependency visualization redesign
- resource capacity/load charts
- advanced saved Timeline presets
- per-column drag reorder if it materially expands scope
- mobile-specific Timeline redesign

These can be handled in later phases.

---

# 19. Follow-up candidates (P1+)

After P0 is stable:

1. Group + Sub-group similar to Notion.
2. Explicit cross-group actions:
   - Move to
   - Add to
3. Unscheduled section and one-click scheduling.
4. Saved Timeline view presets.
5. Column reorder and detailed per-column widths.
6. Resource planning / workload by assignee.
7. Optional keyboard zoom:
   - `+` zoom in
   - `-` zoom out
8. Middle-button pan if desired.
9. Mobile/tablet gesture-specific Timeline UX.

---

# 20. Definition of done

P0 is done only when the Timeline can be used as the primary planning surface without depending on scrollbar manipulation.

The expected user workflow is:

```text
select Day/Week/Month/Quarter
        ↓
choose one Group by dimension
        ↓
drag the background to navigate the timeline
        ↓
drag/resize tasks to schedule them
        ↓
read ownership/status directly from the row/bar
        ↓
change visible properties without leaving Timeline
```

The key UX invariant is:

> **Dragging empty Timeline space moves the viewport; dragging a task modifies the task.**

If users still need to hunt for one of multiple scrollbars to navigate the chart, the P0 implementation is not complete.
