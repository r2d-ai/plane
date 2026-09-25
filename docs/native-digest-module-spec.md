# Native Digest Module — Product & Implementation Spec

Status: Proposed / ready for implementation  
Target branch: `master`  
Scope: Community Edition fork  
Primary goal: Add deterministic scheduled email digests directly to Plane so users and project leaders receive actionable work summaries without requiring plane-cli, GoClaw, cron agents, or an LLM.

---

## 1. Problem

Plane already contains the source-of-truth data needed for routine daily and weekly work summaries, but users and project leaders must manually inspect projects, filters, timelines, and work-item lists to identify:

- overdue work;
- work due today or soon;
- blocked or stale work;
- project-level exceptions that require leader attention;
- weekly delivery and carry-over;
- workload distribution and upcoming deadlines.

This information is deterministic. Running an LLM or an external agent every morning to fetch, classify, group, and format the same data adds cost, latency, failure modes, and an unnecessary privileged integration path.

The digest feature should therefore run natively inside Plane.

V1 adds three scheduled email digests:

1. Personal Daily Digest.
2. Leader Morning Pulse.
3. Leader Weekly Digest.

The feature must reuse Plane's existing background-worker and email infrastructure, respect user email preferences, avoid empty/noise emails, and remain useful without any AI provider.

---

## 2. Product principles

### 2.1 Deterministic core

V1 MUST NOT depend on an LLM.

All V1 output is generated from deterministic queries, classification rules, metrics, and templates.

Future AI summaries may consume the already-generated digest snapshot, but failure or absence of AI must never prevent the base digest from being generated or delivered.

### 2.2 Actionable, not exhaustive

Digests are not a replacement for Plane views.

Do not dump every active work item into email.

A daily digest should answer: "What needs my attention now?"

A leader pulse should answer: "What needs intervention this morning?"

A weekly digest should answer: "What changed this week, what remains at risk, and what should I inspect before next week?"

### 2.3 No empty email

If a digest has no relevant content, do not send it.

Examples:

- a user has no assigned active work items: skip Personal Daily Digest;
- a user has active work items but none match an actionable daily category: skip Personal Daily Digest;
- a project leader has no exceptions: skip Leader Morning Pulse;
- a leader has no active work and no reportable activity during the weekly window: skip Leader Weekly Digest.

There is no "Everything looks good" email in V1.

### 2.4 User opt-out is authoritative

Users can opt out of each digest type independently in Preferences.

The user's explicit preference is the final delivery gate. No instance or workspace setting may override a user's opt-out.

### 2.5 One email per recipient per digest period

A user may belong to many workspaces and projects.

V1 consolidates all eligible content into one email per digest type and reporting period.

Do not send one Personal Daily Digest per workspace.

Do not send one Leader Weekly Digest per project.

### 2.6 Native data access

Digest generation runs inside the Plane backend using the ORM.

Do not route native digest generation through:

- public REST APIs;
- PATs;
- service access tokens;
- plane-cli;
- MCP;
- GoClaw;
- an external cron service.

This avoids unnecessary credentials and ensures the feature can use the same internal data and permission semantics as Plane.

---

## 3. Existing Plane infrastructure to reuse

The current fork already has the required execution and delivery primitives:

- `worker` background worker;
- `beat-worker`;
- Celery;
- django-celery-beat `DatabaseScheduler`;
- Redis;
- RabbitMQ;
- configured email delivery;
- `EmailMultiAlternatives`;
- Django email templates under `apps/api/templates/emails/`;
- `generate_plain_text_from_html`;
- existing account notification-preference UI/path;
- `UserNotificationPreference`;
- `Project.project_lead`.

Relevant existing files:

- `apps/api/plane/celery.py`
- `apps/api/plane/bgtasks/email_notification_task.py`
- `apps/api/plane/db/models/notification.py`
- `apps/api/plane/db/models/project.py`
- `apps/api/templates/emails/`

The implementation should extend these patterns instead of introducing a separate scheduling service.

---

## 4. V1 digest types

Use stable internal identifiers:

