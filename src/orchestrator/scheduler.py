from __future__ import annotations

from dataclasses import dataclass

from orchestrator.config import SchedulerConfig


@dataclass
class Scheduler:
    config: SchedulerConfig
    last_tick_ms: int | None = None

    def next_tick_ms(self, *, now_ms: int) -> int:
        if self.config.mode == "timer":
            return self._next_timer_tick(now_ms)
        return self._next_boundary_tick(now_ms)

    def _next_timer_tick(self, now_ms: int) -> int:
        interval_ms = self._require(self.config.timer_interval_ms)
        if self.last_tick_ms is None:
            self.last_tick_ms = now_ms
        else:
            self.last_tick_ms += interval_ms
        return self.last_tick_ms

    def _next_boundary_tick(self, now_ms: int) -> int:
        interval_ms = self._require(self.config.boundary_interval_ms)
        delay_ms = self.config.boundary_delay_ms or 0
        if self.last_tick_ms is not None:
            self.last_tick_ms += interval_ms
            return self.last_tick_ms

        base = now_ms - delay_ms
        if base < 0:
            base = 0
        next_boundary = ((base // interval_ms) + 1) * interval_ms
        self.last_tick_ms = next_boundary + delay_ms
        return self.last_tick_ms

    @staticmethod
    def _require(value: int | None) -> int:
        if value is None:
            raise ValueError("scheduler interval is required")
        return value
