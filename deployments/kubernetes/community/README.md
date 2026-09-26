# Helm Chart: Plane Community

Click on the below link to access the helm chart instructions.

[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/makeplane)](https://artifacthub.io/packages/helm/makeplane/plane-ce)

## Optional API environment variables

Workspace dashboards are toggled by `WORKSPACE_DASHBOARDS` on the API service. On (`1`) every workspace exposes the single fixed v3 Workspace Dashboard at `/:workspaceSlug/dashboards` (RD-475 / `docs/workspace-dashboards-analytics-v2-spec.md` §4 and §44.3); off leaves the route read-only. Only the literal value `1` enables the feature (`true` and any other value are treated as off); default `0` (v3 dashboard disabled). Documented in `apps/api/.env.example` and `apps/api/plane/settings/common.py`.