```python
PERSONAL_DAILY = "personal_daily"
LEADER_MORNING = "leader_morning"
LEADER_WEEKLY = "leader_weekly"
```

### 4.1 Personal Daily Digest

Recipient:

- active Plane user;
- email address is present;
- Personal Daily Digest preference is enabled.

Default schedule:

- Monday-Friday;
- 08:00 in the configured digest timezone.

Scope:

- all workspaces/projects visible to the recipient;
- only work items assigned to the recipient;
- one consolidated email.

Report actionable buckets in this order:

1. overdue;
2. due today;
3. blocked;
4. due soon;
5. stale in progress.

A work item may match more than one condition but MUST be rendered once, in the highest-priority bucket.

Example:

- overdue + blocked -> render under Overdue;
- due today + blocked -> render under Due today;
- due soon + stale -> render under Due soon.

### 4.2 Leader Morning Pulse

Recipient:

- user is `Project.project_lead` for at least one active project;
- leader-morning preference enabled.

Default schedule:

- Monday-Friday;
- 08:15 in the configured digest timezone.

Scope:

- all active projects where `Project.project_lead_id == recipient.id`;
- the recipient must still have access to the project;
- consolidate across workspaces/projects into one email.

V1 exceptions:

- overdue work item;
- blocked work item;
- urgent/high-priority work item without assignee;
- work item due today but not started;
- stale in-progress work item.

If there are no exceptions, do not send an email.

Do not include a full project inventory.

Do not include generic "team is healthy" content.

Workload-concentration alerts are intentionally excluded from the V1 morning pulse because a raw work-item count is not a reliable overload signal. Workload distribution is included in the weekly digest as descriptive context.

### 4.3 Leader Weekly Digest

Recipient:

- user is `Project.project_lead` for at least one active project;
- weekly-leader preference enabled.

Default schedule:

- Friday;
- 16:00 in the configured digest timezone.

Default reporting window:

- Monday 00:00 inclusive;
- Friday 16:00 exclusive/end-at-generation;
- same configured digest timezone.

Scope:

- all active projects led by the recipient and accessible to the recipient;
- consolidate into one email;
- group details by workspace/project where useful.

Weekly report sections:

1. summary counts;
2. delivery/activity;
3. unfinished/carry-over;
4. risks;
5. workload distribution;
6. next-week deadlines;
7. Plane data hygiene.

The weekly digest is descriptive operational data, not an employee-performance score.

---

## 5. Work-item eligibility

Before category-specific rules are applied, a work item must pass the common eligibility filter.

Exclude:

- soft-deleted work items;
- archived work items;
- draft work items;
- work items in state group `completed`;
- work items in state group `cancelled` for current/open-item sections.

Personal Daily Digest additionally requires:

- recipient is an active assignee;
- recipient can access the owning project.

Leader digests additionally require:

- owning project is active;
- recipient is `project_lead`;
- recipient can access the project.

When historical events are used for weekly completion metrics, a work item that is currently completed may still be counted as a completion event. The open-item exclusion above applies to current-risk/current-work sections, not historical delivery events.

---

## 6. Daily classification rules

All date comparisons are made in the configured digest timezone.

Let:

```text
today = local date at generation time
due_soon_days = configurable integer, default 2
stale_days = configurable integer, default 3
```

### 6.1 Overdue

```text
target_date < today
AND current state group NOT IN (completed, cancelled)
```

### 6.2 Due today

```text
target_date == today
AND current state group NOT IN (completed, cancelled)
```

### 6.3 Due soon

```text
today < target_date <= today + due_soon_days
AND current state group NOT IN (completed, cancelled)
```

V1 uses calendar days. Business-day calendars/holidays are P2.

### 6.4 Blocked

Plane has native issue-relation semantics including `blocked_by`.

A work item is blocked when it has at least one active `IssueRelation` with:

```text
relation_type == "blocked_by"
```

and the related blocker work item is not in `completed` or `cancelled`.

Deleted relations and deleted related work items are ignored.

A blocker that has already completed does not keep the work item in the Blocked bucket.

### 6.5 Stale in progress

```text
current state group == started
AND updated_at < now - stale_days
```

