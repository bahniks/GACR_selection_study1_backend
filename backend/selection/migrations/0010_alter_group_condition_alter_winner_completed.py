# Generated by Django 4.1.7 on 2023-04-28 20:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selection', '0009_winner_charity_winner_completed_winner_reward_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='condition',
            field=models.CharField(default='', max_length=12),
        ),
        migrations.AlterField(
            model_name='winner',
            name='completed',
            field=models.IntegerField(default=0, null=True),
        ),
    ]
