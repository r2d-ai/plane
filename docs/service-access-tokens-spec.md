# Service Access Tokens — Workspace and Instance Scope

**Status:** Proposed / implementation-ready  
**Target:** Plane CE fork `r2d-ai/plane`  
**Branch:** `master`  
**Primary use case:** MCP and AI agents that must operate as a workspace-level or instance-level service identity, including daily/weekly digest jobs across multiple workspaces.  
**Compatibility requirement:** Existing Personal Access Tokens (PATs) and session authentication must continue to work unchanged.

---

## 1. Problem

Plane CE currently exposes Personal Access Tokens through `APIToken`. A PAT authenticates as its owning user.

The current model already contains:

- `APIToken.is_service`
- `APIToken.workspace`
- `APIToken.allowed_rate_limit`
- `User.is_bot`

but service tokens are not a complete service-principal implementation.

Current API-key authentication resolves a token to:

```python
(api_token.user, api_token.token)
```

and current workspace/project authorization and multiple API querysets still depend on:

```python
request.user
WorkspaceMember(member=request.user)
ProjectMember(member=request.user)
```

Therefore a token marked `is_service=True` is still effectively constrained by the backing user's memberships. It cannot reliably act as a workspace-level or instance-level service principal.

This blocks:

- MCP agents acting on behalf of a whole workspace.
- Daily/weekly workspace digests without creating a privileged human user.
- Instance-wide digest/reporting across all workspaces.
- Central AI agents that need stable access independent of a specific employee account.
- Long-running automation that must survive the creator leaving or being deactivated.

---

## 2. Goals

### P0 goals

1. Add **Workspace Access Tokens (WSAT)**.
2. Add **Instance Access Tokens (IAT)**.
3. Implement service-principal authorization independent from human `WorkspaceMember` / `ProjectMember` membership.
4. Keep an internal bot user as the technical actor so existing FK/audit code using `request.user` remains compatible.
5. Add explicit token scopes.
6. Add a public API token-context endpoint so MCP can discover whether a token is personal, workspace-scoped, or instance-scoped.
7. Add a public API workspace-discovery endpoint usable by instance-level agents.
8. Support read-only daily/weekly digest use cases across all workspaces.
9. Store new service-token secrets hashed; never persist the raw secret.
10. Add create/list/revoke UI/API for workspace and instance admins.
11. Preserve all existing PAT behavior.

### P1 goals

- Rotate token without changing token identity.
- Fine-grained project allowlists.
- IP/CIDR allowlists.
- Per-token audit-log viewer.
- Per-token rate-limit customization.
- Additional write scopes.
- MCP helper tools for instance-wide aggregation.

### Non-goals for P0

- Replacing PATs.
- OAuth2 client credentials.
- User impersonation.
- Project-specific tokens.
- Making instance tokens equivalent to instance super-admin.
- Automatically adding service bots to every workspace/project.
- Exposing hidden service bot users in ordinary member pickers.

---

## 3. Design principles

### 3.1 Service identity is not a human identity

A service token must not inherit permissions from the human that created it.

The creator is only the provisioner/audit owner.

If Alice creates a token and Alice is later disabled or removed, the token continues to work until it expires or is revoked.

### 3.2 Resource boundary and permission scope are separate

`scope_level=instance` means the token may target resources in every workspace.

It does **not** mean the token may perform every action.

Example:

```text
scope_level = instance
scopes = [
  "workspaces:read",
  "projects:read",
  "work_items:read",
  "cycles:read",
  "modules:read"
]
```

This token can build a company-wide digest but cannot mutate work items, users, instance settings, or tokens.

### 3.3 No synthetic membership fan-out

Do not implement instance access by creating the bot as a member of every workspace/project.

Reasons:

- Pollutes member lists and assignee pickers.
- Requires synchronization whenever a workspace/project is created.
- Creates accidental human-style permissions.
- Makes revocation and permission reasoning harder.
- Does not scale cleanly.

Authorization must understand service principals directly.

### 3.4 Existing `request.user` contract remains valid

