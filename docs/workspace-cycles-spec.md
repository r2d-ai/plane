# Workspace Cycles — Product & Implementation Spec

Status: Proposed / ready for implementation  
Target branch: `master`  
Scope: Community Edition fork  
Primary goal: Add a workspace-level cycle that gives leaders an ACL-safe overview across projects without changing existing project-cycle semantics.

---

## 1. Problem

Plane cycles are currently project-scoped. The project cycle page is useful because it combines:

- active/upcoming/completed cycle grouping,
- progress distribution,
- burndown,
- priority work items,
- assignees/labels,
- dates and cycle status.

For a workspace leader, this forces project-by-project navigation and prevents a single workspace-wide operational view.

We need a workspace-level cycle that:

1. aggregates cycle data across the projects the viewer is allowed to see;
2. never leaks private project/work-item data through counts, charts, filters, search, cache, or metadata;
3. supports user-created workspace cycles;
4. creates sensible default workspace cycles automatically;
5. keeps project cycles as the execution-level source of truth rather than duplicating work-item assignment.

---

## 2. Product principles

### 2.1 Workspace cycle is an umbrella/reporting cycle

A `WorkspaceCycle` is a workspace-scoped time window used to aggregate project-cycle data.

It does **not** replace project cycles.

It does **not** directly own work items in V1.

It does **not** require users to assign a work item twice.

Existing project `Cycle` + `CycleIssue` remain the source of truth for sprint/iteration membership.

### 2.2 ACL is evaluated at request time

The same workspace cycle may show different totals to different users.

Example:

- Workspace has Project A (public), Project B (private), Project C (private).
- User X can access A + B.
- User Y can access A + C.
- Both open `Q4 2026`.
- X sees only A + B metrics.
- Y sees only A + C metrics.

The workspace cycle object itself is workspace-visible, but all aggregate data is viewer-specific.

### 2.3 Default calendar quarters

Each workspace receives four default workspace cycles per calendar year:

- Q1 YYYY: Jan 01 00:00:00 → Mar 31 23:59:59.999...
- Q2 YYYY: Apr 01 → Jun 30
- Q3 YYYY: Jul 01 → Sep 30
- Q4 YYYY: Oct 01 → Dec 31

Date boundaries are calculated in the workspace timezone and stored normalized to UTC.

Default names:

- `Q1 2026`
- `Q2 2026`
- `Q3 2026`
- `Q4 2026`

### 2.4 Custom workspace cycles are allowed

Workspace Admin/Member roles may create custom workspace cycles, for example:

- `Launch Phase 1`
- `H2 2026`
- `Black Friday 2026`
- `R&D Milestone 3`

Custom cycles may overlap quarterly cycles and other custom cycles.

Overlap is intentional because workspace cycles are reporting/coordination windows, not accounting buckets.

---

## 3. V1 semantics

### 3.1 Which project cycles belong to a workspace cycle?

For V1, a project cycle is included when its **start date** falls inside the workspace cycle window:

```
workspace_cycle.start_date <= project_cycle.start_date <= workspace_cycle.end_date
```

Reason:

- deterministic;
- prevents the same project cycle from appearing in two adjacent default quarters;
- avoids double counting caused by project cycles that cross quarter boundaries;
- requires no extra mapping table;
- keeps migration/backfill simple.

Draft project cycles with no `start_date` are not included in workspace-cycle metrics.

A future version may add explicit project-cycle mapping or alternate aggregation policies, but V1 must keep one predictable rule.

### 3.2 Work-item membership

The workspace-cycle work-item set is the union of active `CycleIssue` rows from included project cycles after ACL filtering.

Pseudo-query:

```python
visible_project_ids = get_accessible_project_ids(request, workspace)

project_cycle_ids = Cycle.objects.filter(
    workspace=workspace,
    project_id__in=visible_project_ids,
    start_date__gte=workspace_cycle.start_date,
    start_date__lte=workspace_cycle.end_date,
    archived_at__isnull=True,
).values_list("id", flat=True)

visible_issue_ids = CycleIssue.objects.filter(
    workspace=workspace,
    project_id__in=visible_project_ids,
    cycle_id__in=project_cycle_ids,
    deleted_at__isnull=True,
    issue__archived_at__isnull=True,
    issue__is_draft=False,
).values_list("issue_id", flat=True).distinct()
```

