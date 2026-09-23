# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Rate limiting for public Wiki page publishing (WIKI-07b, spec §15).

The published page endpoint is anonymous and therefore a new public attack
surface. The throttle is keyed on the public token *and* the client identity so
one noisy reader cannot exhaust the budget for every reader of the page (and a
single token cannot be used to amplify traffic across the instance).
"""

from rest_framework.throttling import SimpleRateThrottle


class PagePublishRateThrottle(SimpleRateThrottle):
    scope = "page_publish"

    def get_cache_key(self, request, view):
        anchor = view.kwargs.get("anchor")
        if not anchor:
            return None
        return f"throttle_page_publish_{anchor}_{self.get_ident(request)}"
