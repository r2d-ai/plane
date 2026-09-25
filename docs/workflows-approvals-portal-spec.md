# Workflows, Approvals, and Portal Process Engine — Product & Implementation Spec

**Status:** Proposed / implementation-ready  
**Target repository:** `r2d-ai/plane`  
**Target branch:** `master`  
**Research baseline:** 2026-09-26  
**Primary goal:** Bring Plane Commercial-style Workflows and Approvals into the CE fork, then extend the same primitives so HR, IT, Finance, Procurement, Onboarding, Offboarding, and other internal Portal processes can run natively on Plane Work Items without maintaining a parallel request/workflow engine.

---

## 1. Executive decision

### 1.1 Plane Work Items become the process/request object

Do not create a parallel `PortalRequest`, `PortalTask`, `PortalComment`, or `PortalAttachment` stack.

Use the existing Plane Work Item as the process instance:

```text
Request / Case / Ticket / Approval
               │
               ▼
           Work Item
               │
      ┌────────┼─────────┐
      ▼        ▼         ▼
    Type     State     Properties
      │        │         │
      └────────┴─────────┘
               │
           Workflow
               │
      ┌────────┴────────┐
      ▼                 ▼
 Transition          Approval
```

Existing Plane primitives remain authoritative for:

- title and description;
- assignees;
- comments;
- attachments;
- subscribers;
- child work items;
- work-item relations;
- activity/history;
- labels;
- notifications;
- project/workspace ACL.

### 1.2 Domain entities remain domain entities

Do **not** model long-lived business records as Work Items.

Examples:

| Portal concept | Plane representation |
| --- | --- |
| Leave request | typed Work Item |
| Expense claim | typed Work Item |
| Equipment request | typed Work Item |
| Purchase request | typed Work Item |
| Onboarding case | typed Work Item |
| Offboarding case | typed Work Item |
| Employee | domain entity, referenced by Work Item |
| Department | domain entity |
| Organization structure | domain entity |
| Asset | domain entity |
| Vendor | domain entity |
| Cost center | domain entity |

Rule:

> Plane owns the process. Domain modules own long-lived business data.

### 1.3 Workflow is a guarded state machine, not BPMN

The implementation follows Plane Commercial's public model:

- a workflow contains states;
- each state may allow or forbid creation directly into it;
- flows define allowed transitions;
- flows may be ordinary transitions or approval gates;
- type-specific workflows override the project default;
- conditions may run before or after a transition.

No BPMN graph editor, arbitrary branching DSL, parallel gateway, timer node, or generic low-code workflow runtime is required for V1.

---

## 2. Commercial behavior baseline

The public Plane documentation as of 2026-09-26 defines the following behavior.

### 2.1 Project default workflow

Every project has one default workflow. When workflows are active, that default governs work items unless a more specific workflow applies.

### 2.2 Type-specific workflows

Enterprise Grid supports additional workflows assigned to selected Work Item Types.

Resolution order:

```text
matching type-specific workflow
            │
            ├─ yes ─▶ use it
            │
            └─ no  ─▶ use project default workflow
```

### 2.3 Workflow states

A workflow selects the project states participating in the workflow.

Each included state has:

```text
allow_new_work_items = true | false
```

A work item may only be created directly in a state with this flag enabled.

### 2.4 Transition flows

A transition flow specifies:

- source state;
- destination state;
- actors allowed to perform the transition;
- optional pre-validation;
- optional post-actions.

### 2.5 Approval flows

An approval flow specifies:

- source state;
- state reached on approval;
- state reached on rejection;
- actors allowed to approve/reject;
- optional pre-validation;
- optional post-actions.

When a work item reaches a state that has an approval flow, it becomes approval-pending and eligible approvers receive Approve/Reject actions.

### 2.6 Flow type invariant

A source state may have multiple flows, but all flows from that source state must be the same type:

```text
valid:
State A ─transition─▶ B
        └transition─▶ C

valid:
State A ─approval─▶ B / reject C
        └approval─▶ D / reject C

invalid:
State A ─transition─▶ B
        └approval───▶ C
```

For V1 of this fork, multiple transition flows are supported. The data model supports multiple approval flows, but the configuration API MUST initially allow at most one approval flow per source state until multi-approval-flow UI semantics are verified against the Commercial implementation.

### 2.7 Conditions

Commercial Plane uses Plane Runner scripts for:

- pre-validation;
- post-actions.

For this fork, V1 intentionally implements deterministic/declarative conditions and actions first. Arbitrary script execution is deferred.

---

## 3. Goals

### P0 — Workflow core

1. Add project workflows.
2. Add one default workflow per project.
3. Add type-specific workflow assignment.
4. Add workflow states.
5. Add `allow_new_work_items`.
6. Add transition flows.
7. Add actor authorization for flows.
8. Enforce workflows on the backend for every state mutation path.
9. Add workflow revisioning.
10. Add audit history.
11. Preserve existing projects when workflows are disabled.

### P1 — Approvals

1. Add approval flows.
2. Add runtime approval instances.
3. Snapshot eligible approvers when approval starts.
4. Add approve/reject actions.
5. Add approval decision audit.
6. Add transactional concurrency protection.
7. Add notifications and Inbox entries.
8. Add dynamic approver resolvers needed by Portal.

