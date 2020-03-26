# Generated by Django 2.0.7 on 2019-05-08 09:30

from django.db import migrations, models


def set_assistant_flag(apps, schema_editor):
    """
    проставление флажков для существующих файлов и команд о том, что они были созданы ассистентами
    """
    EventMaterial = apps.get_model('isle', 'EventMaterial')
    EventTeamMaterial = apps.get_model('isle', 'EventTeamMaterial')
    Team = apps.get_model('isle', 'Team')
    User = apps.get_model('isle', 'User')
    assistants = list(User.objects.filter(unti_id__isnull=False, is_assistant=True).values_list('unti_id', flat=True))
    EventMaterial.objects.filter(initiator__in=assistants).update(loaded_by_assistant=True)
    EventTeamMaterial.objects.filter(initiator__in=assistants).update(loaded_by_assistant=True)
    assistants = list(User.objects.filter(is_assistant=True).values_list('id', flat=True))
    Team.objects.filter(creator_id__in=assistants).update(created_by_assistant=True)


class Migration(migrations.Migration):

    dependencies = [
        ('isle', '0044_auto_20190328_0215'),
    ]

    operations = [
        migrations.CreateModel(
            name='CasbinData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.TextField()),
                ('policy', models.TextField()),
            ],
        ),
        migrations.AddField(
            model_name='eventmaterial',
            name='loaded_by_assistant',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='eventteammaterial',
            name='loaded_by_assistant',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='team',
            name='created_by_assistant',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(set_assistant_flag, reverse_code=migrations.RunPython.noop)
    ]
