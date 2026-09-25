# Generated manually to normalize legacy Timeline display defaults.

from django.db import migrations


GANTT_LAYOUT = "gantt_chart"

# These properties were historically defaulted to True by Plane. Before the
# configurable Timeline columns feature, that was harmless because Timeline
# did not render them as independent columns. v1.4.2-2 started mapping those
# flags into Timeline columns, so legacy user properties suddenly appeared as
# "show everything".
GANTT_LEGACY_DEFAULT_KEYS = (
    "key",
    "issue_type",
    "state",
    "assignee",
    "priority",
    "modules",
    "labels",
    "start_date",
    "due_date",
)

GANTT_MINIMAL_DISPLAY_PROPERTIES = {
    "key": False,
    "issue_type": False,
    "state": False,
    "assignee": False,
    "priority": False,
    "estimate": False,
    "modules": False,
    "labels": False,
    "start_date": False,
    "due_date": False,
}


def _looks_like_legacy_gantt_defaults(display_properties):
    properties = display_properties or {}

    # Missing/None values are also computed as True by the web client, so they
    # belong to the legacy-default shape. Any explicit False means the user has
    # already customized a Timeline-relevant property and must be preserved.
    return all(properties.get(key) is not False for key in GANTT_LEGACY_DEFAULT_KEYS)


def _normalize_model(apps, model_name):
    Model = apps.get_model("db", model_name)

    rows = Model.objects.filter(
        display_filters__layout=GANTT_LAYOUT,
        deleted_at__isnull=True,
    ).only("id", "display_properties")

    for row in rows.iterator(chunk_size=500):
        if not _looks_like_legacy_gantt_defaults(row.display_properties):
            continue

        display_properties = dict(row.display_properties or {})
        display_properties.update(GANTT_MINIMAL_DISPLAY_PROPERTIES)
        Model.objects.filter(pk=row.pk).update(display_properties=display_properties)


def forwards(apps, schema_editor):
    # Normalize only entities whose currently persisted layout is Timeline.
    # Explicitly customized Timeline properties (any relevant False flag) are
    # left untouched.
    for model_name in (
        "ProjectUserProperty",
        "CycleUserProperties",
        "ModuleUserProperties",
        "IssueView",
    ):
        _normalize_model(apps, model_name)


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0130_wiki_bootstrap_defaults"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
