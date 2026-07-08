from __future__ import annotations

from typing import Any

from apps.audit.models import AuditEvent


class AuditEventService:
    @classmethod
    def record_state_change(
        cls,
        *,
        entity_type: str,
        entity_id: int | str,
        field_name: str,
        from_state: str | None,
        to_state: str,
        actor_user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return AuditEvent.objects.create(
            entity_type=entity_type,
            entity_id=str(entity_id),
            field_name=field_name,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_user_id,
            metadata=metadata or {},
        )
