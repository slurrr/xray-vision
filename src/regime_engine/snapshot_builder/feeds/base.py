from __future__ import annotations

from typing import Protocol

from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
)


class SnapshotFeed(Protocol):
    """
    Feed interface for building frozen snapshots.

    Phase 0: interface-only. Implementations must not contain regime logic.
    Missing data must be represented explicitly (e.g., using `MISSING` from
    `regime_engine.contracts.snapshots`), not silently omitted.
    """

    def market(self, *, symbol: str, timestamp_ms: int) -> MarketSnapshot: ...

    def derivatives(self, *, symbol: str, timestamp_ms: int) -> DerivativesSnapshot: ...

    def flow(self, *, symbol: str, timestamp_ms: int) -> FlowSnapshot: ...

    def context(self, *, symbol: str, timestamp_ms: int) -> ContextSnapshot: ...

