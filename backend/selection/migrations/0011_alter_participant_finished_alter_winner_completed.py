# Generated by Django 4.1.7 on 2023-04-28 20:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selection', '0010_alter_group_condition_alter_winner_completed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participant',
            name='finished',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='winner',
            name='completed',
            field=models.IntegerField(default=0),
        ),
    ]
