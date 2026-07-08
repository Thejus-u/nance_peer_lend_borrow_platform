from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.loans.reconnect import reconnect_strategy_payload


class LoanEventsConsumer(AsyncJsonWebsocketConsumer):
    heartbeat_interval_seconds = 30

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return

        self.user_group_name = f"loan_user_{user.id}"
        self.subscribed_loan_groups: set[str] = set()

        print("[WS CONNECT] Authenticated user id:", user.id)
        print("[WS CONNECT] Joined group:", self.user_group_name)
        print("[WS CONNECT] Channel name:", self.channel_name)

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connection_ack",
                "data": {
                    "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
                    "reconnect": reconnect_strategy_payload(),
                },
            }
        )

    async def disconnect(self, close_code: int) -> None:
        user_group_name = getattr(self, "user_group_name", None)
        if user_group_name:
            await self.channel_layer.group_discard(user_group_name, self.channel_name)

        for group_name in getattr(self, "subscribed_loan_groups", set()):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content: dict, **kwargs) -> None:
        action = content.get("action")

        if action == "subscribe_loan":
            loan_id = content.get("loan_id")
            if not loan_id:
                await self.send_json({"type": "error", "message": "loan_id is required."})
                return
            await self._subscribe_loan_group(loan_id=int(loan_id))
            await self.send_json({"type": "subscription_ack", "loan_id": int(loan_id)})
            return

        if action == "unsubscribe_loan":
            loan_id = content.get("loan_id")
            if not loan_id:
                await self.send_json({"type": "error", "message": "loan_id is required."})
                return
            await self._unsubscribe_loan_group(loan_id=int(loan_id))
            await self.send_json({"type": "unsubscription_ack", "loan_id": int(loan_id)})
            return

        if action == "ping":
            await self.send_json({"type": "pong"})
            return

        await self.send_json({"type": "error", "message": "Unsupported action."})

    async def loan_event(self, event: dict) -> None:
        print("[WS loan_event] Consumer received loan_event")
        print("[WS loan_event] Payload:", event)
        await self.send_json(
            {
                "type": "loan_event",
                "event": event.get("event"),
                "loan": event.get("loan"),
                "actor_user_id": event.get("actor_user_id"),
                "timestamp": event.get("timestamp"),
            }
        )

    async def notification_event(self, event: dict) -> None:
        print("[WS notification_event] Payload:", event)
        await self.send_json(
            {
                "type": "notification_event",
                "event": event.get("event"),
                "notification": event.get("notification"),
                "timestamp": event.get("timestamp"),
            }
        )

    async def _subscribe_loan_group(self, *, loan_id: int) -> None:
        group_name = f"loan_{loan_id}"
        if group_name in self.subscribed_loan_groups:
            return
        await self.channel_layer.group_add(group_name, self.channel_name)
        self.subscribed_loan_groups.add(group_name)

    async def _unsubscribe_loan_group(self, *, loan_id: int) -> None:
        group_name = f"loan_{loan_id}"
        if group_name not in self.subscribed_loan_groups:
            return
        await self.channel_layer.group_discard(group_name, self.channel_name)
        self.subscribed_loan_groups.remove(group_name)
