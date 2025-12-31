from __future__ import annotations

from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
)
from regime_engine.snapshot_builder.feeds.base import SnapshotFeed


class BinanceFeed(SnapshotFeed):
    """
    Stub adapter for Binance REST/WS.

    Phase 0: method signatures only; no live connectivity.
    """

    def market(self, *, symbol: str, timestamp_ms: int) -> MarketSnapshot:  # pragma: no cover
        raise NotImplementedError

    def derivatives(
        self, *, symbol: str, timestamp_ms: int
    ) -> DerivativesSnapshot:  # pragma: no cover
        raise NotImplementedError

    def flow(self, *, symbol: str, timestamp_ms: int) -> FlowSnapshot:  # pragma: no cover
        raise NotImplementedError

    def context(self, *, symbol: str, timestamp_ms: int) -> ContextSnapshot:  # pragma: no cover
        raise NotImplementedError

