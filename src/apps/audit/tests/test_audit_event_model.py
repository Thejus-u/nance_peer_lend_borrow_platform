from __future__ import annotations

from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditEvent


class AuditEventModelTestCase(TestCase):
    def test_create_audit_event(self) -> None:
        actor = User.objects.create_user(
            mobile_number="+14156660001",
            name="Audit Actor",
            password="StrongPass123!",
        )

        event = AuditEvent.objects.create(
            entity_type="loan",
            entity_id="101",
            field_name="status",
            from_state="pending_review",
            to_state="approved",
            actor=actor,
            metadata={"action": "loan.accept"},
        )

        self.assertEqual(event.entity_type, "loan")
        self.assertEqual(event.entity_id, "101")
        self.assertEqual(event.from_state, "pending_review")
        self.assertEqual(event.to_state, "approved")
        self.assertEqual(event.actor_id, actor.id)
