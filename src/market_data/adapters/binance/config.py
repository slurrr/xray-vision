from __future__ import annotations

from dataclasses import dataclass

from market_data.config import RetryPolicy


@dataclass(frozen=True)
class BinanceTradeAdapterConfig:
    source_id: str
    symbol: str
    stream: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls) -> BinanceTradeAdapterConfig:
        return cls(
            source_id="binance",
            symbol="BTCUSDT",
            stream="btcusdt@trade",
            ws_url="wss://stream.binance.com:9443/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )
