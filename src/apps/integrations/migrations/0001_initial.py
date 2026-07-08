from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GmailAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254, unique=True)),
                ("google_user_id", models.CharField(max_length=255, unique=True)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("connected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integration_gmail_accounts", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-connected_at"],
                "indexes": [
                    models.Index(fields=["user", "connected_at"], name="int_gmail_user_conn_idx"),
                    models.Index(fields=["email"], name="int_gmail_email_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DiscoveredEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gmail_message_id", models.CharField(max_length=255)),
                ("subject", models.CharField(blank=True, max_length=500)),
                ("sender", models.CharField(blank=True, max_length=320)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("processed", models.BooleanField(default=False)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "gmail_account",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="discovered_emails", to="integrations.gmailaccount"),
                ),
            ],
            options={
                "ordering": ["-received_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["gmail_account", "received_at"], name="int_disc_email_recv_idx"),
                    models.Index(fields=["processed"], name="int_disc_email_proc_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("gmail_account", "gmail_message_id"), name="int_discovered_email_unique_per_account"),
                ],
            },
        ),
    ]