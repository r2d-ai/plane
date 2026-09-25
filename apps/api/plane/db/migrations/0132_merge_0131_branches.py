# Generated manually to merge the conflicting 0131 branches.
#
# 0131_normalize_gantt_display_defaults and 0131_service_access_tokens were
# authored in parallel and both depend on 0130_wiki_bootstrap_defaults, which
# left two leaf nodes in the migration graph and made makemigrations fail with
# "Conflicting migrations detected".
#
# This is a no-op merge: it only joins the two branches, so neither migration is
# renamed and databases that already recorded either one stay consistent.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0131_normalize_gantt_display_defaults"),
        ("db", "0131_service_access_tokens"),
    ]

    operations = []