All workspace-cycle metrics must derive from this ACL-filtered issue/project set.

### 3.3 Deduplication

A work item must be counted once per workspace-cycle response even if malformed legacy data links it to more than one included project cycle.

Use `COUNT(DISTINCT issue_id)` or an equivalent distinct issue set for workspace aggregate totals.

Per-project metrics may count the same issue only in its owning project; cross-project duplication is impossible because an issue belongs to one project.

### 3.4 Projects with cycles disabled

Projects with `cycle_view = false` naturally contribute no project-cycle work items.

The dashboard must expose coverage instead of silently implying complete workspace coverage:

- visible projects;
- visible projects with cycles enabled;
- visible projects contributing at least one project cycle;
- visible work items outside project cycles is optional P1, not required for V1.

---

## 4. ACL and security

This is the most important implementation constraint.

### 4.1 Workspace cycle visibility

Read:

- any active workspace member may list/read workspace cycle metadata.

Create/update/archive/delete:

- Workspace Admin: allowed;
- Workspace Member: allowed;
- Workspace Guest: read-only.

Use existing workspace-role constants and permission patterns.

### 4.2 Project visibility resolver

Do not write a new ad-hoc ACL query inside every endpoint.

Introduce a reusable helper, for example:

```python
get_accessible_project_ids(request, workspace_slug) -> QuerySet[UUID]
```

For human users, V1 behavior must match the project list visibility semantics already used by `ProjectListCreateAPIEndpoint`:

- project membership with `is_active=True`, OR
- public project (`network=2`) inside the workspace.

For service principals:

- respect the service token workspace boundary;
- respect the requested service scope;
- do not create synthetic project memberships;
- workspace-wide tokens may query workspace-cycle aggregates across projects permitted by the token boundary/scopes.

If service-token ACL semantics become more restrictive later, workspace-cycle endpoints must consume the centralized resolver instead of bypassing it.

### 4.3 No aggregate side-channel

A user must not be able to infer inaccessible project data from:

- total work-item counts;
- project counts;
- status counts;
- burndown points;
- priority work items;
- assignee lists;
- labels;
- project names/icons;
- search suggestions;
- filters/facets;
- pagination totals;
- CSV/export endpoints;
- cache keys;
- error messages.

Bad:

```
total_workspace_items = 120
visible_items = 70
```

This leaks that 50 hidden items exist.

Correct:

```
total_items = 70
```

All values are computed **after** ACL filtering.

### 4.4 Cache safety

Never cache workspace-cycle analytics only by:

```
workspace_id + workspace_cycle_id
```

because aggregate output is viewer-dependent.

V1 recommendation: no cross-user aggregate cache.

If caching is introduced later, key by an ACL fingerprint such as:

```
workspace_id
workspace_cycle_id
principal_type
principal_id / service_token_id
visible_project_acl_version
query/filter hash
```

Do not use a cached privileged/admin response for a less privileged viewer.

### 4.5 Object lookup safety

All detail endpoints must scope objects by workspace:

```python
WorkspaceCycle.objects.get(
    id=cycle_id,
    workspace__slug=slug,
    deleted_at__isnull=True,
)
```

Never fetch only by UUID.

---

## 5. Data model

Add a new model. Do not overload the existing project `Cycle` table with nullable project IDs.

Recommended file:

`apps/api/plane/db/models/workspace_cycle.py`

### 5.1 WorkspaceCycle