Many models/tasks use `request.user`, `created_by=request.user`, or `actor_id=request.user.id`.

A service token therefore uses a hidden bot `User` as its technical actor.

Authorization, however, is derived from the authenticated `APIToken`, not from bot membership.

---

## 4. Current code baseline

Relevant existing code on `master`:

- `apps/api/plane/db/models/api.py`
  - `APIToken` already has `workspace`, `is_service`, `allowed_rate_limit`.
- `apps/api/plane/api/middleware/api_authentication.py`
  - API key resolves to `api_token.user`.
- `apps/api/plane/utils/permissions/workspace.py`
  - Workspace authorization checks `WorkspaceMember(member=request.user)`.
- `apps/api/plane/utils/permissions/project.py`
  - Project authorization checks `ProjectMember(member=request.user)`.
- `apps/api/plane/api/views/project.py`
  - Project list queryset filters and annotates using `request.user`.
- `apps/api/plane/app/views/api.py`
  - Personal token endpoint explicitly filters `is_service=False`.
- `apps/api/plane/license/api/permissions/instance.py`
  - `InstanceAdminPermission` is the existing instance-admin authorization entry point.
- `apps/api/plane/api/rate_limit.py`
  - Current throttle cache key contains the raw `X-Api-Key`.

The implementation must account for both permission classes **and** queryset filtering. Passing permission checks while querysets still filter by the bot user is considered incorrect.

---

## 5. Token types

| Type | Prefix | Principal | Resource boundary | Typical use |
|---|---|---|---|---|
| Personal PAT | `plane_api_` | Human/bot user | User memberships | Personal scripts |
| Workspace Access Token | `plane_wsat_` | Hidden service bot | One workspace | Team agent, workspace MCP |
| Instance Access Token | `plane_iat_` | Hidden service bot | All active workspaces | Central MCP, daily/weekly digest |

Token prefix is informational only. Authorization must use persisted token metadata, not trust the prefix.

---

## 6. Data model

Extend `APIToken`; do not create a parallel authentication table.

### 6.1 Proposed fields

```python
class APIToken(BaseModel):
    # Existing
    label
    description
    is_active
    last_used
    token                 # legacy raw PAT; nullable after migration
    user                  # human or backing service bot
    user_type
    workspace             # workspace boundary for WSAT
    expired_at
    is_service
    allowed_rate_limit

    # New
    scope_level           # "user" | "workspace" | "instance"
    scopes                # JSONField(list[str])
    token_prefix          # safe display prefix
    token_hash            # SHA-256 hash for new service tokens
    revoked_at            # nullable
    revoked_by            # nullable FK User
```

Suggested choices:

```python
class APITokenScopeLevel(models.TextChoices):
    USER = "user", "User"
    WORKSPACE = "workspace", "Workspace"
    INSTANCE = "instance", "Instance"
```

### 6.2 Constraints

Enforce in model validation and serializer validation:

- `scope_level=user`
  - legacy PAT behavior.
  - `workspace` may remain as existing legacy data requires.
- `scope_level=workspace`
  - `is_service=True`
  - `workspace IS NOT NULL`
  - backing `user.is_bot=True`
- `scope_level=instance`
  - `is_service=True`
  - `workspace IS NULL`
  - backing `user.is_bot=True`
- Service tokens must have a non-empty `scopes` list.
- A revoked token cannot authenticate.
- Expired token cannot authenticate.

Add DB constraints where practical, but retain application validation for readable errors.

### 6.3 Service bot user

Add:

```python
class BotTypeEnum(models.TextChoices):
    WORKSPACE_SEED = "WORKSPACE_SEED", "Workspace Seed"
    SERVICE_TOKEN = "SERVICE_TOKEN", "Service Token"
```

Recommended service user properties:

```text
is_bot = true
bot_type = SERVICE_TOKEN
is_active = true
display_name = token label
email = deterministic internal/non-routable address
```

The bot exists to satisfy current actor/FK contracts.

It must not:

- receive normal notifications,
- appear in standard workspace/member lists,
- be selectable as an assignee unless explicitly supported later,
- require `WorkspaceMember` or `ProjectMember` records.

