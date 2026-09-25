# Timeline scale semantics

Status: P0 implementation spec  
Target: Plane CE fork v1.4.2, `master`

## Problem

Timeline scale names currently describe the grid granularity, but the visible viewport covers a much larger rolling range. In practice:

- Week feels closer to a month.
- Month feels closer to a quarter.
- Quarter feels closer to a year.
- Too few time columns are visible, so short tasks are compressed and difficult to inspect or drag accurately.
- Centering the current date causes Month and Quarter to cross calendar boundaries instead of presenting one coherent calendar period.

This is different from the planning mental model used by Trello/Notion-style timelines, where the selected scale should remain visually close to the period named by the control.

## UX invariant

The selected scale defines the primary visible planning window, not merely the label density.

| Scale | Primary visible window | Left-edge anchor | Primary columns |
| --- | --- | --- | --- |
| Day | ~5 days | selected day | days |
| Week | 7 days | configured start of week | days |
| Month | one calendar month | day 1 | **days** |
| Quarter | one calendar quarter | first day of quarter | **week-sized chunks** |

Generated dates may extend beyond this visible window as an off-screen buffer for panning and infinite range expansion. Generated range and visible range are intentionally separate concepts.

## Responsive density

The timeline canvas width is the scroll container width minus the sticky properties/sidebar width.

For each scale:

```
dayWidth = timelineViewportWidth / targetDays
```

with readability clamps:

| Scale | Minimum day width | Maximum day width |
| --- | ---: | ---: |
| Day | 120 px | 240 px |
| Week | 88 px | 180 px |
| Month | 24 px | 64 px |
| Quarter | 8 px | 24 px |

Target days are:

- Day: 5
- Week: 7
- Month: actual number of days in the selected month
- Quarter: actual number of days in the selected calendar quarter

This means a normal desktop viewport shows approximately one semantic period, while smaller screens overflow horizontally rather than compressing columns below usable widths.

### Grid hierarchy

The selected scale controls the default viewport, but it must not throw away lower-level detail:

- **Month:** render one column per calendar day. Do not collapse the body/grid into week columns.
- **Quarter:** render week-sized subdivisions inside each month. Do not collapse the body/grid into one column per month.
- Task bars remain day-based in every scale, so drag/resize precision never becomes coarser than one day.

## Interactive zoom

Timeline supports continuous pixel zoom without changing the selected Day/Week/Month/Quarter mode.

Controls:

- toolbar **Zoom out / Zoom in** buttons
- mouse wheel directly over the sticky time-axis header
- `Ctrl + wheel` / `Cmd + wheel` anywhere in the timeline canvas; this also supports trackpad pinch gestures that arrive as modifier-wheel events

Behavior:

- zoom changes `dayWidth` only; it does not mutate dates or switch scale mode
- zoom is anchored under the mouse pointer; the date under the pointer should remain visually stable
- toolbar zoom anchors around the center of the visible timeline
- ordinary wheel scrolling in the task body remains native so long work-item lists are still easy to scroll
- zoom limits prevent unusably tiny or excessively large cells

Zoom bounds:

| Scale | Min day width | Max day width |
| --- | ---: | ---: |
| Day | 64 px | 320 px |
| Week | 32 px | 240 px |
| Month | 18 px | 120 px |
| Quarter | 4 px | 48 px |

## Calendar-boundary anchoring

When a scale is selected or Today is pressed:

- Day anchors to the selected day.
- Week anchors to the user's configured start-of-week.
- Month anchors to the first day of the month.
- Quarter anchors to the first day of the calendar quarter.

Do not center the selected date for Month/Quarter. Centering creates rolling windows such as Aug 15 → Sep 15 and defeats the meaning of Month.

## Render buffers

Initial/off-screen generated ranges are reduced to avoid multi-year DOM payloads while leaving enough room to pan:

- Day: 1 month buffer unit
- Week: 1 month buffer unit
- Month: 2 month buffer units
- Quarter: 3 month buffer units

Quarter left/right expansion must operate in whole 3-month chunks; fractional month expansion is prohibited.

## Interaction compatibility

This change must not alter task scheduling semantics:

- Task drag still snaps using `dayWidth`.
- Resize still maps pixels to whole calendar days.
- Background pan remains independent from task drag.
- Range prepend must preserve viewport position.
- The sticky properties pane remains outside the semantic timeline width calculation.
- Today must use the actual current date at click time.

## Acceptance criteria

- [ ] Week opens with one configured calendar week occupying approximately the timeline viewport.
- [ ] Month opens at day 1, exposes the whole selected month, and renders **every day as its own column**.
- [ ] Quarter opens at the first month of the quarter, exposes exactly that quarter, and renders **week-sized subdivisions** rather than month-only columns.
- [ ] Month/Quarter no longer open as rolling date-centered windows.
- [ ] Small screens overflow horizontally instead of shrinking below minimum readable widths.
- [ ] Large generated buffers are not mistaken for the visible planning window.
- [ ] Today re-anchors to the real current period.
- [ ] Existing task drag/resize date calculations remain unchanged.
- [ ] Existing infinite left/right range extension remains functional.
- [ ] Zoom buttons adjust timeline density without changing scale mode.
- [ ] Wheel over the time header zooms in/out.
- [ ] Ctrl/Cmd + wheel zooms from the pointer position inside the timeline.
- [ ] Normal wheel scrolling in the task body remains available.
- [ ] Unit tests cover period boundaries, target day counts, responsive density, and zoom bounds.

## Follow-up

Year scale is intentionally not added in this patch. If introduced later, it should follow the same invariant: one calendar year as the primary visible window, anchored on January 1, with month-level headers.
