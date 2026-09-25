# Generated manually for native digest module foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0132_merge_0131_branches"),
    ]

    operations = [
        migrations.AddField(
            model_name="usernotificationpreference",
            name="leader_morning_digest",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="usernotificationpreference",
            name="leader_weekly_digest",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="usernotificationpreference",
            name="personal_daily_digest",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="DigestDelivery",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Last Modified At"),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("digest_type", models.CharField(max_length=32)),
                ("period_key", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sending", "Sending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("snapshot", models.JSONField(default=dict)),
                ("scheduled_at", models.DateTimeField(null=True)),
                ("sent_at", models.DateTimeField(null=True)),
                ("failed_at", models.DateTimeField(null=True)),
                ("error", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="digest_deliveries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "Digest Delivery",
                "verbose_name_plural": "Digest Deliveries",
                "db_table": "digest_deliveries",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="digestdelivery",
            constraint=models.UniqueConstraint(
                fields=("recipient", "digest_type", "period_key"),
                name="unique_digest_delivery_period_recipient",
            ),
        ),
    ]
