from __future__ import annotations

from django.test import SimpleTestCase

from apps.loans.reconnect import next_reconnect_delay_ms, reconnect_strategy_payload


class ReconnectStrategyTestCase(SimpleTestCase):
    def test_reconnect_strategy_payload_shape(self) -> None:
        payload = reconnect_strategy_payload()

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["strategy"], "exponential_backoff_with_jitter")
        self.assertEqual(payload["initial_delay_ms"], 1000)
        self.assertEqual(payload["max_delay_ms"], 30000)

    def test_next_reconnect_delay_caps_at_max(self) -> None:
        self.assertEqual(next_reconnect_delay_ms(attempt=1), 1000)
        self.assertEqual(next_reconnect_delay_ms(attempt=2), 2000)
        self.assertEqual(next_reconnect_delay_ms(attempt=7), 30000)
