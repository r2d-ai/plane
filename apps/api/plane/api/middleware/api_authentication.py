# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

from django.utils import timezone
from django.db.models import Q

from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from plane.api.service_tokens import SERVICE_SCOPE_LEVELS, hash_service_token
from plane.db.models import APIToken


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authentication with an API key."""

    www_authenticate_realm = "api"
    media_type = "application/json"
    auth_header_name = "X-Api-Key"

    def get_api_token(self, request):
        return request.headers.get(self.auth_header_name)

    def validate_api_token(self, raw_token):
        now = timezone.now()
        validity = Q(expired_at__gt=now) | Q(expired_at__isnull=True)

        api_token = (
            APIToken.objects.select_related("user", "workspace")
            .filter(
                validity,
                token_hash=hash_service_token(raw_token),
                is_active=True,
                revoked_at__isnull=True,
                user__is_active=True,
            )
            .first()
        )

        if api_token is None:
            api_token = (
                APIToken.objects.select_related("user", "workspace")
                .filter(
                    validity,
                    token=raw_token,
                    is_active=True,
                    revoked_at__isnull=True,
                    user__is_active=True,
                )
                .first()
            )

        if api_token is None:
            raise AuthenticationFailed("Given API token is not valid")

        if api_token.last_used is None or api_token.last_used < now - timedelta(minutes=1):
            APIToken.objects.filter(pk=api_token.pk).update(last_used=now)
            api_token.last_used = now

        return api_token

    def authenticate(self, request):
        raw_token = self.get_api_token(request=request)
        if not raw_token:
            return None

        api_token = self.validate_api_token(raw_token)
        request.api_token = api_token
        if api_token.is_service and api_token.scope_level in SERVICE_SCOPE_LEVELS:
            request.service_token = api_token

        return api_token.user, raw_token