V1 uses `Issue.updated_at` for deterministic low-cost classification.

Activity-aware staleness using the most recent meaningful `IssueActivity` is P2.

### 6.6 Due today but not started

Used in Leader Morning Pulse:

```text
target_date == today
AND current state group IN (backlog, unstarted)
```

### 6.7 High/urgent and unassigned

Used in Leader Morning Pulse:

```text
priority IN (high, urgent)
AND no active IssueAssignee
AND current state group NOT IN (completed, cancelled)
```

---

## 7. Sort and rendering rules

Within each bucket, sort by:

1. priority severity: urgent -> high -> medium -> low -> none;
2. target date ascending, null last;
3. project identifier;
4. sequence ID.

Each work-item row/card must include enough information to act without opening a project list:

- identifier;
- title;
- workspace name;
- project name;
- priority when set;
- current state;
- target date when set;
- assignee for leader digests;
- direct Plane work-item URL.

Do not include descriptions, comments, attachments, or arbitrary HTML from work items in V1 digest emails.

This keeps email compact and avoids treating user-controlled work-item content as executable/template instructions.

---

## 8. Personal Daily skip rules

Personal Daily Digest MUST NOT be sent when any of these are true:

1. user preference is disabled;
2. user is inactive;
3. user has no email address;
4. user has zero eligible active assigned work items;
5. user has eligible active work items but zero work items in any actionable bucket;
6. an unrecoverable data-generation error occurs;
7. the same digest period has already been sent.

Therefore:

```python
if not preference.personal_daily_digest:
    return SKIPPED_DISABLED

items = get_personal_actionable_items(user)

if not items:
    return SKIPPED_EMPTY

send(...)
```

Do not send:

> You have no pending work.

Do not send:

> Everything is on track.

Silence is the success state when there is nothing actionable.

---

## 9. Leader Morning skip rules

Leader Morning Pulse MUST NOT be sent when:

- user preference is disabled;
- user leads no accessible active projects;
- no leader exception exists;
- user is inactive/no email;
- period already sent;
- generation fails.

A leader with 100 normal active work items and zero defined exceptions receives no morning pulse.

---

## 10. Leader Weekly metrics

Use deterministic event/history data where possible.

### 10.1 Created

Count work items created during the weekly reporting window in led/accessible projects.

### 10.2 Started

Count distinct work items with a state transition into state group `started` during the reporting window.

Use `IssueActivity` state-change events and state identifiers rather than `Issue.updated_at`.

### 10.3 Completed

Count distinct work items with a state transition into state group `completed` during the reporting window.

### 10.4 Reopened

Count distinct work items with a state transition:

```text
completed -> any non-completed/non-cancelled group
```

during the reporting window.

### 10.5 Carry-over / unfinished

V1 defines weekly carry-over deterministically as an open work item that satisfies at least one of:

- target date falls inside the reporting window; or
- transitioned into `started` during the reporting window;

and is still not completed/cancelled when the weekly digest is generated.

This is an operational signal, not a commitment/accounting metric.

Future cycle-aware "committed vs delivered" metrics can replace or supplement it when cycle commitment semantics are available.

### 10.6 Current overdue

Current eligible work items with target date earlier than the local generation date.

### 10.7 Current blocked

Use the same unresolved `blocked_by` rule as daily digests.

### 10.8 Workload distribution

Per assignee, report descriptive counts:

- current active assigned;
- completed during reporting window;
- current overdue.

Do not calculate a productivity score.

Do not rank employees as best/worst.

Email copy must state that counts describe workload/flow, not individual performance.

### 10.9 Next-week deadlines

Report open items with target dates after the weekly cutoff and up to the end of the following Friday by default.

Group/count by:

- priority;
- state group;
- project.

Show detailed items only for urgent/high priority or when the total is small enough to remain readable.

### 10.10 Data hygiene

Count current active work items in led projects with:

- no assignee;
- no target date;
- stale in progress.

These are quality/operability signals.

Do not treat missing target date as employee failure.

---

## 11. User preferences

### 11.1 Reuse existing model

