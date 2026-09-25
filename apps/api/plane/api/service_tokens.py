# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Service access-token primitives shared by the public API and management API."""

import hashlib
import secrets
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import SAFE_METHODS

from plane.db.models import APIToken, User


SCOPE_LEVEL_WORKSPACE = "workspace"
SCOPE_LEVEL_INSTANCE = "instance"
SERVICE_SCOPE_LEVELS = {SCOPE_LEVEL_WORKSPACE, SCOPE_LEVEL_INSTANCE}

VALID_SERVICE_SCOPES = frozenset(
    {
        "workspaces:read",
        "projects:read",
        "projects:write",
        "work_items:read",
        "work_items:write",
        "cycles:read",
        "cycles:write",
        "modules:read",
        "modules:write",
        "states:read",
        "states:write",
        "labels:read",
        "labels:write",
        "workspaces.members:read",
        "wiki.pages:read",
        "wiki.pages:write",
    }
)

READ_ONLY_SERVICE_SCOPES = tuple(
    sorted(scope for scope in VALID_SERVICE_SCOPES if scope.endswith(":read"))
)


def hash_service_token(service_token_value):
    # codeql[py/weak-sensitive-data-hashing] Service-token fingerprint for lookup, not a password hash
    return hashlib.sha256(service_token_value.encode("utf-8")).hexdigest()


def generate_service_token(scope_level):
    if scope_level == SCOPE_LEVEL_WORKSPACE:
        prefix = "plane_wsat_"
    elif scope_level == SCOPE_LEVEL_INSTANCE:
        prefix = "plane_iat_"
    else:
        raise ValueError("Unsupported service token scope level")

    raw_token = prefix + secrets.token_urlsafe(32)
    return raw_token, raw_token[:24], hash_service_token(raw_token)


def normalize_service_scopes(scopes):
    if not isinstance(scopes, (list, tuple, set)):
        raise ValueError("scopes must be a list")

    normalized = sorted({str(scope).strip() for scope in scopes if str(scope).strip()})
    if not normalized:
        raise ValueError("At least one scope is required")

    invalid = sorted(set(normalized) - VALID_SERVICE_SCOPES)
    if invalid:
        raise ValueError("Unsupported scopes: " + ", ".join(invalid))
    return normalized


def get_api_token(request):
    return getattr(request, "api_token", None)


def is_service_principal(request):
    api_token = get_api_token(request)
    return bool(
        api_token
        and api_token.is_service
        and api_token.scope_level in SERVICE_SCOPE_LEVELS
        and api_token.revoked_at is None
        and api_token.is_active
    )


def service_token_allows_workspace(api_token, workspace_slug):
    if not workspace_slug:
        return False
    if api_token.scope_level == SCOPE_LEVEL_INSTANCE:
        return True
    if api_token.scope_level == SCOPE_LEVEL_WORKSPACE:
        return bool(api_token.workspace_id and api_token.workspace and api_token.workspace.slug == workspace_slug)
    return False


def required_service_scope(resource, method):
    if not resource:
        return None
    action = "read" if method in SAFE_METHODS else "write"
    return f"{resource}:{action}"


def authorize_service_request(request, workspace_slug, resource):
    if not is_service_principal(request):
        return False
    api_token = get_api_token(request)
    if not service_token_allows_workspace(api_token, workspace_slug):
        return False
    required_scope = required_service_scope(resource, request.method)
    if not required_scope:
        return False
    return required_scope in set(api_token.scopes or [])


@transaction.atomic
def create_service_access_token(
    *,
    label,
    description,
    created_by,
    scope_level,
    scopes,
    workspace=None,
    expired_at=None,
):
    normalized_scopes = normalize_service_scopes(scopes)

    if scope_level == SCOPE_LEVEL_WORKSPACE and workspace is None:
        raise ValueError("Workspace access tokens require a workspace")
    if scope_level == SCOPE_LEVEL_INSTANCE and workspace is not None:
        raise ValueError("Instance access tokens cannot be bound to a workspace")
    if scope_level not in SERVICE_SCOPE_LEVELS:
        raise ValueError("Unsupported service token scope level")

    raw_token, token_prefix, token_hash = generate_service_token(scope_level)
    identity = uuid4().hex
    bot_user = User.objects.create(
        email=f"service-token-{identity}@plane.invalid",
        username=f"service-token-{identity}",
        display_name=label,
        is_bot=True,
        bot_type="SERVICE_TOKEN",
        is_active=True,
    )

    api_token = APIToken.objects.create(
        label=label,
        description=description,
        user=bot_user,
        user_type=1,
        workspace=workspace,
        expired_at=expired_at,
        is_service=True,
        scope_level=scope_level,
        scopes=normalized_scopes,
        token=None,
        token_prefix=token_prefix,
        token_hash=token_hash,
        created_by=created_by,
    )
    return api_token, raw_token


@transaction.atomic
def revoke_service_access_token(api_token, revoked_by):
    if not api_token.is_service or api_token.scope_level not in SERVICE_SCOPE_LEVELS:
        raise ValueError("Token is not a service access token")

    api_token.is_active = False
    api_token.revoked_at = timezone.now()
    api_token.revoked_by = revoked_by
    api_token.save(update_fields=["is_active", "revoked_at", "revoked_by", "updated_at"])

    has_other_active_tokens = APIToken.objects.filter(
        user=api_token.user,
        is_service=True,
        is_active=True,
        revoked_at__isnull=True,
    ).exclude(pk=api_token.pk).exists()
    if not has_other_active_tokens and api_token.user.is_bot:
        api_token.user.is_active = False
        api_token.user.save(update_fields=["is_active"])
