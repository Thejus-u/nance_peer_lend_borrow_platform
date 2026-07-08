from __future__ import annotations


def reconnect_strategy_payload() -> dict[str, object]:
    return {
        "enabled": True,
        "strategy": "exponential_backoff_with_jitter",
        "initial_delay_ms": 1000,
        "max_delay_ms": 30000,
        "max_attempts": 20,
        "jitter_ratio": 0.2,
    }


def next_reconnect_delay_ms(*, attempt: int, initial_delay_ms: int = 1000, max_delay_ms: int = 30000) -> int:
    if attempt <= 0:
        return initial_delay_ms
    delay = initial_delay_ms * (2 ** (attempt - 1))
    return min(delay, max_delay_ms)