Extend the existing `UserNotificationPreference` model instead of creating a second user-preference system.

Add:

```python
personal_daily_digest = models.BooleanField(default=True)
leader_morning_digest = models.BooleanField(default=True)
leader_weekly_digest = models.BooleanField(default=True)
```

Migration defaults must preserve opt-in behavior for existing users.

### 11.2 Preference semantics

Each toggle independently gates email delivery.

If a user disables Personal Daily Digest, neither admin configuration nor a workspace setting may send it to that user.

Leader toggles apply only when the user currently leads one or more projects.

### 11.3 UI

Extend the existing account notification preferences screen, currently linked by notification emails at:

```text
/<workspace>/settings/account/notifications/
```

Add an "Email digests" section.

Suggested UI copy:

```text
Email digests

[✓] Daily work digest
    Receive one morning email when you have work that needs attention.

[✓] Leader morning pulse
    Receive a morning exception summary when projects you lead need attention.

[✓] Weekly leader digest
    Receive a weekly summary for projects you lead.
```

The UI may show leader options for all users; the descriptions make clear that delivery only applies when they lead a project. This avoids preference state changing unexpectedly when a user becomes a project leader later.

Preference updates must use the existing preference API/store patterns rather than a digest-specific settings endpoint where possible.

### 11.4 Email footer

Every digest email must contain a link to the account notification-preferences screen so the recipient can disable that digest type.

---

## 12. Instance digest configuration

Personal Daily Digest spans all workspaces, so V1 scheduling is instance-level.

Do not allow independent per-workspace send times in V1 because one user may belong to many workspaces and would otherwise receive duplicate daily emails.

Introduce a single digest configuration source with these effective values:

```text
enabled
timezone
personal_daily_enabled
personal_daily_time
leader_morning_enabled
leader_morning_time
leader_weekly_enabled
leader_weekly_day
leader_weekly_time
due_soon_days
stale_days
```

Recommended defaults:

```text
enabled=true
timezone=UTC
personal_daily_enabled=true
personal_daily_time=08:00
leader_morning_enabled=true
leader_morning_time=08:15
leader_weekly_enabled=true
leader_weekly_day=Friday
leader_weekly_time=16:00
due_soon_days=2
stale_days=3
```

Production deployment for the company should set the digest timezone to `Asia/Ho_Chi_Minh`.

Implementation options, in priority order:

1. persist typed instance settings if the fork already has an appropriate instance-settings facility;
2. otherwise add a small `DigestConfiguration` singleton model;
3. environment variables may provide defaults/bootstrapping but should not be the only long-term configuration mechanism.

P1 may add an admin UI for instance schedule/threshold editing.

User opt-out remains authoritative regardless of instance configuration.

---

## 13. Scheduling architecture

### 13.1 Use Celery beat + worker

Add a lightweight dispatcher task to the existing Celery beat schedule.

Recommended:

```python
"digest-dispatcher": {
    "task": "plane.bgtasks.digest_task.dispatch_due_digests",
    "schedule": crontab(minute="*/5"),
}
```

The dispatcher:

1. loads effective digest configuration;
2. converts current time into digest timezone;
3. determines which digest definitions are due;
4. creates/enqueues recipient-generation tasks;
5. relies on period-key idempotency to tolerate repeated dispatcher runs.

Five-minute scheduling resolution is sufficient for V1 and matches existing email-notification worker cadence.

### 13.2 Fan-out

Do not generate every user's digest synchronously inside the beat process.

Use:

```text
beat-worker
   |
   +-- dispatch_due_digests
          |
          +-- generate_personal_daily(user_id, period_key)
          +-- generate_leader_morning(user_id, period_key)
          +-- generate_leader_weekly(user_id, period_key)
```

Batch recipient discovery where appropriate, but each recipient digest should be independently retryable.

### 13.3 Period keys

Use stable period keys:

```text
personal_daily:YYYY-MM-DD
leader_morning:YYYY-MM-DD
leader_weekly:YYYY-Www
```

The recipient is part of the database uniqueness constraint, not necessarily embedded in the string.

---

## 14. Delivery/idempotency model

