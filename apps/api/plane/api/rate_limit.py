# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ApiKeyRateThrottle(SimpleRateThrottle):
    scope = "api_key"
    rate = settings.API_KEY_RATE_LIMIT

    def get_cache_key(self, request, view):
        api_key = request.headers.get("X-Api-Key")
        if not api_key:
            return None

        api_token = getattr(request, "api_token", None)
        identifier = (
            str(api_token.id)
            if api_token is not None
            else hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        )
        return f"{self.scope}:{identifier}"

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)

        if allowed:
            now = self.timer()
            history = self.cache.get(self.key, [])
            while history and history[-1] <= now - self.duration:
                history.pop()

            available = self.num_requests - len(history)
            request.META["X-RateLimit-Remaining"] = max(0, available)
            request.META["X-RateLimit-Reset"] = int(now + self.duration)

        return allowed
