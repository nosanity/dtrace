# Generated by Django 2.0.7 on 2018-12-03 17:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('isle', '0038_auto_20181107_0320'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabsTeamResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField(default='')),
                ('approved', models.BooleanField(default=False)),
                ('result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='isle.LabsEventResult')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='isle.Team')),
            ],
        ),
        migrations.AddField(
            model_name='eventteammaterial',
            name='result_v2',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='isle.LabsTeamResult'),
        ),
    ]
