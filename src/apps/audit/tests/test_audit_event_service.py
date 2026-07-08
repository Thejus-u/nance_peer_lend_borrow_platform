from __future__ import annotations

from django.test import TestCase

from apps.accounts.models import User
from apps.audit.services import AuditEventService


class AuditEventServiceTestCase(TestCase):
    def test_record_state_change(self) -> None:
        actor = User.objects.create_user(
            mobile_number="+14156660002",
            name="Audit Service Actor",
            password="StrongPass123!",
        )

        event = AuditEventService.record_state_change(
            entity_type="notification",
            entity_id=55,
            field_name="status",
            from_state="pending",
            to_state="sent",
            actor_user_id=actor.id,
            metadata={"action": "notification.mark_sent"},
        )

        self.assertEqual(event.entity_type, "notification")
        self.assertEqual(event.entity_id, "55")
        self.assertEqual(event.from_state, "pending")
        self.assertEqual(event.to_state, "sent")
        self.assertEqual(event.actor_id, actor.id)
