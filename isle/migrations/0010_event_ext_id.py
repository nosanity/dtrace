# Generated by Django 2.0.7 on 2018-07-12 19:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('isle', '0009_event_ile_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='ext_id',
            field=models.PositiveIntegerField(default=None, verbose_name='id в LABS'),
        ),
    ]
