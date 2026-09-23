# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.urls import path

# Module imports
from plane.space.views import PublishedPageEndpoint

urlpatterns = [
    path(
        "anchor/<str:anchor>/page/",
        PublishedPageEndpoint.as_view(),
        name="published-page",
    ),
]