```python
class WorkspaceCycle(BaseModel):
    class Kind(models.TextChoices):
        QUARTER = "quarter", "Quarter"
        CUSTOM = "custom", "Custom"

    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="workspace_cycles",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    timezone = models.CharField(max_length=255, default="UTC")

    owned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_workspace_cycles",
    )

    kind = models.CharField(
        max_length=32,
        choices=Kind.choices,
        default=Kind.CUSTOM,
    )

    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.USER,
    )

    year = models.PositiveSmallIntegerField(null=True, blank=True)
    quarter = models.PositiveSmallIntegerField(null=True, blank=True)

    sort_order = models.FloatField(default=65535)
    archived_at = models.DateTimeField(null=True, blank=True)
    logo_props = models.JSONField(default=dict)
```

### 5.2 Constraints

Required:

- `start_date <= end_date`;
- `quarter` must be 1..4 when `kind=quarter`;
- system quarterly cycles must have `year` and `quarter`;
- unique active quarterly cycle per `(workspace, year, quarter)`.

Recommended partial unique constraint:

```python
UniqueConstraint(
    fields=["workspace", "year", "quarter"],
    condition=Q(
        deleted_at__isnull=True,
        kind="quarter",
    ),
    name="workspace_cycle_unique_quarter",
)
```

### 5.3 Why a separate model?

Do not modify existing `Cycle(ProjectBaseModel)` into a dual project/workspace model.

The current model assumes:

- every cycle belongs to a project;
- sort order is project-relative;
- serializers validate project cycle enablement;
- permissions use `ProjectEntityPermission`;
- project cycle work-item mutation routes require `project_id`.

Making `project_id` nullable would create a large regression surface and ambiguous semantics.

A separate model isolates the feature and keeps upstream merge/backport risk lower.

---

## 6. Automatic quarter provisioning

### 6.1 Workspace creation

When a workspace is created, provision all four quarters for the current workspace-local year.

Example if workspace is created on Sep 25, 2026:

- Q1 2026
- Q2 2026
- Q3 2026
- Q4 2026

Past quarters are still created so the annual workspace navigation is complete.

### 6.2 Existing workspace migration/backfill

Migration must be safe and idempotent.

For every active workspace:

1. obtain the workspace timezone;
2. determine the current year in that timezone;
3. create Q1-Q4 for current year if missing;
4. use conflict-safe insert / `get_or_create`.

Do not generate all historical years.

### 6.3 Future year top-up

Do not require a manual annual admin task.

Use lazy provisioning plus optional scheduled top-up.

**Required V1 lazy provisioning:**

Whenever the workspace cycle list is requested:

```
ensure_quarters(workspace, current_workspace_year)
ensure_quarters(workspace, current_workspace_year + 1)
```

This guarantees next year's quarters exist before year rollover for active workspaces.

The operation must be idempotent and concurrency-safe.

**Optional P1 scheduled task:**

Run daily on Dec 1–31 and ensure next year's quarters for all active workspaces.

The scheduled job is only a convenience. Correctness must not depend on Celery/worker scheduling.

### 6.4 Manual deletion of system quarter

System-generated quarterly cycles should not be hard deleted through normal UI.

Allowed operations:

- rename: no, keep deterministic display;
- change dates: no;
- archive: optional, Admin only;
- delete: no.

Custom cycles may be edited/archived/deleted according to normal rules.

This prevents `ensure_quarters()` from fighting user modifications.

---

## 7. API

Suggested base:

`/api/v1/workspaces/{slug}/workspace-cycles/`

Use `service_scope = "cycles"` initially unless a new `workspace_cycles` scope is intentionally added.

### 7.1 List workspace cycles

`GET /api/v1/workspaces/{slug}/workspace-cycles/`

Query params:

- `cycle_view=current|upcoming|completed|all`
- `year=2026`
- `kind=quarter|custom`
- `order_by=start_date|-start_date|created_at|-created_at`

Response is metadata only, not heavy analytics.

### 7.2 Create custom cycle

`POST /api/v1/workspaces/{slug}/workspace-cycles/`

Body:

```json
{
  "name": "Launch Phase 1",
  "description": "",
  "start_date": "2026-10-01",
  "end_date": "2026-11-15"
}
```

Server sets:

- `kind=custom`
- `source=user`
- `owned_by=request.user`
- `timezone=workspace.timezone`

