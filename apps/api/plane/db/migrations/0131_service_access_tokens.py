# Generated manually for service access tokens.

import plane.db.models.api
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0130_wiki_bootstrap_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apitoken",
            name="token",
            field=models.CharField(
                blank=True,
                db_index=True,
                default=plane.db.models.api.generate_token,
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="scope_level",
            field=models.CharField(
                choices=[("user", "User"), ("workspace", "Workspace"), ("instance", "Instance")],
                db_index=True,
                default="user",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="scopes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="token_prefix",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="token_hash",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="apitoken",
            name="revoked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="revoked_api_tokens",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
