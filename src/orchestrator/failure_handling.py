from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from orchestrator.lifecycle import Lifecycle
from orchestrator.retry import Retrier


class IngestionFailure(RuntimeError):
    """Raised when ingestion retries are exhausted."""


class BufferAppendFailure(RuntimeError):
    """Raised when buffer append retries are exhausted."""


class EngineRunFailure(RuntimeError):
    """Raised when engine run retries are exhausted."""


class PublishFailure(RuntimeError):
    """Raised when publish retries are exhausted."""


@dataclass
class BackpressureState:
    ingestion_paused: bool = False
    scheduling_paused: bool = False


@dataclass
class FailureHandler:
    lifecycle: Lifecycle
    backpressure: BackpressureState

    def handle_ingestion(self, action: Callable[[], None], retrier: Retrier) -> None:
        if not retrier.run(action):
            raise IngestionFailure("ingestion retries exhausted")

    def handle_buffer_append(self, action: Callable[[], None], retrier: Retrier) -> None:
        if retrier.run(action):
            return
        self.lifecycle.degrade()
        self.backpressure.ingestion_paused = True
        raise BufferAppendFailure("buffer append retries exhausted")

    def handle_engine_run(self, action: Callable[[], None], retrier: Retrier) -> None:
        if retrier.run(action):
            return
        raise EngineRunFailure("engine run retries exhausted")

    def handle_publish(self, action: Callable[[], None], retrier: Retrier) -> None:
        if retrier.run(action):
            return
        self.backpressure.scheduling_paused = True
        raise PublishFailure("publish retries exhausted")
