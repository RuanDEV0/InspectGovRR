"""Aponta as relações para unidades.Unit, preservando tabela e chaves existentes."""

import django.db.models.deletion
from django.db import migrations, models


def move_content_type(apps, schema_editor, source, target):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    alias = schema_editor.connection.alias
    old = ContentType.objects.using(alias).filter(app_label=source, model='unit').first()
    new_exists = ContentType.objects.using(alias).filter(app_label=target, model='unit').exists()
    if old and not new_exists:
        old.app_label = target
        old.save(using=alias, update_fields=['app_label'])


def forward(apps, schema_editor):
    move_content_type(apps, schema_editor, 'integrations', 'unidades')


def backward(apps, schema_editor):
    move_content_type(apps, schema_editor, 'unidades', 'integrations')


class Migration(migrations.Migration):
    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('integrations', '0005_syncrun_creditorsnapshot'),
        ('unidades', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='daily',
                    name='unit',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_units', to='unidades.unit'),
                ),
                migrations.AlterField(
                    model_name='creditorsnapshot',
                    name='unit',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='creditor_snapshots', to='unidades.unit'),
                ),
                migrations.DeleteModel(name='Unit'),
            ],
        ),
        migrations.RunPython(forward, backward),
    ]