Do not overload `EmailNotificationLog` for digests.

Existing notification email logs are actor/event-oriented and require fields that do not map cleanly to system-generated digest reports.

Add a dedicated model, e.g. `DigestDelivery`.

Suggested fields:

```python
class DigestDelivery(BaseModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="digest_deliveries",
    )
    digest_type = models.CharField(max_length=32)
    period_key = models.CharField(max_length=64)

    status = models.CharField(
        max_length=16,
        choices=[
            ("pending", "Pending"),
            ("sending", "Sending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
    )

    # Deterministic generated payload used for rendering/debugging.
    snapshot = models.JSONField(default=dict)

    scheduled_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)
    failed_at = models.DateTimeField(null=True)
    error = models.TextField(blank=True, default="")
```

Constraint:

```python
UniqueConstraint(
    fields=["recipient", "digest_type", "period_key"],
    name="unique_digest_delivery_period_recipient",
)
```

This is the durable idempotency boundary.

Redis locks may be used as an optimization but MUST NOT be the sole duplicate-send protection.

### 14.1 Empty/disabled runs

Do not create `DigestDelivery` rows for routine:

- disabled preference;
- no relevant content.

These should be counters/logs, not durable per-user database records.

Create a delivery row only when a non-empty digest has been produced and is about to enter delivery.

---

## 15. Digest snapshot contract

Separate query/aggregation from rendering.

Each generator should produce a JSON-serializable snapshot.

Example Personal Daily snapshot:

```json
{
  "schema_version": 1,
  "digest_type": "personal_daily",
  "generated_at": "2026-09-28T08:00:00+07:00",
  "period_key": "2026-09-28",
  "recipient": {
    "id": "uuid",
    "display_name": "An",
    "email": "an@example.com"
  },
  "counts": {
    "overdue": 2,
    "due_today": 3,
    "blocked": 1,
    "due_soon": 2,
    "stale": 1
  },
  "sections": {
    "overdue": [],
    "due_today": [],
    "blocked": [],
    "due_soon": [],
    "stale": []
  }
}
```

Work-item snapshot entry:

```json
{
  "id": "uuid",
  "identifier": "DES-128",
  "name": "Banner Game A",
  "workspace": {
    "id": "uuid",
    "name": "Design",
    "slug": "design"
  },
  "project": {
    "id": "uuid",
    "name": "Game A",
    "identifier": "DES"
  },
  "state": {
    "name": "In Progress",
    "group": "started"
  },
  "priority": "high",
  "target_date": "2026-09-24",
  "assignees": [],
  "url": "https://plane.example/..."
}
```

Advantages:

- deterministic tests;
- email rendering tests do not need complex ORM fixtures;
- future Slack/Telegram/in-app renderers can consume the same contract;
- optional AI summary can consume snapshot data instead of raw unrestricted Plane content.

---

## 16. Query architecture and performance

### 16.1 Avoid N+1

Digest builders must use bulk ORM queries with:

- `select_related`;
- `prefetch_related`;
- annotations/subqueries where appropriate;
- distinct IDs for many-to-many joins.

Do not loop:

```text
workspace -> project -> issue -> assignee
```

with one query per object.

### 16.2 Recipient discovery

Personal:

- active users with digest preference enabled;
- preferably users who have at least one eligible active assignment, so users with no work are not fanned out unnecessarily.

Leader:

- distinct active `project_lead_id` values from active projects;
- intersect with active users and enabled preferences.

### 16.3 Bulk personal query

A scalable implementation may query all actionable assignments once, ordered/grouped by assignee, then enqueue only users with data.

Do not fetch all issue descriptions/comments.

### 16.4 Weekly event query

Use bulk `IssueActivity` state-change queries for started/completed/reopened metrics.

Resolve old/new state groups in bulk.

Do not perform one state lookup per event.

### 16.5 Index review

Before implementation is merged, inspect query plans for the expected large-instance queries.

Add targeted indexes only if existing indexes are insufficient.

Likely query dimensions include:

- `IssueAssignee.assignee_id`;
- issue project/state/target_date/updated_at;
- `Project.project_lead_id`;
- issue relation type/issue IDs;
- `IssueActivity.issue_id/field/created_at`.

