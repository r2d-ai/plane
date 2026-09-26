# Helm Chart: Plane Community

Click on the below link to access the helm chart instructions.

[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/makeplane)](https://artifacthub.io/packages/helm/makeplane/plane-ce)

## Optional API environment variables

Workspace dashboards are gated by `WORKSPACE_DASHBOARDS` on the API service (RD-452 / spec §44.3). Only the literal value `1` enables the feature; default `0` (fail-closed). Documented in `apps/api/.env.example` and `apps/api/plane/settings/common.py`.