### 7.3 Detail/update/archive

`GET /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/`

`PATCH /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/`

`DELETE /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/`

DELETE should soft-delete custom cycles only.

For system quarterly cycles return `400` or `403` with a stable error code such as:

```json
{
  "error": "SYSTEM_WORKSPACE_CYCLE_IMMUTABLE"
}
```

### 7.4 Overview endpoint

`GET /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/overview/`

Returns all small/medium dashboard aggregates in one request:

```json
{
  "cycle": {},
  "coverage": {
    "visible_projects": 8,
    "cycle_enabled_projects": 7,
    "contributing_projects": 6,
    "project_cycles": 19
  },
  "progress": {
    "total": 124,
    "completed": 72,
    "started": 34,
    "unstarted": 10,
    "backlog": 6,
    "cancelled": 2
  },
  "projects": [
    {
      "id": "...",
      "name": "R&D",
      "identifier": "RND",
      "total": 22,
      "completed": 12,
      "started": 6,
      "unstarted": 3,
      "backlog": 1,
      "cancelled": 0
    }
  ],
  "priority_work_items": [],
  "assignees": [],
  "labels": []
}
```

Every field must use the viewer's ACL-filtered data set.

### 7.5 Burndown endpoint

`GET /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/burndown/`

V1 can aggregate existing project-cycle burndown/history only if the existing data source is reliable.

If existing project burndown is calculated from issue activities/history, reuse that mechanism across the visible issue set.

Do not fabricate historical points from current state.

If an accurate workspace burndown cannot be produced from existing historical data in V1, ship the workspace overview first and gate burndown behind a feature flag until correct.

Accuracy is more important than visual parity.

### 7.6 Work items endpoint

`GET /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/work-items/`

Supports:

- pagination;
- project filter;
- state/state-group;
- assignee;
- label;
- priority;
- text search;
- ordering.

The base queryset is always ACL-filtered first.

### 7.7 Project cycles endpoint

`GET /api/v1/workspaces/{slug}/workspace-cycles/{cycle_id}/project-cycles/`

Returns project cycles contributing to the selected workspace cycle.

Useful for drill-down and debugging coverage.

---

## 8. Backend query architecture

Create a dedicated service layer instead of putting large aggregate queries inside API views.

Suggested:

```
apps/api/plane/domain/workspace_cycles/
  __init__.py
  access.py
  provisioning.py
  query.py
  analytics.py
```

### 8.1 access.py

Responsibilities:

- verify active workspace membership;
- resolve visible projects;
- handle service principal access;
- expose one reusable ACL boundary.

### 8.2 provisioning.py

Responsibilities:

- quarter date generation in workspace timezone;
- `ensure_quarters(workspace, year)`;
- concurrency-safe `get_or_create`;
- workspace creation hook/backfill support.

### 8.3 query.py

Responsibilities:

- resolve workspace-cycle;
- resolve contributing project cycles;
- resolve distinct visible issue queryset.

### 8.4 analytics.py

Responsibilities:

- progress counts;
- per-project counts;
- top priority work items;
- assignee aggregation;
- label aggregation;
- burndown integration.

Views should mostly validate input and serialize output.

---

## 9. Frontend UX

### 9.1 Navigation

Add workspace-level `Cycles` to the main workspace navigation, outside individual project menus.

Suggested route:

`/{workspaceSlug}/cycles`

Cycle detail:

`/{workspaceSlug}/cycles/{workspaceCycleId}`

Do not reuse project route semantics that require `projectId`.

### 9.2 Main page

The first version should visually reuse Plane's existing project-cycle page patterns so the new feature feels native.

Sections:

1. **Active cycle**
   - current workspace cycle;
   - progress ring;
   - date range;
   - owner/source badge when relevant.

2. **Workspace progress**
   - Completed
   - Started
   - Backlog
   - Unstarted
   - Cancelled

3. **Work item burndown**
   - only if backend data is historically correct.