Do not add speculative indexes without checking existing schema/indexes and query plans.

---

## 17. Permission and data-leak rules

### 17.1 Personal digest

A recipient may only receive work-item data they can currently access.

Being present in historical assignment data must not bypass current project/workspace access.

### 17.2 Leader digest

`Project.project_lead` defines leadership scope, but the project must also be currently accessible to the recipient.

A stale/dangling `project_lead` relationship must not grant new access.

### 17.3 Private projects

Counts, titles, identifiers, project names, URLs, assignees, and metrics from inaccessible projects must not appear in the digest.

### 17.4 Cross-workspace consolidation

Cross-workspace consolidation occurs only after per-recipient access filtering.

Do not build a global unrestricted snapshot and then rely on the renderer to hide rows.

### 17.5 Work-item content is untrusted data

V1 renders only controlled scalar fields listed in the snapshot contract.

Escape all user-controlled text.

Do not interpret work-item title/description/comment content as instructions.

Do not render raw work-item HTML.

---

## 18. Email delivery

Reuse existing Plane email configuration from `get_email_configuration()`.

Reuse:

- `EmailMultiAlternatives`;
- HTML + plain-text multipart;
- `generate_plain_text_from_html`.

Add digest templates under a dedicated directory:

```text
apps/api/templates/emails/digests/
├── personal-daily.html
├── leader-morning.html
└── leader-weekly.html
```

Prefer shared partials/styles if the current email-template system supports them cleanly.

### 18.1 Suggested subjects

Personal:

```text
[Plane] Công việc hôm nay — 2 quá hạn · 3 đến hạn
```

Leader morning:

```text
[Plane] Morning Pulse — 4 điểm cần chú ý
```

Weekly:

```text
[Plane] Weekly Digest — Design — 21–25/09
```

When a leader's email spans multiple workspaces/projects, do not force one project/workspace name into the subject. Use a neutral subject such as:

```text
[Plane] Weekly Digest — 21–25/09
```

### 18.2 Email length

Keep detailed item rendering bounded.

Recommended defaults:

- render up to 10 items per section;
- when additional items exist, show "+ N more" with a link into the relevant Plane view/filter where possible;
- weekly workload table: all team members for small teams, otherwise highest-attention rows plus a link to Plane.

Do not truncate counts.

---

## 19. Email content requirements

### 19.1 Personal Daily

Required sections when non-empty:

- Overdue;
- Due today;
- Blocked;
- Due soon;
- Stale.

Footer:

- generated timestamp;
- link to Plane;
- link to notification preferences.

### 19.2 Leader Morning

Lead with number of exceptions, then group by exception type.

No generic prose generated by AI.

Optional deterministic "Check" bullets may be produced from rules, e.g.:

- "Review 3 overdue work items."
- "Resolve or update blocker status for 1 blocked work item."
- "Assign 2 high-priority unassigned work items."

These are template strings derived directly from counts.

### 19.3 Leader Weekly

Required sections when applicable:

- Week summary;
- Delivery;
- Risks;
- Workload distribution;
- Next week;
- Data hygiene.

Include the disclaimer:

> Work-item counts describe workload and workflow signals; they are not employee-performance scores.

---

## 20. Failure semantics

### 20.1 Fail closed

If digest generation cannot establish a complete authorized dataset, do not send a misleading partial "all clear" email.

For exceptions:

- log the error;
- mark the delivery failed if a delivery row already exists;
- retry according to Celery policy.

### 20.2 Retry

Sending must be safe to retry.

Use the durable unique delivery constraint plus status transitions.

Suggested flow:

```text
generate snapshot
    |
create DigestDelivery(pending) atomically
    |
claim/send
    |
sent
```

A second worker encountering the same unique key must not send a duplicate.

### 20.3 SMTP failure

On SMTP failure:

- retain snapshot;
- set status `failed`;
- store a bounded/sanitized error message;
- allow Celery retry;
- never store SMTP password/credentials in error data.

---

## 21. Observability

