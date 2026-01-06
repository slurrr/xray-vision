from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from orchestrator.config import RetryPolicy


@dataclass(frozen=True)
class RetrySchedule:
    min_delay_ms: int
    max_delay_ms: int
    max_attempts: int
    max_elapsed_ms: int | None = None

    @classmethod
    def from_policy(cls, policy: RetryPolicy) -> "RetrySchedule":
        return cls(
            min_delay_ms=policy.min_delay_ms,
            max_delay_ms=policy.max_delay_ms,
            max_attempts=policy.max_attempts,
            max_elapsed_ms=policy.max_elapsed_ms,
        )

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


@dataclass
class Retrier:
    schedule: RetrySchedule
    sleeper: Callable[[int], None]

    def __init__(self, schedule: RetrySchedule, sleeper: Callable[[int], None] | None = None) -> None:
        self.schedule = schedule
        self.sleeper = sleeper or (lambda _: None)

    def run(self, action: Callable[[], None]) -> bool:
        for delay_ms in self.schedule.delays():
            try:
                action()
                return True
            except Exception:
                self.sleeper(delay_ms)
        return False