One bot per service token is the simplest P0 lifecycle model. Revoking/deleting the token may deactivate the corresponding bot if it has no other service tokens.

---

## 7. Secret generation and storage

### 7.1 New service tokens

Generate at least 256 bits of entropy with Python `secrets`.

Examples:

```text
plane_wsat_<url-safe-random-secret>
plane_iat_<url-safe-random-secret>
```

Do not use `uuid4().hex` as the complete service-token secret.

### 7.2 Hash storage

For WSAT/IAT:

```text
raw secret
   |
SHA-256
   |
token_hash stored in DB
```

Persist only:

- `token_hash`
- `token_prefix`
- metadata

Return the raw token **only once** in the create response.

Do not return it from subsequent GET/list endpoints.

SHA-256 is acceptable because the input is a high-entropy random secret; this is not a human password.

### 7.3 Legacy PAT compatibility

Existing PATs currently live in `APIToken.token`.

Migration strategy:

1. Make `token` nullable/blankable.
2. Keep all existing raw PAT values unchanged.
3. Authentication path:
   - WSAT/IAT -> lookup by `token_hash`.
   - legacy `plane_api_` -> existing raw-token lookup.
4. Do not migrate existing PATs to hashes in P0.

This avoids invalidating deployed integrations.

---

## 8. Authentication context

Update `APIKeyAuthentication.authenticate()`.

For every successful API-key authentication, attach:

```python
request.api_token = api_token
```

For a service token also attach:

```python
request.service_token = api_token
```

Keep:

```python
request.user = api_token.user
request.auth = <existing-compatible auth value>
```

Do not require callers to parse token prefixes.

### 8.1 Authentication validation

A token is valid only when:

- `is_active=True`
- `revoked_at IS NULL`
- not expired
- backing user is active
- service-token hash matches
- token data is internally consistent

Update `last_used` after successful authentication.

Avoid unnecessary write amplification: updating `last_used` on every request may become expensive for MCP. P0 may retain current behavior, but preferred implementation is throttled/batched last-used updates (for example at most once per minute per token).

---

## 9. Authorization architecture

Add a single service-principal helper module, for example:

```text
apps/api/plane/api/auth/service_principal.py
```

Required helpers:

```python
get_api_token(request)
is_service_principal(request)
has_service_scope(request, scope)
service_token_allows_workspace(request, workspace_or_slug)
require_service_scope(request, scope)
```

Optional higher-level helpers:

```python
authorize_workspace(request, slug, scope, fallback_user_check)
authorize_project(request, slug, project_id, scope, fallback_user_check)
```

### 9.1 Authorization rule

Every API permission follows:

```text
if service principal:
    validate resource boundary
    validate required token scope
    return allow/deny
else:
    execute existing PAT/user membership logic unchanged
```

Human membership checks must not be applied to service principals.

### 9.2 Workspace boundary

Workspace token:

```text
token.scope_level = workspace
token.workspace.slug = tech
```

Allowed:

```text
/api/v1/workspaces/tech/...
```

Denied:

```text
/api/v1/workspaces/marketing/...
=> 403
```

Instance token:

```text
token.scope_level = instance
token.workspace = NULL
```

may target any active workspace if its operation scope permits the action.

### 9.3 Project access

P0 workspace/instance service tokens operate at workspace scope.

They do not require `ProjectMember` entries.

A service token with:

```text
projects:read
```

can read every project in each workspace inside its resource boundary.

A future P1 project allowlist can narrow this.

---

## 10. Scope model

Use explicit strings and central constants. Do not scatter raw literals across views.

### 10.1 P0 scopes

```text
workspaces:read

projects:read
projects:write

work_items:read
work_items:write

cycles:read
cycles:write

modules:read
modules:write

states:read
states:write

labels:read
labels:write

workspaces.members:read

wiki.pages:read
wiki.pages:write
```

If a corresponding public API does not yet exist, the scope may be reserved but must not imply an unsupported endpoint.

### 10.2 Explicitly excluded from P0 instance-token scopes

Do not expose scopes that permit:

