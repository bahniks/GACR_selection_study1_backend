# Generated by Django 4.1.7 on 2023-10-17 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selection', '0012_participant_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='block',
            field=models.IntegerField(default=0),
        ),
    ]
