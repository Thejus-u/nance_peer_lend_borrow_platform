from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    entity_type = models.CharField(max_length=100, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    field_name = models.CharField(max_length=64, default="status", db_index=True)
    from_state = models.CharField(max_length=64, null=True, blank=True)
    to_state = models.CharField(max_length=64)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="audit_ent_lookup_idx"),
            models.Index(fields=["field_name", "occurred_at"], name="audit_field_time_idx"),
            models.Index(fields=["actor", "occurred_at"], name="audit_actor_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.entity_id}:{self.field_name}:{self.from_state}->{self.to_state}"