- instance configuration changes,
- instance admin management,
- token management,
- authentication configuration,
- email/SMTP secrets,
- LLM/provider secrets,
- destructive workspace deletion.

These remain session/admin operations.

### 10.3 Scope mapping

Use method-aware mapping.

Example:

| Resource | GET/HEAD | POST/PATCH/PUT/DELETE |
|---|---|---|
| projects | `projects:read` | `projects:write` |
| work items | `work_items:read` | `work_items:write` |
| cycles | `cycles:read` | `cycles:write` |
| modules | `modules:read` | `modules:write` |
| states | `states:read` | `states:write` |
| labels | `labels:read` | `labels:write` |
| members | `workspaces.members:read` | not P0 |
| wiki pages | `wiki.pages:read` | `wiki.pages:write` |

A `:write` scope does not automatically imply unrelated read scopes unless explicitly documented. UI presets should include both when needed.

---

## 11. Queryset authorization — mandatory

Permission classes are only half the implementation.

Existing API endpoints often filter resources using `request.user`.

Example pattern:

```python
Project.objects.filter(...)
    .filter(
        Q(project_projectmember__member=request.user, ...)
        | Q(network=2)
    )
```

For service principals this would incorrectly hide projects because the backing service bot has no `ProjectMember`.

Introduce reusable queryset helpers, for example:

```python
filter_projects_for_api_principal(queryset, request, workspace_slug)
filter_work_items_for_api_principal(queryset, request, workspace_slug, project_id=None)
```

Required behavior:

```text
service token:
  authorize by token boundary + token scopes
  filter by workspace/project resource identifiers only

personal PAT:
  preserve current membership/network logic exactly
```

### Acceptance rule

A feature is **not complete** if:

- permission class accepts an instance/workspace token,
- but returned data is empty/incomplete because a queryset still assumes `request.user` membership.

Audit every P0 `/api/v1/` endpoint for this pattern.

---

## 12. Public API additions

### 12.1 Token context

Add:

```http
GET /api/v1/auth/context/
X-Api-Key: <token>
```

Personal PAT response:

```json
{
  "principal_type": "user",
  "scope_level": "user",
  "is_service": false,
  "workspace": null,
  "scopes": null
}
```

Workspace token response:

```json
{
  "principal_type": "service",
  "scope_level": "workspace",
  "is_service": true,
  "workspace": {
    "id": "...",
    "slug": "tech",
    "name": "Tech"
  },
  "scopes": [
    "workspaces:read",
    "projects:read",
    "work_items:read"
  ]
}
```

Instance token response:

```json
{
  "principal_type": "service",
  "scope_level": "instance",
  "is_service": true,
  "workspace": null,
  "scopes": [
    "workspaces:read",
    "projects:read",
    "work_items:read"
  ]
}
```

Never return:

- raw token,
- token hash,
- hidden bot email,
- sensitive creator metadata.

### 12.2 Workspace discovery

Add:

```http
GET /api/v1/workspaces/
```

Required scope for service tokens:

```text
workspaces:read
```

Behavior:

**Personal PAT**
- return only active workspaces visible to the PAT user using existing membership rules.

**Workspace token**
- return exactly its bound active workspace.

**Instance token**
- return all active workspaces in the instance.

Response should use `WorkspaceLiteSerializer`:

```json
[
  {
    "id": "...",
    "name": "Tech",
    "slug": "tech"
  }
]
```

This endpoint is required for instance-level MCP discovery.

---

## 13. Management API

These endpoints use normal session authentication, not service-token authentication.

### 13.1 Workspace token management

Suggested endpoints:

```http
GET  /api/workspaces/{slug}/service-tokens/
POST /api/workspaces/{slug}/service-tokens/
GET  /api/workspaces/{slug}/service-tokens/{id}/
PATCH /api/workspaces/{slug}/service-tokens/{id}/
DELETE /api/workspaces/{slug}/service-tokens/{id}/
```

DELETE means revoke, not hard-delete.

Required permission:

- workspace role **Admin (20)** only.

Do not reuse a permission class that also admits ordinary Member (15).

