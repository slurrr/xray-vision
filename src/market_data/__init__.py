"""market_data contracts and configuration."""

from market_data.adapter import (
    Adapter,
    AdapterState,
    AdapterSupervisor,
    StreamKey,
)
from market_data.decoder import decode_and_ingest
from market_data.observability import NullLogger, NullMetrics, Observability, StdlibLogger
from market_data.serialization import deserialize_event, serialize_event
from market_data.config import (
    BackpressureConfig,
    MarketDataConfig,
    OperationalLimits,
    RetryPolicy,
    SourceConfig,
    validate_config,
)
from market_data.contracts import (
    EVENT_TYPE_REQUIRED_NORMALIZED_KEYS,
    EVENT_TYPES,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    EventType,
    RawMarketEvent,
)
from market_data.sink import BackpressureError, RawEventSink
from market_data.pipeline import IngestionPipeline

__all__ = [
    "BackpressureConfig",
    "Adapter",
    "AdapterState",
    "AdapterSupervisor",
    "StreamKey",
    "MarketDataConfig",
    "OperationalLimits",
    "RetryPolicy",
    "SourceConfig",
    "validate_config",
    "IngestionPipeline",
    "decode_and_ingest",
    "NullLogger",
    "NullMetrics",
    "Observability",
    "StdlibLogger",
    "deserialize_event",
    "serialize_event",
    "EVENT_TYPE_REQUIRED_NORMALIZED_KEYS",
    "EVENT_TYPES",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "EventType",
    "RawMarketEvent",
    "BackpressureError",
    "RawEventSink",
]
