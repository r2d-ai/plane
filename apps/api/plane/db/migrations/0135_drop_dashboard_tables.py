# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Drop P0 workspace dashboard builder tables (RD-484 / spec §16.6).

Reverses ``0134_dashboards`` by deleting the five builder models. Rollback
recreates the tables from the historical migration state.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0134_dashboards"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DashboardFavorite",
        ),
        migrations.DeleteModel(
            name="DashboardMemberAccess",
        ),
        migrations.DeleteModel(
            name="DashboardWidget",
        ),
        migrations.DeleteModel(
            name="DashboardProject",
        ),
        migrations.DeleteModel(
            name="Dashboard",
        ),
    ]
