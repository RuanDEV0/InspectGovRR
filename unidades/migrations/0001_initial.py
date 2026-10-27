"""Assume a tabela de unidades existente sem recriá-la."""

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('integrations', '0005_syncrun_creditorsnapshot'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Unit',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('name', models.CharField(max_length=255)),
                        ('code', models.CharField(max_length=20, unique=True, help_text='unit identifier code in the fiplan API')),
                        ('acronym', models.CharField(max_length=25, blank=True, null=True)),
                    ],
                    options={'db_table': 'integrations_unit'},
                ),
            ],
        ),
    ]