Emit structured logs/counters for:

```text
digest.dispatch.run
digest.personal.sent
digest.personal.skipped_disabled
digest.personal.skipped_empty
digest.personal.failed

digest.leader_morning.sent
digest.leader_morning.skipped_disabled
digest.leader_morning.skipped_empty
digest.leader_morning.failed

digest.leader_weekly.sent
digest.leader_weekly.skipped_disabled
digest.leader_weekly.skipped_empty
digest.leader_weekly.failed

digest.delivery.duplicate_prevented
digest.delivery.retry
```

Do not log full digest snapshots or user work-item titles at INFO level.

IDs/counts are sufficient for routine observability.

---

## 22. API changes

### 22.1 User notification preferences

Extend the existing notification-preference serializer/API response with:

```json
{
  "personal_daily_digest": true,
  "leader_morning_digest": true,
  "leader_weekly_digest": true
}
```

Existing clients that do not send these fields must continue to work.

PATCH semantics must not reset omitted digest fields.

### 22.2 Preview/test API

P1, not required for first merge:

```text
GET  /api/users/me/digests/{type}/preview/
POST /api/users/me/digests/{type}/send-test/
```

Preview must apply the same ACL, query rules, and preference-independent content generation used by scheduled delivery.

"Send test" may ignore the user's disabled preference only when explicitly initiated by that same authenticated user.

### 22.3 Delivery history

P2:

```text
GET /api/users/me/digests/history/
```

Do not block V1 email delivery on building a digest-history UI.

---

## 23. Frontend changes

V1 frontend scope is intentionally small:

- extend account Notification Preferences;
- add three digest toggles;
- use existing settings layout/components;
- provide loading/error/success behavior consistent with current preference toggles;
- add i18n strings rather than hard-coded text.

No dedicated Digest page is required in V1.

P1:

- admin schedule/threshold configuration UI;
- digest preview/test.

P2:

- in-app Digest history/inbox.

---

## 24. Suggested backend module layout

Exact paths may be adjusted to existing project conventions, but keep query/build/render/delivery responsibilities separated.

```text
apps/api/plane/
├── bgtasks/
│   └── digest_task.py
├── digests/
│   ├── __init__.py
│   ├── constants.py
│   ├── config.py
│   ├── permissions.py
│   ├── queries.py
│   ├── snapshots.py
│   ├── renderers.py
│   └── delivery.py
└── db/models/
    └── ... DigestDelivery / optional DigestConfiguration
```

Avoid one giant Celery task containing ORM queries, rendering, SMTP handling, and schedule decisions.

---

## 25. Suggested implementation phases

### Phase 0 — foundation

- extend `UserNotificationPreference`;
- migration;
- API/serializer changes;
- UI toggles;
- digest constants/config;
- `DigestDelivery` model + uniqueness;
- common recipient/project-access helpers;
- test factories.

### Phase 1 — Personal Daily

- actionable-item bulk query;
- classification/deduplication;
- snapshot builder;
- template + plain text;
- delivery;
- dispatcher integration;
- skip-empty;
- idempotency;
- tests.

This is the highest-value digest and should ship first.

### Phase 2 — Leader Morning Pulse

- project-lead scope resolver;
- exception query;
- leader snapshot;
- template;
- skip-no-exception;
- tests.

### Phase 3 — Leader Weekly

- weekly event aggregation;
- started/completed/reopened;
- carry-over;
- workload distribution;
- next-week deadlines;
- data-hygiene counts;
- template;
- tests.

### Phase 4 — hardening

- query-plan/performance review;
- retry/duplicate-send tests;
- timezone/DST tests;
- authorization regression tests;
- email-client rendering checks;
- observability.

---

## 26. Acceptance criteria

### 26.1 Personal Daily

Given an active user with:

- two overdue assigned items;
- one item due today;
- one normal item due next month;

when the daily digest runs:

- exactly one email is sent;
- overdue and due-today items appear;
- the unrelated next-month item is not listed;
- direct links are valid;
- no inaccessible project data appears.

Given a user with no assigned active work:

- no email is sent.

Given a user with active work but no actionable daily item:

