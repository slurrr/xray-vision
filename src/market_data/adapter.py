from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from market_data.config import RetryPolicy


@dataclass(frozen=True)
class StreamKey:
    source_id: str
    channel: str
    symbol: str | None = None


class AdapterState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class Adapter(Protocol):
    stream_key: StreamKey

    def start(self) -> None: ...

    def run(self) -> None: ...

    def stop(self) -> None: ...


@dataclass
class AdapterStatus:
    state: AdapterState = AdapterState.CREATED
    failure_count: int = 0
    last_error: Exception | None = None


@dataclass(frozen=True)
class RetrySchedule:
    min_delay_ms: int
    max_delay_ms: int
    max_attempts: int
    max_elapsed_ms: int | None = None

    def delays(self) -> tuple[int, ...]:
        delays: list[int] = []
        delay = self.min_delay_ms
        elapsed = 0
        for _ in range(self.max_attempts):
            if self.max_elapsed_ms is not None and (elapsed + delay) > self.max_elapsed_ms:
                break
            delays.append(delay)
            elapsed += delay
            delay = min(delay * 2, self.max_delay_ms)
        return tuple(delays)


class AdapterSupervisor:
    def __init__(self, stream_key: StreamKey, retry_policy: RetryPolicy) -> None:
        self.stream_key = stream_key
        self.retry_schedule = RetrySchedule(
            min_delay_ms=retry_policy.min_delay_ms,
            max_delay_ms=retry_policy.max_delay_ms,
            max_attempts=retry_policy.max_attempts,
            max_elapsed_ms=retry_policy.max_elapsed_ms,
        )
        self.status = AdapterStatus()

    def record_start(self) -> None:
        self.status.state = AdapterState.RUNNING

    def record_stop(self) -> None:
        self.status.state = AdapterState.STOPPED

    def record_failure(self, error: Exception) -> None:
        self.status.state = AdapterState.FAILED
        self.status.failure_count += 1
        self.status.last_error = error

    def next_retry_delay_ms(self) -> int | None:
        if self.status.failure_count <= 0:
            return None
        delays = self.retry_schedule.delays()
        index = self.status.failure_count - 1
        if index >= len(delays):
            return None
        return delays[index]
