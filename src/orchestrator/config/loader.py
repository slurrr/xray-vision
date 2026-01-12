from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from importlib import resources

from orchestrator.config.schema import (
    BufferRetentionConfig,
    EngineConfig,
    OrchestratorConfig,
    OutputPublishConfig,
    RetryPolicy,
    SchedulerConfig,
    SourceConfig,
    validate_config,
)

_ROOT_KEYS = {
    "sources",
    "scheduler",
    "engine",
    "ingestion_retry",
    "buffer_retry",
    "engine_retry",
    "publish_retry",
    "buffer_retention",
    "output_publish",
}
_SOURCE_KEYS = {"source_id", "symbols"}
_SCHEDULER_KEYS = {"mode", "timer_interval_ms", "boundary_interval_ms", "boundary_delay_ms"}
_ENGINE_KEYS = {"engine_mode", "hysteresis_state_path"}
_RETRY_KEYS = {"min_delay_ms", "max_delay_ms", "max_attempts", "max_elapsed_ms"}
_BUFFER_RETENTION_KEYS = {"max_records", "max_age_ms"}
_OUTPUT_PUBLISH_KEYS = {"max_pending", "max_block_ms"}


def load_default_config() -> OrchestratorConfig:
    payload = _load_default_payload()
    config = _parse_config(payload)
    validate_config(config)
    return config


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("orchestrator.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("orchestrator default config must be a mapping")
    return data


def _parse_config(payload: Mapping[str, object]) -> OrchestratorConfig:
    _reject_unknown(payload, _ROOT_KEYS, "orchestrator config")
    sources = _parse_sources(payload.get("sources"))
    scheduler = _parse_scheduler(payload.get("scheduler"))
    engine = _parse_engine(payload.get("engine"))
    ingestion_retry = _parse_retry(payload.get("ingestion_retry"), "ingestion_retry")
    buffer_retry = _parse_retry(payload.get("buffer_retry"), "buffer_retry")
    engine_retry = _parse_retry(payload.get("engine_retry"), "engine_retry")
    publish_retry = _parse_retry(payload.get("publish_retry"), "publish_retry")
    buffer_retention = _parse_buffer_retention(payload.get("buffer_retention"))
    output_publish = _parse_output_publish(payload.get("output_publish"))
    return OrchestratorConfig(
        sources=sources,
        scheduler=scheduler,
        engine=engine,
        ingestion_retry=ingestion_retry,
        buffer_retry=buffer_retry,
        engine_retry=engine_retry,
        publish_retry=publish_retry,
        buffer_retention=buffer_retention,
        output_publish=output_publish,
    )


def _parse_sources(data: object) -> tuple[SourceConfig, ...]:
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise ValueError("sources must be a list")
    sources: list[SourceConfig] = []
    for item in data:
        if not isinstance(item, Mapping):
            raise ValueError("source entries must be mappings")
        _reject_unknown(item, _SOURCE_KEYS, "source")
        source_id = item.get("source_id")
        symbols = item.get("symbols")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be set for each source")
        if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes)):
            raise ValueError(f"symbols must be set for source_id={source_id}")
        sources.append(SourceConfig(source_id=source_id, symbols=[str(val) for val in symbols]))
    return tuple(sources)


def _parse_scheduler(data: object) -> SchedulerConfig:
    if not isinstance(data, Mapping):
        raise ValueError("scheduler must be a mapping")
    _reject_unknown(data, _SCHEDULER_KEYS, "scheduler")
    mode = data.get("mode")
    timer_interval_ms = data.get("timer_interval_ms")
    boundary_interval_ms = data.get("boundary_interval_ms")
    boundary_delay_ms = data.get("boundary_delay_ms")
    if not isinstance(mode, str) or not mode:
        raise ValueError("scheduler.mode must be set")
    if timer_interval_ms is not None and not isinstance(timer_interval_ms, int):
        raise ValueError("scheduler.timer_interval_ms must be an int")
    if boundary_interval_ms is not None and not isinstance(boundary_interval_ms, int):
        raise ValueError("scheduler.boundary_interval_ms must be an int")
    if boundary_delay_ms is not None and not isinstance(boundary_delay_ms, int):
        raise ValueError("scheduler.boundary_delay_ms must be an int")
    return SchedulerConfig(
        mode=mode,
        timer_interval_ms=timer_interval_ms,
        boundary_interval_ms=boundary_interval_ms,
        boundary_delay_ms=boundary_delay_ms,
    )


def _parse_engine(data: object) -> EngineConfig:
    if not isinstance(data, Mapping):
        raise ValueError("engine must be a mapping")
    _reject_unknown(data, _ENGINE_KEYS, "engine")
    engine_mode = data.get("engine_mode")
    hysteresis_state_path = data.get("hysteresis_state_path")
    if not isinstance(engine_mode, str) or not engine_mode:
        raise ValueError("engine.engine_mode must be set")
    if hysteresis_state_path is not None and not isinstance(hysteresis_state_path, str):
        raise ValueError("engine.hysteresis_state_path must be a string")
    return EngineConfig(
        engine_mode=engine_mode,
        hysteresis_state_path=hysteresis_state_path,
    )


def _parse_retry(data: object, label: str) -> RetryPolicy:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    _reject_unknown(data, _RETRY_KEYS, label)
    min_delay_ms = data.get("min_delay_ms")
    max_delay_ms = data.get("max_delay_ms")
    max_attempts = data.get("max_attempts")
    max_elapsed_ms = data.get("max_elapsed_ms")
    if not isinstance(min_delay_ms, int):
        raise ValueError(f"{label}.min_delay_ms must be an int")
    if not isinstance(max_delay_ms, int):
        raise ValueError(f"{label}.max_delay_ms must be an int")
    if not isinstance(max_attempts, int):
        raise ValueError(f"{label}.max_attempts must be an int")
    if max_elapsed_ms is not None and not isinstance(max_elapsed_ms, int):
        raise ValueError(f"{label}.max_elapsed_ms must be an int")
    return RetryPolicy(
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        max_attempts=max_attempts,
        max_elapsed_ms=max_elapsed_ms,
    )


def _parse_buffer_retention(data: object) -> BufferRetentionConfig:
    if not isinstance(data, Mapping):
        raise ValueError("buffer_retention must be a mapping")
    _reject_unknown(data, _BUFFER_RETENTION_KEYS, "buffer_retention")
    max_records = data.get("max_records")
    max_age_ms = data.get("max_age_ms")
    if not isinstance(max_records, int):
        raise ValueError("buffer_retention.max_records must be an int")
    if max_age_ms is not None and not isinstance(max_age_ms, int):
        raise ValueError("buffer_retention.max_age_ms must be an int")
    return BufferRetentionConfig(max_records=max_records, max_age_ms=max_age_ms)


def _parse_output_publish(data: object) -> OutputPublishConfig:
    if not isinstance(data, Mapping):
        raise ValueError("output_publish must be a mapping")
    _reject_unknown(data, _OUTPUT_PUBLISH_KEYS, "output_publish")
    max_pending = data.get("max_pending")
    max_block_ms = data.get("max_block_ms")
    if not isinstance(max_pending, int):
        raise ValueError("output_publish.max_pending must be an int")
    if max_block_ms is not None and not isinstance(max_block_ms, int):
        raise ValueError("output_publish.max_block_ms must be an int")
    return OutputPublishConfig(max_pending=max_pending, max_block_ms=max_block_ms)


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
