from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(db_index=True, default="general", max_length=50),
        ),
        migrations.AddField(
            model_name="notification",
            name="is_read",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "is_read"], name="notif_user_read_idx"),
        ),
    ]
