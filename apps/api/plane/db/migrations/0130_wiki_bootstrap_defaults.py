# Generated manually for WikiCE bootstrap normalization.

from django.conf import settings
from django.db import migrations, transaction


WELCOME_EXTERNAL_SOURCE = "wiki_bootstrap"
WELCOME_EXTERNAL_ID = "welcome-v1"
GENERAL_COLLECTION_NAME = "General"
GENERAL_COLLECTION_DESCRIPTION = "Your workspace's general collection."


def _welcome_title(workspace):
    if workspace.slug == settings.COMPANY_WIKI_WORKSPACE_SLUG:
        return "Welcome to Company's Wiki"
    return f"Welcome to {workspace.name} Wiki"


def bootstrap_workspace(apps, workspace_id):
    Workspace = apps.get_model("db", "Workspace")
    Page = apps.get_model("db", "Page")
    PageCollection = apps.get_model("db", "PageCollection")
    PageCollectionPage = apps.get_model("db", "PageCollectionPage")

    with transaction.atomic():
        workspace = Workspace.objects.select_for_update().get(pk=workspace_id)
        owner_id = workspace.owner_id

        collections = PageCollection.objects.filter(workspace_id=workspace.id, deleted_at__isnull=True)
        collection = collections.filter(is_default=True).order_by("created_at", "id").first()
        created_general = False

        if collection is None:
            collection = collections.filter(name__iexact=GENERAL_COLLECTION_NAME).order_by("created_at", "id").first()
            if collection is not None:
                PageCollection.objects.filter(pk=collection.pk).update(
                    is_default=True,
                    updated_by_id=owner_id,
                )
                collection.is_default = True
            else:
                collection = PageCollection.objects.create(
                    workspace_id=workspace.id,
                    name=GENERAL_COLLECTION_NAME,
                    description=GENERAL_COLLECTION_DESCRIPTION,
                    access=0,
                    sort_order=0,
                    is_default=True,
                    created_by_id=owner_id,
                    updated_by_id=owner_id,
                )
                created_general = True

        welcome = (
            Page.objects.filter(
                workspace_id=workspace.id,
                is_global=True,
                deleted_at__isnull=True,
                external_source=WELCOME_EXTERNAL_SOURCE,
                external_id=WELCOME_EXTERNAL_ID,
            )
            .order_by("created_at", "id")
            .first()
        )

        if welcome is None:
            assigned_page_ids = PageCollectionPage.objects.filter(
                workspace_id=workspace.id,
                deleted_at__isnull=True,
            ).values("page_id")
            legacy = list(
                Page.objects.filter(
                    workspace_id=workspace.id,
                    is_global=True,
                    access=0,
                    parent__isnull=True,
                    archived_at__isnull=True,
                    deleted_at__isnull=True,
                    name__iregex=r"^Welcome to .+Wiki$",
                )
                .exclude(id__in=assigned_page_ids)
                .order_by("created_at", "id")[:2]
            )
            if len(legacy) == 1:
                welcome = legacy[0]
                Page.objects.filter(pk=welcome.pk).update(
                    external_source=WELCOME_EXTERNAL_SOURCE,
                    external_id=WELCOME_EXTERNAL_ID,
                    updated_by_id=owner_id,
                )
                welcome.external_source = WELCOME_EXTERNAL_SOURCE
                welcome.external_id = WELCOME_EXTERNAL_ID
            else:
                welcome = Page.objects.create(
                    workspace_id=workspace.id,
                    owned_by_id=owner_id,
                    name=_welcome_title(workspace),
                    access=0,
                    is_global=True,
                    parent_id=None,
                    description_json={},
                    description_html="<p></p>",
                    description_binary=None,
                    external_source=WELCOME_EXTERNAL_SOURCE,
                    external_id=WELCOME_EXTERNAL_ID,
                    created_by_id=owner_id,
                    updated_by_id=owner_id,
                )

        existing_membership = PageCollectionPage.objects.filter(
            page_id=welcome.id,
            deleted_at__isnull=True,
        ).first()
        if existing_membership is None:
            PageCollectionPage.objects.create(
                collection_id=collection.id,
                page_id=welcome.id,
                workspace_id=workspace.id,
                sort_order=welcome.sort_order,
                created_by_id=owner_id,
                updated_by_id=owner_id,
            )

        if created_general:
            assigned_page_ids = PageCollectionPage.objects.filter(
                workspace_id=workspace.id,
                deleted_at__isnull=True,
            ).values("page_id")
            roots = (
                Page.objects.filter(
                    workspace_id=workspace.id,
                    is_global=True,
                    access=0,
                    parent__isnull=True,
                    archived_at__isnull=True,
                    deleted_at__isnull=True,
                )
                .exclude(id__in=assigned_page_ids)
                .order_by("sort_order", "created_at", "id")
            )
            PageCollectionPage.objects.bulk_create(
                [
                    PageCollectionPage(
                        collection_id=collection.id,
                        page_id=page.id,
                        workspace_id=workspace.id,
                        sort_order=page.sort_order,
                        created_by_id=owner_id,
                        updated_by_id=owner_id,
                    )
                    for page in roots
                ],
                batch_size=200,
            )


def forwards(apps, schema_editor):
    Workspace = apps.get_model("db", "Workspace")
    workspace_ids = (
        Workspace.objects.filter(deleted_at__isnull=True)
        .order_by("id")
        .values_list("id", flat=True)
        .iterator(chunk_size=200)
    )
    for workspace_id in workspace_ids:
        bootstrap_workspace(apps, workspace_id)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("db", "0129_wikievent"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