POST example:

```json
{
  "label": "Daily Digest",
  "description": "Read-only MCP digest agent",
  "expired_at": null,
  "scopes": [
    "workspaces:read",
    "projects:read",
    "work_items:read",
    "cycles:read",
    "modules:read",
    "workspaces.members:read"
  ]
}
```

Create response may return secret once:

```json
{
  "id": "...",
  "label": "Daily Digest",
  "scope_level": "workspace",
  "workspace": {
    "id": "...",
    "slug": "tech"
  },
  "scopes": [...],
  "token": "plane_wsat_..."
}
```

List/detail responses must exclude `token`.

### 13.2 Instance token management

Suggested endpoints:

```http
GET  /api/instances/service-tokens/
POST /api/instances/service-tokens/
GET  /api/instances/service-tokens/{id}/
PATCH /api/instances/service-tokens/{id}/
DELETE /api/instances/service-tokens/{id}/
```

Required permission:

- existing `InstanceAdminPermission`, or stricter instance-admin role if desired.
- never accessible by an instance service token itself.

Instance tokens may only be created from an authenticated admin session.

### 13.3 Editable fields

After creation allow:

- label
- description
- expiry
- active/revoked state through explicit action
- scopes, if implementation performs a security-conscious update

Do not allow changing:

- token raw secret
- scope level
- bound workspace
- backing user
- creator

Changing workspace/instance boundary requires creating a new token.

---

## 14. UI

### 14.1 Workspace settings

Add:

```text
Workspace Settings
  -> Access Tokens
```

List columns/cards:

- Name
- Description
- Access preset / scope summary
- Created by
- Created at
- Last used
- Expiration
- Status
- Actions: edit metadata, revoke

Create dialog:

```text
Create access token

Name
Description
Expiration

Access
  ( ) Read only
  ( ) Read + write
  ( ) Custom

Permissions
  [x] Projects: read
  [ ] Projects: write
  [x] Work items: read
  [ ] Work items: write
  ...
```

After creation:

```text
Copy this token now.
It will not be shown again.

plane_wsat_...
[Copy]
```

Require an explicit confirmation before closing if the secret has not been copied, if practical.

### 14.2 Instance admin

Add:

```text
Instance Admin
  -> Access Tokens
```

Clearly label:

```text
Instance access tokens can access resources across all workspaces
subject to the permissions selected below.
```

Do not describe them as super-admin tokens.

### 14.3 Presets

Recommended presets:

**Read only**
- all supported `:read` scopes.

**Read + write**
- read/write content-management scopes,
- still excludes token management and instance administration.

**Custom**
- explicit checkboxes.

For initial deployment, default to **Read only**.

---

## 15. MCP contract

The backend must support two operating modes.

### 15.1 Workspace MCP mode

Existing pattern remains possible:

```text
PLANE_API_KEY=<workspace token>
PLANE_WORKSPACE_SLUG=tech
```

MCP may also omit the slug and discover it from:

```http
GET /api/v1/auth/context/
```

for a workspace-scoped token.

### 15.2 Instance MCP mode

Configuration:

```text
PLANE_API_KEY=<instance token>
PLANE_BASE_URL=https://plane.example.com
PLANE_WORKSPACE_SLUG=
```

Startup flow:

```text
MCP
 |
 +--> GET /api/v1/auth/context/
 |       scope_level=instance
 |
 +--> GET /api/v1/workspaces/
 |
 +--> expose workspace-aware tools
```

Every mutating MCP operation in instance mode must explicitly identify a workspace.

Do not implement ambiguous wildcard writes.

Example:

```text
create_work_item(
  workspace_slug="tech",
  project_id="...",
  ...
)
```

### 15.3 Daily digest flow

```text
Instance service token
        |
        v
GET /api/v1/workspaces/
        |
        +-------------------+
        |                   |
        v                   v
      Tech                 Game
        |                   |
 projects/work items   projects/work items
 cycles/modules        cycles/modules
        |                   |
        +---------+---------+
                  |
                  v
             Aggregator
                  |
                  v
           Daily / Weekly Digest
```