4. **Project breakdown**
   - each visible project;
   - progress stacked bar;
   - work-item count;
   - click project → open project cycle/work-item drill-down.

5. **Priority work items**
   - highest-priority visible items;
   - project identifier must be shown to avoid ambiguity.

6. **Assignees / Labels tabs**
   - aggregated across visible projects only.

7. **Upcoming workspace cycles**

8. **Completed workspace cycles**

### 9.3 Default landing behavior

When opening `/{workspaceSlug}/cycles`:

1. ensure current and next year's quarterly cycles;
2. select a workspace cycle containing `now`;
3. prefer system quarterly cycle when multiple custom cycles also contain `now`;
4. if no current cycle exists, select nearest upcoming cycle;
5. if none exists, select latest completed cycle.

### 9.4 New cycle action

Top-right: `Add cycle`.

Dialog fields:

- Name
- Description
- Start date
- End date

No project selector in V1: workspace cycles cover the viewer-visible workspace project set.

A future version may support explicit project scope, but the default must remain workspace-wide.

### 9.5 ACL-aware UX

Do not show text such as:

- "3 hidden projects"
- "12 items hidden by permissions"

That itself is a side channel.

Simply render the data the viewer can access.

An informational tooltip may say:

> Workspace cycle data reflects the projects you have access to.

This statement contains no hidden counts.

---

## 10. State management / frontend services

Follow existing Plane patterns.

Suggested additions:

- types under shared types package;
- API service for workspace cycles;
- MobX store under `packages/shared-state`;
- workspace route components in `apps/web`;
- reuse existing cycle progress/chart/list primitives where possible.

Do not fork/copy large project-cycle components if they can be generalized.

Preferred refactor:

```
CycleProgressCard
CycleBurndownChart
CycleWorkItemSummary
CycleAssigneeSummary
CycleLabelSummary
```

with a data-source-neutral props interface.

Project cycle pages keep using the same components.

Workspace cycles provide aggregated data through the new service/store.

---

## 11. Performance

Workspace analytics can touch many projects and work items, so V1 must avoid N+1 patterns.

### 11.1 Required indexes

Review existing indexes first.

Add only what is missing.

Likely useful:

```
WorkspaceCycle(workspace_id, start_date)
WorkspaceCycle(workspace_id, end_date)
Cycle(workspace_id, project_id, start_date)
CycleIssue(workspace_id, project_id, cycle_id)
CycleIssue(issue_id, deleted_at)
Issue(workspace_id, project_id, state_id)
ProjectMember(workspace_id, member_id, is_active, project_id)
```

Use `EXPLAIN ANALYZE` against realistic workspace sizes before adding redundant indexes.

### 11.2 Aggregate query rules

- filter visible projects first;
- filter project cycles second;
- filter work-item membership third;
- aggregate last;
- use `distinct issue_id` where necessary;
- avoid serializing all work items just to compute counts;
- prefetch only for list/detail endpoints that render those relations.

### 11.3 Endpoint split

Do not return thousands of work items inside `overview/`.

Use:

- overview = aggregates/small lists;
- work-items = paginated;
- project-cycles = paginated or lightweight;
- burndown = chart series.

This keeps first paint fast.

---

## 12. Migration plan

### Phase 1 — schema

- add `WorkspaceCycle`;
- add constraints/indexes;
- export model from `plane.db.models`;
- add serializer;
- add tests.

### Phase 2 — provisioning

- implement timezone-safe quarter generation;
- hook workspace creation;
- data migration for current year;
- lazy current+next year top-up.

### Phase 3 — ACL query layer

- centralize accessible project resolver;
- add cycle/project-cycle/issue query functions;
- security tests before analytics UI.

### Phase 4 — API

- CRUD metadata endpoints;
- overview;
- project-cycle drill-down;
- work-item list;
- burndown only if historically correct.

### Phase 5 — frontend

- workspace navigation item;
- cycle list/detail route;
- native Plane UI;
- create custom cycle;
- project drill-down.

### Phase 6 — hardening