- no email is sent.

Given a user who disabled `personal_daily_digest`:

- no email is sent even when overdue items exist.

### 26.2 Leader Morning

Given a leader who leads three projects:

- one consolidated email is sent when exceptions exist;
- the email groups/identifies the affected projects;
- no separate project emails are sent.

Given zero exceptions:

- no email is sent.

Given an inaccessible project still references the user as `project_lead`:

- that project's data does not appear.

### 26.3 Leader Weekly

Given weekly activity across multiple led projects:

- one consolidated email is sent;
- created/started/completed/reopened metrics are derived from the reporting window;
- carry-over follows the defined V1 rule;
- workload counts are descriptive and not converted into performance scores;
- next-week and data-hygiene sections use current authorized data.

Given no activity and no active work in led projects:

- no weekly email is sent.

### 26.4 Idempotency

If the dispatcher runs repeatedly for the same due time or a Celery task retries:

- the same recipient/digest/period is sent at most once.

### 26.5 Preferences

Each of the three toggles:

- persists;
- returns correctly from API;
- changes only its own digest behavior;
- does not affect existing issue notification preferences.

---

## 27. Test matrix

Backend unit/integration tests must cover at least:

- preference defaults for existing/new users;
- independent preference toggles;
- user with no work -> no mail;
- user with non-actionable work -> no mail;
- overdue classification;
- due-today classification;
- due-soon boundaries;
- blocked with active blocker;
- blocked relation whose blocker is completed;
- stale threshold boundary;
- duplicate category membership -> one rendered item;
- private/inaccessible project exclusion;
- cross-workspace personal consolidation;
- project-lead multi-project consolidation;
- leader no-exception skip;
- high-priority unassigned exception;
- due-today-not-started exception;
- weekly created/started/completed/reopened;
- weekly carry-over;
- weekly data hygiene;
- timezone day boundary;
- Friday weekly cutoff;
- duplicate dispatcher run;
- duplicate worker retry;
- SMTP failure + retry;
- HTML escaping;
- plain-text email generation.

Frontend tests:

- three toggles render;
- values initialize from API;
- toggle PATCH updates the correct field;
- error rollback/toast behavior follows existing preference UX;
- translations exist.

---

## 28. Out of scope for V1

Explicitly defer:

- LLM-generated summaries;
- GoClaw integration;
- plane-cli integration;
- Slack delivery;
- Telegram delivery;
- webhook delivery;
- custom user-authored digest builders;
- per-workspace schedules;
- holiday/business-day calendars;
- employee scoring/ranking;
- KPI scoring;
- "AI recommendations";
- in-app digest history page;
- automated write-back/update of work items.

The deterministic snapshot contract should make these additions possible later without rewriting the query engine.

---

## 29. Future AI boundary

If an AI summary is added later:

```text
Plane ORM
   |
deterministic DigestSnapshot
   |
   +--------------------> deterministic email (always available)
   |
optional AI summarizer
   |
AI summary section
```

The AI layer receives the bounded authorized snapshot, not unrestricted database access.

It must not:

- alter deterministic counts;
- hide deterministic risk items;
- invent reasons for delays;
- infer employee performance;
- receive data from projects the recipient cannot access.

---

## 30. Final V1 architecture

```text
                         Plane DB
                            |
                   deterministic queries
                            |
                     Digest builders
                            |
                     DigestSnapshot
                            |
               +------------+------------+
               |                         |
        HTML/plain renderer       future renderers
               |                  Slack/Telegram/etc.
               |
         DigestDelivery
               |
       Plane email transport
               |
             User


Celery beat (every 5m)
       |
digest dispatcher
       |
       +-- Personal Daily     Mon-Fri 08:00
       +-- Leader Morning     Mon-Fri 08:15, exceptions only
       +-- Leader Weekly      Friday 16:00

UserNotificationPreference is the final delivery gate.
Empty/non-actionable digest => no email.
```

V1 succeeds when routine work reminders and leader summaries run reliably inside Plane with no LLM, no external privileged token, no duplicate emails, no empty emails, and a clear per-user opt-out path.