A recommended digest token is read-only.

---

## 16. Audit and observability

Every service-token request should be attributable to:

- token ID,
- token label,
- service bot user ID,
- scope level,
- workspace boundary if any,
- HTTP method/path,
- response status,
- source IP,
- user-agent,
- timestamp.

Never log:

- raw `X-Api-Key`,
- token hash,
- raw token secret.

### 16.1 Existing `APIActivityLog`

If reused, `token_identifier` must be a safe identifier such as token UUID or prefix, not the raw secret.

Any captured headers must redact:

```text
X-Api-Key
Authorization
Cookie
Set-Cookie
```

Bodies/responses should also be reviewed for sensitive data before enabling broad activity logging.

---

## 17. Rate limiting

Current `ApiKeyRateThrottle` uses the raw API key in its cache key.

Change it to use a safe stable token identifier when authentication succeeded:

```text
api_key:<APIToken.id>
```

Fallback to legacy behavior only when no authenticated token object is available, and avoid writing raw secrets to logs.

P0 may continue using the global configured API-key rate if changing per-token rate behavior is too broad.

If `allowed_rate_limit` is activated, validate it against safe server-side limits; do not trust arbitrary values from management API payloads.

---

## 18. Revocation and lifecycle

Revocation must be immediate.

On revoke:

```text
is_active = false
revoked_at = now()
revoked_by = request.user
```

Authentication denies the token immediately.

Do not hard-delete the record because audit history must remain attributable.

If the token's backing service bot has no active tokens, it may be deactivated.

Workspace deletion/soft deletion:

- bound workspace token becomes unusable.
- instance token remains valid for other active workspaces.

Instance token does not gain access to soft-deleted workspaces.

---

## 19. Security requirements

### Mandatory

- New WSAT/IAT secrets are hash-only at rest.
- Secret shown once.
- Cryptographically secure random generation.
- Explicit scopes.
- Workspace boundary enforcement.
- Instance boundary does not bypass operation scopes.
- Management endpoints cannot be called using service tokens.
- Workspace token creation requires workspace Admin role 20.
- Instance token creation requires instance admin session.
- Revocation immediate.
- Raw token never appears in logs.
- No hidden service bot membership fan-out.
- No PAT regression.

### Defense in depth

- CSRF protections remain on session management endpoints.
- Token management endpoints should not be cacheable.
- Audit token creation/revocation.
- Do not serialize hidden service users through member-list endpoints.
- Do not expose token hash.
- Constant-time comparison may be used after hash lookup where appropriate.
- Add indexes for `token_hash`, `scope_level`, `is_service`, and useful management filters.

---

## 20. API behavior examples

### Workspace token attempting another workspace

```http
GET /api/v1/workspaces/marketing/projects/
X-Api-Key: plane_wsat_...
```

Response:

```http
403 Forbidden
```

### Read-only instance token attempting write

```http
POST /api/v1/workspaces/tech/projects/
X-Api-Key: plane_iat_...
```

Token scopes:

```text
projects:read
```

Response:

```http
403 Forbidden
```

### Instance token reading a private project

If the token has:

```text
scope_level=instance
projects:read
```

the private project is readable because service-principal access is workspace-bound, not based on `ProjectMember`.

This behavior is intentional for central service automation.

---

## 21. Implementation work breakdown

### Phase A — models and migration

1. Add `SERVICE_TOKEN` bot type.
2. Extend `APIToken` fields.
3. Make legacy `token` nullable.
4. Add migration and indexes.
5. Add model validation/constraints.
6. Add secure token generator/hash helpers.
7. Add serializers that never expose secret except create response.

### Phase B — authentication context

1. Update `APIKeyAuthentication`.
2. Support hash lookup for WSAT/IAT.
3. Preserve legacy PAT lookup.
4. Attach `request.api_token`.
5. Attach `request.service_token`.
6. Update `last_used`.
7. Remove raw secret from throttle/cache/log identifiers.

### Phase C — authorization primitives

