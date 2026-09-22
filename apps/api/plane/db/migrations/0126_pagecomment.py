# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Generated migration for PageComment model (WIKI-06b)

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0125_pageshare'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageComment',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('comment_html', models.TextField(blank=True, default='<p></p>')),
                ('comment_json', models.JSONField(blank=True, default=dict)),
                ('comment_stripped', models.TextField(blank=True, null=True)),
                ('edited_at', models.DateTimeField(blank=True, null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_comments', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_comments', to='db.page')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='parent_page_comment', to='db.pagecomment')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_comments', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Page Comment',
                'verbose_name_plural': 'Page Comments',
                'db_table': 'page_comments',
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='pagecomment',
            index=models.Index(fields=['page', 'created_at'], name='page_comment_page_created_idx'),
        ),
        migrations.AddIndex(
            model_name='pagecomment',
            index=models.Index(fields=['workspace', 'page'], name='page_comment_ws_page_idx'),
        ),
    ]