### P1 — Typed request data

1. Complete Work Item Type support required by workflows.
2. Add custom properties.
3. Validate required properties.
4. Add entity-reference properties for Portal domain records.

### P2 — Portal process layer

1. Internal request forms.
2. Onboarding/offboarding workflows.
3. IT equipment requests.
4. Leave requests.
5. Expense/procurement approvals.
6. Declarative preconditions.
7. Declarative post-actions.
8. Cross-project fulfillment work items.
9. SLA/reminder/escalation primitives.

---

## 4. Non-goals

The first implementation MUST NOT include:

- BPMN;
- a general DAG execution engine;
- arbitrary JavaScript/TypeScript execution;
- unrestricted Python evaluation;
- a user-authored expression language;
- a visual node graph editor;
- workspace governance parity;
- formula custom properties;
- a second Portal-specific comment system;
- a second Portal-specific attachment system;
- a second Portal-specific notification center;
- a second Portal-specific task model.

These may be evaluated after the deterministic workflow foundation is stable.

---

## 5. Current CE fork baseline

The current fork already contains useful foundations.

### 5.1 Existing Work Item model

`apps/api/plane/db/models/issue.py` already provides:

- `Issue.state`;
- `Issue.type`;
- `Issue.parent`;
- assignees;
- labels;
- child work items;
- relations;
- comments;
- links;
- attachments;
- subscribers;
- activity/history.

### 5.2 Existing Work Item Type skeleton

`apps/api/plane/db/models/issue_type.py` already includes:

- `IssueType`;
- `ProjectIssueType`;
- workspace ownership;
- per-project assignment;
- default flags;
- hierarchy level.

Do not create a second type model.

### 5.3 Existing project states

`apps/api/plane/db/models/state.py` already provides project-scoped states and state groups:

- backlog;
- unstarted;
- started;
- completed;
- cancelled;
- triage.

Workflow models MUST reference existing `State` records.

### 5.4 Existing state mutation path is not workflow-safe

The current `IssueCreateSerializer` accepts `state_id` and validates primarily that the state belongs to the project.

The normal update path then calls:

```python
serializer.save()
```

There is currently no central:

- workflow resolver;
- transition policy;
- approval gate;
- allow-create validation;
- condition runner.

Therefore workflow enforcement MUST be implemented as a backend service and wired into every path capable of changing `Issue.state_id`.

Frontend-only restrictions are explicitly forbidden.

---

## 6. Core architecture

Introduce a small workflow domain under the API application.

Suggested structure:

```text
apps/api/plane/
├── db/models/
│   ├── workflow.py
│   ├── workflow_approval.py
│   └── workflow_property.py
├── app/serializers/
│   ├── workflow.py
│   └── workflow_approval.py
├── app/views/
│   ├── workflow/
│   └── workflow_approval/
├── app/urls/
│   ├── workflow.py
│   └── workflow_approval.py
├── services/
│   └── workflow/
│       ├── resolver.py
│       ├── transitions.py
│       ├── approvals.py
│       ├── actors.py
│       ├── conditions.py
│       ├── actions.py
│       └── bindings.py
└── bgtasks/
    ├── workflow_post_action_task.py
    └── workflow_notification_task.py
```

Shared code MUST call the service layer rather than reimplement workflow decisions in serializers, views, Celery tasks, MCP handlers, or import code.

---

## 7. Data model

All new records use Plane's existing UUID/base-model conventions, soft deletion conventions where appropriate, and `workspace` / `project` ownership patterns.

### 7.1 Workflow

```python
class Workflow(ProjectBaseModel):
    name
    description
    is_default
    is_active
    created_by
    updated_by
```

Constraints:

- workflow name unique per project among non-deleted rows;
- exactly one non-deleted default workflow per project;
- the default workflow cannot be deleted;
- a custom workflow may be inactive;
- disabling workflow enforcement at project level does not delete configuration.

Recommended project setting:

```python
Project.workflow_enabled: bool = False
```

### 7.2 WorkflowRevision

Workflow configuration is versioned.

```python
class WorkflowRevision(ProjectBaseModel):
    workflow
    version
    status        # draft | published | retired
    published_at
    published_by
```

Constraints:

- `(workflow, version)` unique;
- only one draft revision per workflow;
- one published revision is current for new bindings;
- published revisions are immutable.

Editing a published workflow creates or edits a draft revision. Publishing the draft makes it the current revision.

### 7.3 WorkflowTypeAssignment

```python
class WorkflowTypeAssignment(ProjectBaseModel):
    workflow
    issue_type
```

Constraints:

- one active workflow assignment per `(project, issue_type)`;
- the default workflow does not require an assignment;
- inactive custom workflows are ignored by resolution.

### 7.4 WorkflowState

```python
class WorkflowState(ProjectBaseModel):
    revision
    state
    allow_new_work_items
    sequence
```

Constraints:

- `(revision, state)` unique;
- referenced state must belong to the same project;
- a flow may only reference states included in its revision.

### 7.5 WorkflowFlow

```python
class WorkflowFlow(ProjectBaseModel):
    revision
    source_state
    flow_type       # transition | approval
    target_state
    reject_state    # nullable for transition
    sequence
    is_active
```

Validation:

