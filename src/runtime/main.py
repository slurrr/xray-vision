from __future__ import annotations

from runtime.bus import EventBus
from runtime.stub_feed import StubMarketDataFeed
from runtime.wiring import build_runtime, register_subscriptions

SOURCE_ID = "stub"
SYMBOL = "BTC-USD"
INTERVAL_MS = 1000


def main() -> None:
    bus = EventBus()
    runtime = build_runtime(bus)
    register_subscriptions(bus, runtime)
    runtime.dashboards.start()
    feed = StubMarketDataFeed(
        bus=bus,
        source_id=SOURCE_ID,
        symbol=SYMBOL,
        interval_ms=INTERVAL_MS,
    )
    try:
        feed.run()
    finally:
        runtime.dashboards.stop()


if __name__ == "__main__":
    main()
