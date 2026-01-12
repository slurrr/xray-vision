from __future__ import annotations

import time

from consumers.analysis_engine.config.loader import (
    load_default_config as load_analysis_engine_config,
)
from consumers.dashboards.config.loader import load_default_config as load_dashboards_config
from consumers.state_gate.config.loader import load_default_config as load_state_gate_config
from market_data.config.loader import load_default_config as load_market_data_config
from market_data.runtime import build_market_data_runtime
from orchestrator.config.loader import load_default_config as load_orchestrator_config
from runtime.bus import EventBus
from runtime.bus_sink import BusRawEventSink
from runtime.observability import bootstrap_observability
from runtime.wiring import build_runtime, register_subscriptions

# Configuration will go in config files later
LOG_DIR = "logs"


def main() -> None:
    observability = bootstrap_observability(log_dir=LOG_DIR)
    analysis_engine_config = load_analysis_engine_config()
    dashboards_config = load_dashboards_config()
    state_gate_config = load_state_gate_config()
    orchestrator_config = load_orchestrator_config()
    market_data_config = load_market_data_config()
    bus = EventBus()
    runtime = build_runtime(
        bus,
        orchestrator_config=orchestrator_config,
        state_gate_config=state_gate_config,
        analysis_engine_config=analysis_engine_config,
        dashboards_config=dashboards_config,
    )
    register_subscriptions(bus, runtime)
    market_data_runtime = build_market_data_runtime(
        sink=BusRawEventSink(bus),
        observability=observability.market_data,
        config=market_data_config,
    )
    runtime.orchestrator.start()
    runtime.dashboards.start()
    runtime.dashboards.render_once()
    observability.runtime.log_runtime_started()
    market_info = market_data_runtime.info
    observability.runtime.log_market_data_adapters_initialized(
        symbol=market_info.symbol,
        adapter_count=market_info.adapter_count,
        optional_enabled=market_info.optional_enabled,
    )
    market_data_runtime.start()
    try:
        while True:
            time.sleep(1)
    finally:
        market_data_runtime.stop()
        runtime.orchestrator.stop()
        runtime.dashboards.stop()


if __name__ == "__main__":
    main()
