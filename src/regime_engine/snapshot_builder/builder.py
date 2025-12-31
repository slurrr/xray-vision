from __future__ import annotations

from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.snapshot_builder.feeds.base import SnapshotFeed


ALIGNMENT_MS = 180_000


def assert_timestamp_aligned(timestamp_ms: int) -> None:
    if timestamp_ms % ALIGNMENT_MS != 0:
        raise ValueError(f"timestamp_ms must be 3m-aligned (ms): got {timestamp_ms}")


def build_snapshot(*, feed: SnapshotFeed, symbol: str, timestamp_ms: int) -> RegimeInputSnapshot:
    """
    Build a frozen RegimeInputSnapshot from a feed.

    Phase 0: orchestration only (no feature/scoring/veto logic). Any explicit missing
    values produced by the feed must propagate unchanged into the snapshot.
    """

    assert_timestamp_aligned(timestamp_ms)
    return RegimeInputSnapshot(
        symbol=symbol,
        timestamp=timestamp_ms,
        market=feed.market(symbol=symbol, timestamp_ms=timestamp_ms),
        derivatives=feed.derivatives(symbol=symbol, timestamp_ms=timestamp_ms),
        flow=feed.flow(symbol=symbol, timestamp_ms=timestamp_ms),
        context=feed.context(symbol=symbol, timestamp_ms=timestamp_ms),
    )