- load tests;
- ACL regression tests;
- service-token tests;
- upgrade/migration test from current production schema.

---

## 13. Tests

### 13.1 Unit tests

Quarter generation:

- leap year;
- non-leap year;
- UTC workspace;
- Asia/Ho_Chi_Minh;
- America DST timezone;
- year rollover;
- repeated ensure call is idempotent.

Model:

- custom overlap allowed;
- duplicate system quarter rejected;
- invalid quarter rejected;
- start > end rejected.

### 13.2 ACL integration tests

Create:

- public Project A;
- private Project B;
- private Project C;
- User X: A+B;
- User Y: A+C;
- Admin with explicit/allowed visibility according to existing Plane ACL semantics.

Verify for X and Y:

- overview totals differ correctly;
- project breakdown contains only visible projects;
- priority list does not leak hidden issue IDs/names;
- assignees do not leak hidden users through work-item relation;
- labels do not leak hidden labels;
- work-item search cannot match hidden issues;
- burndown does not include hidden activity;
- pagination totals are ACL-safe.

### 13.3 Service-token tests

Verify:

- workspace token can access allowed workspace-cycle endpoint with `cycles` scope;
- wrong workspace is rejected;
- missing scope is rejected;
- project-scoped/limited token cannot escalate to full workspace data unless explicitly intended by token policy.

### 13.4 Regression tests

Existing project cycles must continue to work unchanged:

- create/update project cycle;
- cycle work-item assignment;
- transfer;
- archive;
- project cycle list;
- project cycle dashboard.

---

## 14. Acceptance criteria

V1 is complete when all are true:

- Workspace navigation contains `Cycles`.
- Opening it shows a current workspace-level cycle.
- Existing workspaces receive current-year Q1-Q4.
- Active workspaces automatically receive next year's Q1-Q4 without manual admin work.
- New workspaces receive current-year Q1-Q4.
- Authorized users can create custom workspace cycles.
- System quarterly cycles cannot be accidentally modified/deleted.
- Workspace cycle aggregates project-cycle work items across all projects visible to the current viewer.
- Private/inaccessible project data never affects any returned count, chart, facet, search result, or metadata.
- Per-project breakdown is visible and drillable.
- Existing project cycles behave exactly as before.
- API responses remain performant at realistic workspace scale.
- Backend + frontend tests cover ACL leakage scenarios.

---

## 15. P0 / P1 split

### P0

- `WorkspaceCycle` model
- quarterly auto provisioning
- custom cycle CRUD
- ACL-safe project resolver
- workspace cycle list/detail
- workspace overview progress
- project breakdown
- priority work items
- assignee + label summaries
- workspace navigation/UI
- work-item drill-down
- security tests

### P1

- accurate historical workspace burndown if existing history aggregation is not immediately reusable
- scheduled annual provisioning task in addition to lazy provisioning
- explicit project subset for a custom workspace cycle
- compare two workspace cycles
- export/report
- workspace-cycle snapshots
- trend deltas versus previous quarter

---

## 16. Explicit non-goals for V1

Do not:

- make `Cycle.project` nullable;
- migrate project cycles into workspace cycles;
- create a second direct work-item assignment table for workspace cycles;
- allow workspace cycle to mutate project-cycle membership;
- show hidden-project counts;
- cache privileged analytics for all users;
- invent historical burndown from current state;
- require a background scheduler for annual correctness.

---

## 17. Implementation note for this fork

Current Plane code already keeps project cycles strongly project-scoped through:

- `Cycle(ProjectBaseModel)`;
- `CycleIssue(ProjectBaseModel)`;
- `ProjectEntityPermission`;
- project-specific cycle serializers/routes.

The workspace implementation should therefore be additive rather than changing those assumptions.

The project list currently treats a project as visible when the user is an active project member or the project is public (`network=2`). Workspace-cycle aggregation should reuse that visibility rule through a centralized resolver so future ACL changes are applied consistently.

This design deliberately favors correctness, ACL isolation, and low upstream-merge risk over trying to force workspace cycles into the existing project-cycle table.
