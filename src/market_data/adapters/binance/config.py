from __future__ import annotations

from dataclasses import dataclass

from market_data.config import RetryPolicy


@dataclass(frozen=True)
class BinanceAggTradeConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceAggTradeConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@aggTrade",
            channel="trades",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceKlineConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceKlineConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@kline_3m",
            channel="candle_3m",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceBookTickerConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceBookTickerConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@bookTicker",
            channel="book_top",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceDepthConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceDepthConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@depth@100ms",
            channel="book_delta",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceMarkPriceConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceMarkPriceConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@markPrice@1s",
            channel="mark_price",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceForceOrderConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceForceOrderConfig:
        stream_symbol = symbol.lower()
        return cls(
            source_id="binance",
            symbol=symbol,
            stream=f"{stream_symbol}@forceOrder",
            channel="liquidation",
            ws_url="wss://fstream.binance.com/ws",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            connect_timeout_ms=10_000,
            read_timeout_ms=30_000,
        )


@dataclass(frozen=True)
class BinanceOpenInterestConfig:
    source_id: str
    symbol: str
    rest_url: str
    channel: str
    retry: RetryPolicy
    request_timeout_ms: int
    poll_interval_ms: int

    @classmethod
    def default(cls, *, symbol: str = "BTCUSDT") -> BinanceOpenInterestConfig:
        return cls(
            source_id="binance",
            symbol=symbol,
            rest_url="https://fapi.binance.com",
            channel="open_interest",
            retry=RetryPolicy(
                min_delay_ms=250,
                max_delay_ms=5_000,
                max_attempts=5,
            ),
            request_timeout_ms=10_000,
            poll_interval_ms=10_000,
        )