- `source_state != target_state`;
- transition flow requires `reject_state = NULL`;
- approval flow requires `reject_state != NULL`;
- source/target/reject states must all be in `WorkflowState`;
- all active flows from one source state must have identical `flow_type`;
- V1 API limits approval flows to one active flow per source state.

### 7.6 WorkflowFlowActor

```python
class WorkflowFlowActor(ProjectBaseModel):
    flow
    actor_type
    config          # JSON
    sequence
```

Initial actor types:

```text
ALL_PROJECT_MEMBERS
STATIC_USERS
PROJECT_ROLE
REQUESTER_MANAGER
DEPARTMENT_HEAD
PORTAL_ROLE
PROPERTY_MEMBER
```

Actor resolver contract:

```python
resolve(flow, issue, context) -> set[user_id]
```

No workflow service may interpret actor JSON directly outside `actors.py`.

### 7.7 IssueWorkflowBinding

The fork intentionally pins a running work item to a workflow revision.

```python
class IssueWorkflowBinding(ProjectBaseModel):
    issue             # one-to-one
    workflow
    workflow_revision
    bound_at
    bound_by
    completed_at
    migrated_from_revision
```

Semantics:

- new governed Work Items bind to the current published revision at creation;
- changing the workflow later does not silently change an already-running process;
- legacy Work Items created before workflow support are lazy-bound to the current revision on first workflow-aware state action, or can be backfilled;
- explicit migration of running bindings is deferred to a later admin tool.

This is a fork-specific safety guarantee. Public Commercial docs do not specify revision behavior for already-running items.

### 7.8 WorkflowApproval

```python
class WorkflowApproval(ProjectBaseModel):
    issue
    binding
    flow
    source_state
    status            # pending | approved | rejected | cancelled
    requested_at
    requested_by
    resolved_at
    resolved_by
    resolution_comment
```

Constraints:

- at most one pending approval per Work Item;
- flow must belong to the bound revision;
- approval source state must equal the Work Item's current state when opened.

### 7.9 WorkflowApprovalApprover

Eligible approvers are resolved and snapshotted.

```python
class WorkflowApprovalApprover(ProjectBaseModel):
    approval
    user
    source_type
    source_metadata
    delegated_from
```

Example snapshot:

```json
{
  "source_type": "REQUESTER_MANAGER",
  "source_metadata": {
    "requester_id": "...",
    "resolved_manager_id": "...",
    "resolved_at": "..."
  }
}
```

Org-chart changes after the approval begins MUST NOT silently change the eligible approvers for that approval instance.

### 7.10 WorkflowApprovalDecision

```python
class WorkflowApprovalDecision(ProjectBaseModel):
    approval
    actor
    decision          # approve | reject
    comment
    idempotency_key
```

V1 decision policy:

- any snapshotted eligible approver may decide;
- first committed valid decision resolves the approval;
- later competing decisions receive `409 APPROVAL_ALREADY_RESOLVED`.

The schema should leave room for future policies:

```text
ANY
ALL
QUORUM
```

but only `ANY` is implemented in V1 because Commercial public documentation does not define multi-approver aggregation semantics.

---

## 8. Workflow resolution

Central resolver:

```python
WorkflowResolver.resolve(issue) -> EffectiveWorkflow | None
```

Resolution:

```text
project.workflow_enabled?
        │
        ├─ no ─▶ None
        │
        ▼
active type-specific workflow for issue.type?
        │
        ├─ yes ─▶ current published revision
        │
        └─ no
             │
             ▼
      active project default
```

When `IssueWorkflowBinding` already exists, the binding wins over current configuration.

This prevents a running request from changing behavior when an administrator publishes a new revision.

---

## 9. Creation semantics

### 9.1 Workflows disabled

Behavior remains identical to current CE.

### 9.2 Workflows enabled

Creation must:

1. resolve the effective workflow;
2. resolve its current published revision;
3. verify requested state belongs to the revision;
4. verify `allow_new_work_items = true`;
5. validate required custom properties;
6. create the Work Item;
7. create `IssueWorkflowBinding`;
8. if the initial state has an approval flow, open the approval instance;
9. emit normal Plane activity/webhook events.

If no state is supplied, choose the project's default state only if that state has `allow_new_work_items = true`. Otherwise choose the first allowed state by workflow sequence.

If no state allows creation, reject creation with a configuration error.

Suggested error:

```json
{
  "code": "WORKFLOW_NO_CREATION_STATE",
  "detail": "This workflow has no state that allows new work items."
}
```

---

## 10. Transition semantics

Expose one authoritative service:

```python
TransitionService.transition(
    issue,
    target_state,
    actor,
    origin,
    idempotency_key=None,
    system_bypass=False,
    bypass_reason=None,
)
```

Algorithm:

```text
BEGIN TRANSACTION
    lock Issue row
    resolve/bind workflow
    load current state
    find flow current_state -> target_state
    validate flow type == transition
    resolve actors
    authorize actor
    execute preconditions
    update Issue.state
    sync completed_at using existing semantics
    emit IssueActivity / transition audit
COMMIT

enqueue post-actions
enqueue notifications/webhooks
```

State changes through generic Work Item PATCH MUST call this service.

Do not maintain separate rules in the UI.

### 10.1 Same-state update

A request that supplies the current state again is a no-op and MUST NOT create a workflow transition record.

### 10.2 Approval source state

If the current state has an active approval flow, ordinary state transition requests are blocked until the approval resolves unless an explicit transition flow exists in a future supported model.

V1 cannot mix approval and transition flows from the same state.

---

## 11. Approval lifecycle

### 11.1 Opening approval

Approval is opened when:

- a Work Item enters a state whose flow type is `approval`; or
- a Work Item is directly created in an allowed state whose flow type is `approval`.

Opening:

1. create `WorkflowApproval(status=pending)`;
2. resolve eligible approvers;
3. snapshot them in `WorkflowApprovalApprover`;
4. reject entry if the approver set is empty;
5. notify eligible approvers;
6. expose pending approval status in Work Item detail.

### 11.2 Approve

```text
pending approval
      │
      ├─ actor eligible?
      │      └─ no → 403
      │
      ▼
preconditions
      │
      ├─ fail → stay pending
      │
      ▼
mark approved
      │
      ▼
move issue to target_state
      │
      ▼
open next approval if target state requires one
      │
      ▼
post-actions
```

### 11.3 Reject

Same path, but state becomes `reject_state`.

### 11.4 Concurrency

Approve/reject MUST run inside one DB transaction using row locks.

Minimum lock set:

```text
SELECT ... FOR UPDATE WorkflowApproval
SELECT ... FOR UPDATE Issue
```

Two simultaneous decisions cannot both succeed.

Expected behavior:

```text
Request A: Approve → 200
Request B: Reject  → 409 APPROVAL_ALREADY_RESOLVED
```

### 11.5 Idempotency

Approval endpoints accept an optional `Idempotency-Key`.

Replaying the same decision with the same key returns the original outcome.

---

## 12. Dynamic approver resolution

Portal processes require more than static project members.

### 12.1 STATIC_USERS

Config:

```json
{
  "user_ids": ["..."]
}
```

All IDs must be active users allowed by the flow's project/workspace boundary.

### 12.2 ALL_PROJECT_MEMBERS

All active project members eligible to perform ordinary workflow actions.

### 12.3 PROJECT_ROLE

Example:

```json
{
  "roles": [20]
}
```

Resolve against active `ProjectMember` records.

### 12.4 REQUESTER_MANAGER

Requires a domain organization provider.

Contract:

```python
OrganizationProvider.get_manager(user_id, effective_at) -> user_id | None
```

The workflow engine MUST depend on an interface/provider, not directly on a future People model.

### 12.5 DEPARTMENT_HEAD

Contract:

```python
OrganizationProvider.get_department_head(user_id, effective_at) -> user_id | None
```

### 12.6 PORTAL_ROLE

Example:

```json
{
  "role": "HR_APPROVER"
}
```

This is a domain role, not a Plane project role.

### 12.7 PROPERTY_MEMBER

Config:

```json
{
  "property_id": "...",
  "allow_multiple": false
}
```

Resolve an approver from a member-type custom property on the Work Item.

### 12.8 Empty resolver result

Never auto-approve.

If a required approver resolver returns zero eligible users:

- block entry into the approval state; or
- if discovered while opening an approval, roll back the transition.

Error:

```text
WORKFLOW_APPROVER_NOT_RESOLVED
```

---

## 13. Declarative conditions

Do not implement arbitrary code execution in V1.

### 13.1 WorkflowCondition

```python
class WorkflowCondition(ProjectBaseModel):
    flow
    phase             # pre | post
    condition_type
    config            # JSON
    sequence
    is_active
```

For post-actions it is acceptable to use a separate `WorkflowAction` model if implementation clarity is better.

### 13.2 P1 preconditions

Initial built-ins:

```text
FIELD_REQUIRED
PROPERTY_REQUIRED
PROPERTY_EQUALS
PROPERTY_IN
HAS_ASSIGNEE
HAS_ATTACHMENT
ALL_CHILDREN_COMPLETE
RELATED_ITEM_STATE
USER_HAS_ROLE
ENTITY_STATE_EQUALS
```

Execution contract:

```python
ConditionResult(
    success: bool,
    code: str | None,
    message: str | None,
)
```

All preconditions run in sequence and all must pass.

### 13.3 P1/P2 post-actions

Initial actions:

```text
ADD_COMMENT
ADD_LABEL
ADD_SUBSCRIBER
ASSIGN_USER
CREATE_CHILD_WORK_ITEM
CREATE_LINKED_WORK_ITEM
UPDATE_PROPERTY
SEND_NOTIFICATION
SEND_EMAIL
WEBHOOK
```

Post-actions MUST execute asynchronously after the state transaction commits.

A failed post-action MUST NOT roll back an already-committed transition.

Failures are recorded and retryable.

### 13.4 Future Runner

Arbitrary scripts are deferred until the fork has a reviewed sandbox model including:

- CPU/time limits;
- memory limits;
- no filesystem access;
- no process execution;
- network allowlist;
- secret handling;
- restricted Plane API capabilities;
- execution history;
- kill/retry controls.

---

## 14. Work Item Types and custom properties

Workflows can exist without custom properties, but Portal replacement cannot.

### 14.1 Reuse IssueType

Extend the existing `IssueType`; do not introduce `PortalRequestType`.

### 14.2 Required property types for Portal MVP

```text
TEXT
PARAGRAPH
NUMBER
BOOLEAN
DATE
DATETIME
DROPDOWN
MULTI_SELECT
MEMBER
URL
EMAIL
ENTITY_REFERENCE
```

Later:

```text
RICH_TEXT
FORMULA
```

### 14.3 Proposed models

```text
WorkspaceProperty
    workspace
    name
    property_type
    config
    is_active

IssueTypeProperty
    issue_type
    property
    is_required
    default_value
    sequence

IssuePropertyValue
    issue
    property
    value_json
```

Use one JSON value column with strict type-aware validation instead of adding a database column per custom field.

### 14.4 ENTITY_REFERENCE

The workflow system must be able to reference Portal/domain records without duplicating them into dropdown options.

Example:

```json
{
  "entity_type": "employee",
  "entity_id": "..."
}
```

The domain entity provider owns validation/display.

Examples:

- employee;
- asset;
- department;
- vendor;
- cost center.

---

## 15. Intake and internal request forms

Plane Commercial Intake Forms map naturally to Portal request forms.

### 15.1 External intake remains intake

External anonymous/public submissions continue to use Intake/Triage.

### 15.2 Internal authenticated forms

Add a first-class internal request-form surface.

A form defines:

```text
RequestForm
 ├─ workspace
 ├─ project
 ├─ title
 ├─ description
 ├─ issue_type
 ├─ allowed properties
 ├─ default state
 ├─ requester mapping
 └─ active
```

Submitting the form creates an ordinary typed Work Item and immediately enters its effective workflow.

Suggested UI:

```text
Requests
├── Leave request
├── Expense claim
├── IT equipment request
├── Purchase request
├── Onboarding
└── Offboarding
```

The resulting item remains visible through normal Plane views, filters, timelines, dashboards, APIs, and agents.

---

## 16. Portal process mappings

### 16.1 Leave request

```text
Submitted
    │
    ▼
Manager Approval
    ├─ reject ─▶ Rejected
    └─ approve
          │
          ▼
      HR Approval
          ├─ reject ─▶ Rejected
          └─ approve ─▶ Approved
```

Approvers:

```text
Manager Approval → REQUESTER_MANAGER
HR Approval      → PORTAL_ROLE(HR_APPROVER)
```

Suggested properties:

- requester;
- leave type;
- start date;
- end date;
- number of days;
- reason;
- supporting attachment.

### 16.2 Equipment request

```text
Submitted
   │
   ▼
Manager Approval
   │
   ▼
IT Review
   ├─ asset available ─▶ Allocation ─▶ Fulfilled
   └─ purchase needed ─▶ Procurement Requested
                               │
                               ▼
                      linked Purchase Work Item
                               │
                               ▼
                            Allocation
```

### 16.3 Onboarding

Parent Work Item:

```text
ONBOARD-123
```

Post-action creates child/cross-project fulfillment work:

```text
├── HR: verify employee record
├── IT: create accounts
├── IT: prepare machine
├── Office: prepare desk/access card
└── Manager: onboarding plan
```

Final transition condition:

```text
ALL_CHILDREN_COMPLETE
```

### 16.4 Offboarding

```text
Submitted
    │
    ▼
Manager/HR Approval
    │
    ▼
Fulfillment
    ├── IT revoke accounts
    ├── IT recover equipment
    ├── Office recover card/key
    ├── HR finalize records
    └── Manager confirm handover
    │
    ▼
ALL_CHILDREN_COMPLETE
    │
    ▼
Closed
```

### 16.5 Expense claim

Expense line items and receipts may require a dedicated domain table because they are one-to-many structured financial data.

The process itself remains a Work Item:

```text
ExpenseClaim domain record
        ▲
        │ ENTITY_REFERENCE
        │
    Work Item
        │
        ▼
Approval Workflow
```

Do not force complex line-item accounting data into Work Item custom properties.

---

## 17. API design

Use current Plane API naming conventions and workspace/project boundaries.

### 17.1 Workflow administration

Suggested routes:

```text
GET    /api/workspaces/:slug/projects/:project_id/workflows/
POST   /api/workspaces/:slug/projects/:project_id/workflows/

GET    /api/workspaces/:slug/projects/:project_id/workflows/:workflow_id/
PATCH  /api/workspaces/:slug/projects/:project_id/workflows/:workflow_id/
DELETE /api/workspaces/:slug/projects/:project_id/workflows/:workflow_id/

POST   /api/.../workflows/:workflow_id/draft/
POST   /api/.../workflows/:workflow_id/publish/
GET    /api/.../workflows/:workflow_id/revisions/
```

### 17.2 Flow configuration

```text
POST   /api/.../workflow-revisions/:revision_id/states/
PATCH  /api/.../workflow-revisions/:revision_id/states/:state_id/
DELETE /api/.../workflow-revisions/:revision_id/states/:state_id/

POST   /api/.../workflow-revisions/:revision_id/flows/
PATCH  /api/.../workflow-revisions/:revision_id/flows/:flow_id/
DELETE /api/.../workflow-revisions/:revision_id/flows/:flow_id/
```

Only draft revisions are mutable.

### 17.3 Runtime actions

```text
GET  /api/workspaces/:slug/projects/:project_id/issues/:issue_id/workflow/
GET  /api/workspaces/:slug/projects/:project_id/issues/:issue_id/workflow/actions/

POST /api/workspaces/:slug/projects/:project_id/issues/:issue_id/transitions/
POST /api/workspaces/:slug/projects/:project_id/issues/:issue_id/approvals/:approval_id/approve/
POST /api/workspaces/:slug/projects/:project_id/issues/:issue_id/approvals/:approval_id/reject/
```

Example actions response:

```json
{
  "workflow": {
    "id": "...",
    "revision": 3
  },
  "state": {
    "id": "...",
    "name": "Manager Approval"
  },
  "approval": {
    "status": "pending",
    "can_decide": true
  },
  "transitions": []
}
```

For a normal transition state:

```json
{
  "approval": null,
  "transitions": [
    {
      "flow_id": "...",
      "target_state_id": "...",
      "target_state_name": "In Review",
      "allowed": true
    }
  ]
}
```

### 17.4 Compatibility with existing PATCH

Existing clients already update `state_id` through the normal Work Item update API.

Do not immediately break that API.

When workflows are enabled:

- if `state_id` is unchanged, continue normally;
- if `state_id` changes, route the change through `TransitionService`;
- if the requested change is not an allowed transition, return a workflow error;
- approval cannot be bypassed by PATCHing directly to the approval target.

---

## 18. Permission model

### 18.1 Workflow configuration

Default V1:

- Project Admin: configure project workflows;
- Workspace Admin: configure workflows for any accessible project;
- Member: read effective workflow metadata and perform allowed actions;
- Guest: only actions explicitly allowed by existing project permissions plus flow policy;
- service principal: must satisfy service-token scopes and workflow actor rules.

### 18.2 Actor rule does not replace ACL

A flow actor rule is an additional gate.

Required:

```text
base Plane authorization
        AND
workflow actor authorization
        AND
preconditions
```

A `STATIC_USERS` entry does not grant a user project access by itself.

### 18.3 Service tokens

Service-token authorization must not bypass workflow transitions.

A service token changing state must:

- have the required write scope;
- satisfy resource boundary;
- satisfy workflow actor policy unless using an explicit privileged system-bypass path.

---

## 19. Workflow bypass policy

Some internal operations need controlled bypasses, such as migrations.

Never bypass implicitly based on code path.

Required API at service layer:

```python
system_bypass=True
bypass_reason="migration: backfill imported issue states"
```

Every bypass MUST be audited with:

- actor/service principal;
- issue;
- previous state;
- new state;
- reason;
- timestamp;
- origin.

Production application code should contain very few bypass call sites.

---

## 20. State mutation audit

Before implementation, inventory every location that may mutate `Issue.state` or `Issue.state_id`.

At minimum review:

- normal create;
- normal PATCH;
- bulk update;
- Intake accept;
- importers;
- archive/restore side effects;
- recurring work items;
- automation;
- API v1/v2;
- PAT;
- workspace/instance service token paths;
- MCP;
- mobile-backed API routes;
- Celery tasks;
- internal maintenance tasks.

Acceptance rule:

> Every state mutation either calls `TransitionService` or uses a documented audited bypass.

Direct `Issue.objects.filter(...).update(state=...)` for user-facing process transitions is forbidden after workflow enforcement ships.

---

## 21. Activity and transition history

Plane already records Issue activity. Preserve that.

Add workflow-specific structured records rather than relying only on display text.

The Work Item UI should be able to show:

```text
Transition
──────────
Submitted → Manager Approval
Huy Doan • Sep 26, 09:10

Approval requested
Manager Approval
Approver: Nguyễn B

Approved
Manager Approval → HR Approval
Nguyễn B • Sep 26, 10:02
Comment: Approved
```

Bot/service actions must identify the service principal.

---

## 22. Notifications

Approval open:

- notify snapshotted approvers;
- create Inbox notification;
- optionally email according to user preferences.

Approval resolved:

- notify requester/creator;
- notify subscribers;
- notify assignees where normal Plane notification policy applies.

Avoid duplicate notification paths if Issue activity already triggers equivalent notifications.

V1 does not require a separate "Portal Inbox."

---

## 23. Frontend UX

### 23.1 Project Settings → Workflows

Add:

```text
Project Settings
└── Workflows
```

List columns:

- name;
- Default badge;
- Active/Inactive;
- assigned Work Item Types;
- modified date.

Controls:

- search;
- active/inactive filter;
- type filter;
- create workflow;
- enable/disable workflows at project level.

### 23.2 Workflow detail

Prefer Commercial-like configuration, not a graph editor.

```text
Workflow: Leave Request

● Submitted
  Allow new work items   [✓]
  └─ Transition → Manager Approval
     By: All

● Manager Approval
  Allow new work items   [ ]
  └─ Approval
     Approve → HR Approval
     Reject  → Rejected
     By      → Requester's manager

● HR Approval
  ...
```

### 23.3 Work Item detail

When approval pending:

- show `Approval pending` badge near the identifier/header;
- show Approve / Reject only to eligible approvers;
- non-approvers see who/what role is pending without exposing hidden membership data;
- optional decision comment;
- state selector must not expose illegal destinations.

### 23.4 State dropdown

With workflows enabled, state dropdown options come from runtime workflow actions, not from the full project-state list.

### 23.5 Error UX

Backend blocker messages must be displayed directly.

Examples:

```text
This transition is not allowed by the current workflow.
Manager approval is required before this item can move forward.
All onboarding tasks must be completed first.
No approver could be resolved for this step.
```

---

## 24. Revision publishing

### 24.1 Draft editing

Administrators edit a draft revision without affecting running/new items.

### 24.2 Publish

Publishing:

1. validates the entire revision;
2. marks previous current revision retired;
3. makes new revision current for future bindings;
4. preserves old revisions while bound issues exist.

Validation checklist:

- at least one state;
- at least one state allows creation;
- all flow states are included;
- source-state flow-type invariant holds;
- no duplicate transition destinations;
- approval reject state present;
- actor configuration valid;
- no active approval state with unresolved actor configuration.

### 24.3 Deletion

A workflow referenced by bindings cannot be hard-deleted.

Archive/soft-delete configuration instead.

Existing bindings continue to resolve their revision.

---

## 25. Migration and rollout

### Phase 0 — Schema only

Add models and migrations without enabling workflows.

No existing behavior changes.

### Phase 1 — Workflow service behind feature flag

Recommended instance flag:

```text
ENABLE_WORKFLOWS=true
```

Project-level `workflow_enabled` remains false by default.

### Phase 2 — Default workflow bootstrap

When a project first enables workflows:

1. create default `Workflow`;
2. create revision 1;
3. include all current non-triage states;
4. mark current project default state `allow_new_work_items=true`;
5. preserve compatibility by creating transition flows between every distinct state pair initially.

This bootstrap prevents enabling workflows from unexpectedly freezing existing project behavior.

Admins can then remove transitions to tighten the process.

### Phase 3 — Binding

New Work Items bind immediately.

Existing Work Items:

- remain unbound initially;
- are lazy-bound on first state-changing workflow action;
- optional background backfill can bind active items after validation.

### Phase 4 — Approvals

Enable approval flow configuration only after transition enforcement is proven stable.

### Phase 5 — Portal pilots

Recommended order:

1. Leave Request;
2. IT Equipment Request;
3. Onboarding;
4. Offboarding;
5. Expense / Procurement.

Use real operational feedback before generalizing additional workflow primitives.

---

## 26. Failure semantics

### 26.1 Preconditions

Failure:

- transaction does not change state;
- user receives actionable message;
- failure may be logged for diagnostics but is not an Issue transition.

### 26.2 Post-actions

Failure:

- transition remains committed;
- record execution error;
- retry according to action policy;
- surface failure to admins/operators.

### 26.3 Notification failure

Does not roll back process transition.

### 26.4 Resolver failure

Dynamic approver resolver failure blocks opening an approval.

Never silently fall back to "All."

---

## 27. Performance

Workflow runtime lookup occurs on common Work Item mutation paths, so avoid N+1 queries.

Runtime fetch should be able to preload:

- binding;
- revision;
- workflow states;
- source flows;
- actors;
- conditions.

Recommended indexes:

```text
Workflow(project_id, is_active, is_default)
WorkflowTypeAssignment(project_id, issue_type_id)
WorkflowRevision(workflow_id, status)
WorkflowState(revision_id, state_id)
WorkflowFlow(revision_id, source_state_id, is_active)
IssueWorkflowBinding(issue_id)
WorkflowApproval(issue_id, status)
WorkflowApprovalApprover(approval_id, user_id)
```

Cache immutable published revision configuration if profiling shows benefit.

Authorization and approval status remain DB-backed and must not use stale cache for writes.

---

## 28. Security invariants

These are release blockers.

1. A client cannot bypass workflow by directly PATCHing `state_id`.
2. PAT cannot bypass workflow.
3. service access token cannot bypass workflow.
4. MCP cannot bypass workflow.
5. bulk update cannot bypass workflow.
6. Intake accept cannot enter a forbidden state.
7. approver identity is checked server-side.
8. frontend hidden buttons are never the authorization boundary.
9. approval is concurrency-safe.
10. empty dynamic approver result never means auto-approve.
11. published workflow revision is immutable.
12. running Work Items remain pinned to their revision.
13. explicit bypasses are audited.
14. actor resolver does not grant base project access.
15. post-action failure cannot corrupt the committed state transition.

---

## 29. Test matrix

### 29.1 Workflow resolution

- default workflow resolves;
- type-specific workflow overrides default;
- inactive type workflow falls back to default;
- existing binding wins over newly published revision;
- workflows disabled returns no enforcement.

### 29.2 Creation

- allowed initial state succeeds;
- forbidden initial state fails;
- no supplied state selects valid allowed state;
- no allowed creation state returns configuration error;
- required custom property missing fails;
- approval state creation opens approval.

### 29.3 Transition

- allowed transition succeeds;
- missing flow fails;
- unauthorized actor fails;
- project outsider fails;
- same-state update no-op;
- precondition failure keeps old state;
- target completed state preserves existing `completed_at` semantics.

### 29.4 Approval

- eligible approver approves;
- eligible approver rejects;
- ineligible user fails;
- second concurrent decision returns 409;
- same idempotency key is replay-safe;
- approval opens next approval state;
- reject target may itself have normal flows;
- empty approver resolver rolls back entry;
- org chart changes do not mutate snapshotted approvers.

### 29.5 Bypass attempts

Test each state write path:

