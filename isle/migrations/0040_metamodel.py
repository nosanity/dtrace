# Generated by Django 2.0.7 on 2019-01-24 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('isle', '0039_auto_20181204_0302'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.CharField(max_length=255, unique=True)),
                ('guid', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=500)),
            ],
        ),
    ]