1. Add service-principal helpers.
2. Add central scope constants.
3. Add workspace-boundary helper.
4. Add method-to-scope helpers.
5. Update workspace permission classes.
6. Update project permission classes.
7. Preserve legacy branches for PATs.

### Phase D — queryset adaptation

Audit all P0 public API endpoints for `request.user` membership filtering.

At minimum:

- projects
- work items
- cycles
- modules
- states
- labels
- workspace members

Add principal-aware queryset filters.

This phase is mandatory before declaring backend support complete.

### Phase E — discovery API

1. Add `GET /api/v1/auth/context/`.
2. Add `GET /api/v1/workspaces/`.
3. Add serializers/docs/tests.

### Phase F — management API

1. Workspace service-token CRUD/revoke endpoints.
2. Instance service-token CRUD/revoke endpoints.
3. Correct admin permissions.
4. Audit create/revoke actions.

### Phase G — UI

1. Workspace Settings -> Access Tokens.
2. Instance Admin -> Access Tokens.
3. Create dialog.
4. One-time secret modal.
5. List/revoke/edit metadata.
6. Scope presets.

### Phase H — MCP compatibility

1. Detect principal using auth-context endpoint.
2. Support workspace token without requiring duplicated workspace configuration.
3. Support instance mode.
4. Workspace discovery.
5. Require explicit workspace for writes.
6. Validate daily/weekly digest use case.

---

## 22. Expected code touchpoints

Likely backend files:

```text
apps/api/plane/db/models/api.py
apps/api/plane/db/models/user.py
apps/api/plane/db/migrations/<new>.py

apps/api/plane/api/middleware/api_authentication.py
apps/api/plane/api/rate_limit.py

apps/api/plane/utils/permissions/workspace.py
apps/api/plane/utils/permissions/project.py
apps/api/plane/utils/permissions/base.py

apps/api/plane/api/views/base.py
apps/api/plane/api/views/project.py
apps/api/plane/api/views/work_item.py
apps/api/plane/api/views/cycle.py
apps/api/plane/api/views/module.py
apps/api/plane/api/views/state.py
apps/api/plane/api/views/label.py
apps/api/plane/api/views/member.py

apps/api/plane/api/urls/__init__.py
apps/api/plane/api/urls/<new auth/workspace routes>.py

apps/api/plane/app/views/<service token management>.py
apps/api/plane/app/urls/<service token management>.py

apps/api/plane/license/api/views/<instance service token management>.py
apps/api/plane/license/urls.py
```

Exact frontend paths should follow the existing Workspace Settings and Instance Admin routing/component conventions at implementation time.

Avoid duplicating permission modules if both `plane.app.permissions` and `plane.utils.permissions` aliases exist; identify the canonical import path before patching.

---

## 23. Migration and backward compatibility

### Existing PATs

Must continue authenticating without recreation.

Existing PAT API behavior remains:

- list personal tokens only,
- no service tokens mixed into personal token UI,
- permissions derived from user membership.

### Existing `is_service=True` rows

Do not silently reinterpret unknown legacy service rows as instance tokens.

Migration should classify safely:

```text
is_service=False
  -> scope_level=user

is_service=True and workspace_id IS NOT NULL
  -> scope_level=workspace only if the row is known/compatible
  otherwise mark for review or preserve legacy behavior

is_service=True and workspace_id IS NULL
  -> DO NOT automatically promote to instance access
```

No migration may grant broader permissions than a token had before migration.

---

## 24. Testing

### 24.1 Authentication tests

- valid legacy PAT works.
- invalid PAT rejected.
- valid WSAT hash works.
- valid IAT hash works.
- expired WSAT rejected.
- expired IAT rejected.
- revoked token rejected.
- inactive backing bot rejected.
- service token raw value cannot be recovered from DB/list API.

### 24.2 Workspace-boundary tests

Given WSAT bound to `tech`:

- read `tech` with correct read scope -> 200.
- read `marketing` -> 403.
- write `tech` without write scope -> 403.
- write `tech` with write scope -> allowed according to endpoint semantics.

### 24.3 Instance-boundary tests

Given read-only IAT:

- list workspaces -> all active workspaces.
- read private project in workspace A -> allowed.
- read private project in workspace B -> allowed.
- POST/PATCH/DELETE without write scope -> 403.
- instance configuration endpoint -> denied.
- service-token management endpoint -> denied.

### 24.4 Queryset regression tests

Critical tests must prove service tokens return data even though the backing bot has:

- no `WorkspaceMember`,
- no `ProjectMember`.

Test at least:

- project list,
- project detail,
- work item list,
- cycle list,
- module list,
- workspace-member list.

### 24.5 PAT regression tests

Existing contract tests in:

```text
apps/api/plane/tests/contract/app/test_api_token.py
```

must continue passing.

Add tests proving PAT data visibility has not broadened.

### 24.6 Management tests

- workspace member role 15 cannot create WSAT.
- workspace admin role 20 can create WSAT.
- workspace admin cannot create token for another workspace.
- non-instance-admin cannot create IAT.
- instance admin can create/revoke IAT.
- secret only exists in create response.
- GET/PATCH response never exposes secret/hash.

### 24.7 Security tests

- raw API key absent from logs.
- raw API key absent from throttle cache key where token identity is available.
- token hash never serialized.
- service bot excluded from member-list API/UI.
- no automatic workspace/project membership created.

---

## 25. Acceptance criteria

P0 is accepted only when all are true:

1. Workspace admin can create a read-only workspace token.
2. Instance admin can create a read-only instance token.
3. Raw service token is displayed exactly once.
4. Database contains only a hash for new WSAT/IAT secrets.
5. WSAT can access all permitted private projects/work items in its workspace without bot membership.
6. WSAT gets 403 for any other workspace.
7. IAT can discover all active workspaces.
8. IAT can read permitted private resources across all workspaces without bot membership.
9. IAT cannot mutate resources without the matching write scope.
10. IAT cannot modify instance configuration or manage tokens.
11. Existing PATs behave exactly as before.
12. Service tokens do not appear in personal PAT lists.
13. Service bots do not appear in ordinary workspace/project member lists.
14. Revoked tokens stop working immediately.
15. MCP can detect token mode using `/api/v1/auth/context/`.
16. MCP can enumerate workspaces using `/api/v1/workspaces/`.
17. A read-only IAT can execute an end-to-end multi-workspace daily/weekly digest data collection.
18. Tests prove querysets do not silently filter service-token data by backing bot membership.

---

## 26. Recommended first implementation slice

Ship a backend-first vertical slice before broad write support:

```text
Models + hashed secrets
        |
Authentication context
        |
Scopes + workspace boundary
        |
GET /api/v1/auth/context/
        |
GET /api/v1/workspaces/
        |
projects:read
work_items:read
cycles:read
modules:read
workspaces.members:read
        |
Workspace token UI
Instance token UI
        |
MCP read-only daily digest
```

This provides immediate value while limiting the initial security surface.

Write scopes should use the same architecture but can be enabled after read-path tests are complete.

---

## 27. Final architecture

```text
                    Human session
                         |
        +----------------+----------------+
        |                                 |
 Workspace Settings                Instance Admin
        |                                 |
 Create WSAT                         Create IAT
        |                                 |
        v                                 v
 hidden service bot                hidden service bot
        |                                 |
        +--------------+------------------+
                       |
                  APIToken
             scopes + boundary
              hashed secret
                       |
                       v
             APIKeyAuthentication
                       |
            request.api_token
            request.user = bot
                       |
                       v
          Service-principal authz
             /               \
    workspace boundary      operation scope
             \               /
              +-------------+
                    |
                    v
             Principal-aware
                querysets
                    |
                    v
                /api/v1
                    |
                    v
                   MCP
                    |
       +------------+-------------+
       |                          |
 Workspace agent            Instance agent
                                  |
                         all workspaces
                                  |
                         daily/weekly digest
```

The key invariant is:

> `request.user` identifies the technical actor; `request.api_token` determines service authorization.

This preserves compatibility with Plane's existing audit/data model while enabling stable workspace-level and instance-level AI agents without granting those agents a human user's identity or implicit super-admin privileges.