- web;
- REST API;
- PAT;
- service token;
- MCP;
- bulk update;
- Intake;
- import;
- background task.

### 29.6 Revision behavior

- draft does not affect runtime;
- publish affects new items;
- running item remains on old revision;
- old revision cannot be deleted while referenced.

### 29.7 UI

- illegal states absent from picker;
- approval buttons visible only when eligible;
- pending badge visible;
- blocker error rendered;
- workflow editor enforces same-type flows per source state.

---

## 30. Implementation breakdown

### P0.1 — Models and migrations

- add `Project.workflow_enabled`;
- add Workflow;
- add WorkflowRevision;
- add WorkflowTypeAssignment;
- add WorkflowState;
- add WorkflowFlow;
- add WorkflowFlowActor;
- add IssueWorkflowBinding;
- constraints/indexes;
- model tests.

### P0.2 — Workflow administration API

- workflow CRUD;
- draft lifecycle;
- workflow-state CRUD;
- transition-flow CRUD;
- actor CRUD;
- revision validation/publish;
- permissions;
- API tests.

### P0.3 — Resolver and transition service

- effective workflow resolver;
- binding service;
- allowed action computation;
- transition actor resolver;
- transaction service;
- structured workflow errors.

### P0.4 — State mutation integration

Audit and route all existing state mutation paths through the service.

This task is not complete until bypass tests cover the known write surfaces.

### P0.5 — Workflow settings UI

- settings list;
- workflow create/edit;
- state inclusion;
- allow-create;
- transition editor;
- type assignment;
- active toggle;
- revision publish.

### P1.1 — Approval models and APIs

- WorkflowApproval;
- WorkflowApprovalApprover;
- WorkflowApprovalDecision;
- approve/reject endpoints;
- row locking;
- idempotency;
- audit.

### P1.2 — Approval UI

- pending badge;
- approve/reject controls;
- decision comment;
- approval activity;
- notification integration.

### P1.3 — Dynamic approver provider layer

- actor resolver registry;
- requester manager;
- department head;
- portal role;
- member property;
- approver snapshot metadata.

### P1.4 — Work Item custom properties

- workspace property model;
- type-property association;
- values;
- validation;
- API;
- form renderer;
- Work Item detail renderer.

### P2.1 — Declarative conditions/actions

- condition registry;
- built-in preconditions;
- action registry;
- async post-action execution;
- retry/error history.

### P2.2 — Internal request forms

- form model;
- property selection;
- authenticated submit route;
- request landing page;
- create Work Item through workflow-safe service.

### P2.3 — Portal process templates

Ship example/configuration templates for:

- Leave Request;
- Equipment Request;
- Onboarding;
- Offboarding;
- Expense Claim;
- Purchase Request.

### P2.4 — SLA/reminders

Later P2:

- approval due date;
- reminder schedule;
- escalation target;
- overdue flag;
- deterministic Celery jobs.

---

## 31. Acceptance criteria for first production milestone

The first production milestone is complete when all are true:

1. An admin can enable workflows for a project.
2. Plane creates a compatibility-safe default workflow.
3. Admin can remove transitions and thereby restrict state movement.
4. Illegal direct PATCH to another state is blocked.
5. PAT/service-token/API calls obey the same rules.
6. A type-specific workflow can override the default.
7. Admin can configure one approval flow on a state.
8. Entering the approval state creates a pending approval.
9. Only eligible approvers can approve/reject.
10. Approve/reject moves to configured destinations transactionally.
11. Running items remain pinned to their workflow revision.
12. Work Item activity shows workflow/approval actions.
13. Workflow settings and Work Item detail UI are usable without a graph editor.
14. Automated tests prove common workflow bypass attempts fail.

Portal rollout begins only after these criteria pass.

---

## 32. Product direction after V1

After core workflows and approvals stabilize, the preferred evolution path is:

```text
Plane Work Item
     │
     ├── Work Item Type
     ├── Custom Properties
     ├── Workflow / Approval
     ├── Intake / Request Form
     ├── Child / Related Work Items
     ├── Organization / Asset references
     └── Declarative automation
```

This allows the internal Portal to become a set of Plane-native business capabilities instead of a separate workflow product.

Workspace Governance and a secure Runner may be added later, but neither is required to replace the initial HR/IT request workflows.

---

## 33. Source references

Commercial/public behavior baseline:

- Plane Workflows and Approvals  
  https://docs.plane.so/workflows-and-approvals/workflows

- Workspace Work Item Types  
  https://docs.plane.so/work-items/workspace-work-item-types

- Intake Forms  
  https://docs.plane.so/intake/intake-forms

- Plane Runner  
  https://docs.plane.so/automations/plane-runner

Current fork implementation baseline:

- `apps/api/plane/db/models/issue.py`
- `apps/api/plane/db/models/issue_type.py`
- `apps/api/plane/db/models/state.py`
- `apps/api/plane/app/serializers/issue.py`
- `apps/api/plane/app/views/issue/base.py`

---

## 34. Key implementation rule

The project should preserve one architectural invariant above all others:

> **Work Item state is no longer a freely writable property once a workflow governs the item. It is the result of an authorized workflow transition or approval decision.**

Everything — web UI, API, PAT, service tokens, MCP, automation, import paths, and future mobile support — must obey that invariant.
