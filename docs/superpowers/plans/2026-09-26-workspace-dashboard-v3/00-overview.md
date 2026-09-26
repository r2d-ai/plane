# Workspace Dashboard v3 — Rebuild & Cleanup Master Plan

> **Issue:** [RD-475](mention://issue/01a0de71-11a2-79b3-a62f-80487b402688) → [RD-476](mention://issue/01a0de71-cd05-739a-b73e-89d28c7d9ee9)
> **Spec:** `docs/workspace-dashboards-analytics-v2-spec.md` (file v2, content v3 — rewritten in-place at commit `9fd91c41a`, PR #75)
> **Author:** Anna (planning), implementation by Coda (backend) + Pixel (frontend)
> **Generated:** 2026-09-26

## Context (why)

Huy rewrote the spec in-place at `9fd91c41a`. The filename still ends in `v2` but the body is the **v3 spec: fixed Workspace Dashboard, dashboard builder retired**. The merged code in `master` (`5af14ad45`) still implements the *old* builder product — that is exactly why "dashboard đi quá xa so với yêu cầu" (Huy's original complaint). The code, migrations, tests and feature flag are all aimed at a builder UX that the spec no longer wants.

This folder is the **planning artifact** for RD-476 Phase 0. No code changes yet. Coda and Pixel will each pull one or more of the proposed child issues off this plan and implement them serially.

## The 5 deliverables

Each is a self-contained file in this folder. They are sequenced: 01 defines what to keep and what to delete; 02 uses that to scope Phase A–F work; 03 enumerates the files that must disappear; 04 covers perf; 05 proposes the concrete child-issue split for Alex.

| # | File | Purpose |
|---|------|---------|
| 01 | `01-audit-keep-extract-remove.md` | §16 KEEP / EXTRACT / REMOVE audit with file paths |
| 02 | `02-phase-task-breakdown.md` | Phase A–F task list, each task has a real path |
| 03 | `03-builder-cleanup-list.md` | Exhaustive list of builder-only files + i18n keys + flag plumbing to delete |
| 04 | `04-perf-plan.md` | Performance targets + measurement plan for the new dashboard |
| 05 | `05-child-issue-proposal.md` | Proposed 9 child issues (RD-477…RD-485), owner assignment, dependency order |

## Out of scope for Phase 0

- No source code deletion, no migration changes, no UI work yet.
- No decisions on whether to keep `Dashboard`, `DashboardWidget`, `DashboardProject`, `DashboardMemberAccess`, `DashboardFavorite` tables in the schema (decided in Phase E only, after migration safety analysis).
- No changes to Analytics V2 engine (`apps/api/plane/analytics/v2/*` is **KEEP**, see 01).

## Open assumptions (will be confirmed by Alex/Huy before Phase C)

1. Route stays at `/:workspaceSlug/dashboards` (plural) for migration ease per spec §4.1, and renders a single fixed dashboard — no list.
2. Per-user preference persistence uses localStorage keyed by `(workspaceId, userId)` per §15.1 — no new backend table for v1.
3. Analytics V2 `/analytics/v2/batch/` endpoint already exists at `apps/api/plane/app/urls/analytic.py:60`. New dashboard will reuse it (no new endpoint needed).
4. `WORKSPACE_DASHBOARDS` env flag (`apps/api/plane/settings/common.py:634`) stays fail-closed; Alex flips the default after RD-482 (cutover) lands.
5. **No extract of `apps/api/plane/utils/dashboard_analytics.py`** — Alex verified (2026-09-26 follow-up): only 2 consumers, both deleted in Phase E. `/analytics/v2/batch/` already implements generic batch with `MAX_BATCH_QUERIES=20`. Phase B is now frontend-only; backend contract + perf proof moved to RD-480.

## Done-when for RD-476

- [x] All 5 files present in this folder with concrete file paths
- [x] No code change committed by Anna (plan-only)
- [ ] Alex confirms child-issue split in `05-child-issue-proposal.md` and creates RD-477… child issues
- [ ] Coda picks up the first backend child issue
- [ ] Pixel picks up the first frontend child issue
