from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from composer.observability import Observability as ComposerObservability
from composer.observability import StdlibLogger as ComposerStdlibLogger
from composer.observability import set_observability as set_composer_observability
from market_data.observability import (
    NullMetrics as MarketNullMetrics,
)
from market_data.observability import (
    Observability as MarketObservability,
)
from market_data.observability import (
    StdlibLogger as MarketStdlibLogger,
)
from regime_engine.observability import Observability as RegimeObservability
from regime_engine.observability import StdlibLogger as RegimeStdlibLogger
from regime_engine.observability import set_observability as set_regime_observability


@dataclass(frozen=True)
class RuntimeObservability:
    logger: logging.Logger

    def log_runtime_started(self) -> None:
        self.logger.info("runtime.started", extra={"fields": {}})

    def log_market_data_adapters_initialized(
        self,
        *,
        symbol: str,
        adapter_count: int,
        optional_enabled: bool,
    ) -> None:
        self.logger.info(
            "runtime.market_data_adapters_initialized",
            extra={
                "fields": {
                    "symbol": symbol,
                    "adapter_count": adapter_count,
                    "optional_enabled": optional_enabled,
                }
            },
        )


@dataclass(frozen=True)
class ObservabilityBundle:
    runtime: RuntimeObservability
    market_data: MarketObservability


class _FieldsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "fields"):
            record.fields = {}
        return True


def bootstrap_observability(*, log_dir: str) -> ObservabilityBundle:
    _setup_logging(log_dir=log_dir)
    runtime_logger = logging.getLogger("runtime")
    market_logger = logging.getLogger("market_data")
    composer_logger = logging.getLogger("composer")
    regime_logger = logging.getLogger("regime_engine")

    set_composer_observability(
        ComposerObservability(logger=ComposerStdlibLogger(composer_logger))
    )
    set_regime_observability(RegimeObservability(logger=RegimeStdlibLogger(regime_logger)))

    return ObservabilityBundle(
        runtime=RuntimeObservability(logger=runtime_logger),
        market_data=MarketObservability(
            logger=MarketStdlibLogger(market_logger),
            metrics=MarketNullMetrics(),
        ),
    )


def _setup_logging(*, log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    fields_filter = _FieldsFilter()
    handler = logging.FileHandler(os.path.join(log_dir, "xray-vision.log"))
    handler.addFilter(fields_filter)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(fields)s"
    )
    handler.setFormatter(formatter)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
    )
    logging.getLogger("orchestrator").setLevel(logging.DEBUG)
    logging.getLogger("market_data").setLevel(logging.WARNING)
    logging.getLogger("consumers").setLevel(logging.DEBUG)
    logging.getLogger("runtime").setLevel(logging.DEBUG)
    logging.getLogger("composer").setLevel(logging.DEBUG)
    logging.getLogger("regime_engine").setLevel(logging.DEBUG)
