from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    min_delay_ms: int
    max_delay_ms: int
    max_attempts: int
    max_elapsed_ms: int | None = None


@dataclass(frozen=True)
class BufferRetentionConfig:
    max_records: int
    max_age_ms: int | None = None


@dataclass(frozen=True)
class OutputPublishConfig:
    max_pending: int
    max_block_ms: int | None = None


@dataclass(frozen=True)
class SchedulerConfig:
    mode: str
    timer_interval_ms: int | None = None
    boundary_interval_ms: int | None = None
    boundary_delay_ms: int | None = None


@dataclass(frozen=True)
class EngineConfig:
    engine_mode: str
    hysteresis_state_path: str | None = None


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    symbols: Sequence[str]


@dataclass(frozen=True)
class OrchestratorConfig:
    sources: Sequence[SourceConfig]
    scheduler: SchedulerConfig
    engine: EngineConfig
    ingestion_retry: RetryPolicy
    buffer_retry: RetryPolicy
    engine_retry: RetryPolicy
    publish_retry: RetryPolicy
    buffer_retention: BufferRetentionConfig
    output_publish: OutputPublishConfig


def validate_config(config: OrchestratorConfig) -> None:
    if not config.sources:
        raise ValueError("orchestrator config must include at least one source")

    source_ids: set[str] = set()
    for source in config.sources:
        if not source.source_id:
            raise ValueError("source_id must be set for each source")
        if source.source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        source_ids.add(source.source_id)
        if not source.symbols:
            raise ValueError(f"symbols must be set for source_id={source.source_id}")

    _validate_scheduler(config.scheduler)
    _validate_engine(config.engine)

    _validate_retry(config.ingestion_retry, "ingestion_retry")
    _validate_retry(config.buffer_retry, "buffer_retry")
    _validate_retry(config.engine_retry, "engine_retry")
    _validate_retry(config.publish_retry, "publish_retry")

    _require_positive(config.buffer_retention.max_records, "buffer_retention.max_records")
    if config.buffer_retention.max_age_ms is not None:
        _require_positive(config.buffer_retention.max_age_ms, "buffer_retention.max_age_ms")

    _require_positive(config.output_publish.max_pending, "output_publish.max_pending")
    if config.output_publish.max_block_ms is not None:
        _require_positive(config.output_publish.max_block_ms, "output_publish.max_block_ms")


def _validate_scheduler(scheduler: SchedulerConfig) -> None:
    if scheduler.mode not in {"timer", "boundary"}:
        raise ValueError("scheduler.mode must be 'timer' or 'boundary'")
    if scheduler.mode == "timer":
        _require_positive(scheduler.timer_interval_ms, "scheduler.timer_interval_ms")
    if scheduler.mode == "boundary":
        _require_positive(scheduler.boundary_interval_ms, "scheduler.boundary_interval_ms")
        _require_non_negative(scheduler.boundary_delay_ms, "scheduler.boundary_delay_ms")


def _validate_engine(engine: EngineConfig) -> None:
    if engine.engine_mode not in {"truth", "hysteresis"}:
        raise ValueError("engine.engine_mode must be 'truth' or 'hysteresis'")
    if engine.engine_mode == "hysteresis" and not engine.hysteresis_state_path:
        raise ValueError("engine.hysteresis_state_path is required for hysteresis mode")


def _validate_retry(retry: RetryPolicy, field_name: str) -> None:
    _require_positive(retry.min_delay_ms, f"{field_name}.min_delay_ms")
    _require_positive(retry.max_delay_ms, f"{field_name}.max_delay_ms")
    if retry.max_delay_ms < retry.min_delay_ms:
        raise ValueError(f"{field_name}.max_delay_ms must be >= {field_name}.min_delay_ms")
    if retry.max_attempts <= 0:
        raise ValueError(f"{field_name}.max_attempts must be > 0")
    if retry.max_elapsed_ms is not None:
        _require_positive(retry.max_elapsed_ms, f"{field_name}.max_elapsed_ms")


def _require_positive(value: int | None, field_name: str) -> None:
    if value is None or value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _require_non_negative(value: int | None, field_name: str) -> None:
    if value is None or value < 0:
        raise ValueError(f"{field_name} must be >= 0")
