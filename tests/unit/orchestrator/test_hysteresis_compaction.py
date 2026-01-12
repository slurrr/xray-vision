from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.engine_runner import HysteresisStatePersistence
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.persistence import build_record, encode_record, restore_store
from regime_engine.hysteresis.state import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    HysteresisConfig,
    HysteresisState,
    HysteresisStore,
)


def _make_state(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    anchor_regime: Regime,
    candidate_regime: Regime | None = None,
    progress_current: int = 0,
    progress_required: int = 3,
    last_commit_timestamp_ms: int | None = None,
) -> HysteresisState:
    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        anchor_regime=anchor_regime,
        candidate_regime=candidate_regime,
        progress_current=progress_current,
        progress_required=progress_required,
        last_commit_timestamp_ms=last_commit_timestamp_ms,
        reason_codes=(),
        debug=None,
    )


class TestHysteresisCompaction(unittest.TestCase):
    def test_compact_atomic_writes_sorted_records(self) -> None:
        state_a = _make_state(
            symbol="A", engine_timestamp_ms=10, anchor_regime=Regime.CHOP_BALANCED
        )
        state_b = _make_state(
            symbol="B", engine_timestamp_ms=20, anchor_regime=Regime.TREND_BUILD_UP
        )
        store = HysteresisStore(states={"B": state_b, "A": state_a})
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = str(Path(tmp_dir) / "hysteresis.jsonl")
            persistence = HysteresisStatePersistence(store=store, path=path)

            persistence.compact_atomic()

            content = Path(path).read_text(encoding="utf-8")
            self.assertTrue(content.endswith("\n"))
            lines = content.splitlines()
            expected = [
                encode_record(build_record(state_a)),
                encode_record(build_record(state_b)),
            ]
            self.assertEqual(lines, expected)

    def test_restore_compact_restore_is_equivalent(self) -> None:
        config = HysteresisConfig()
        state_a1 = _make_state(
            symbol="A", engine_timestamp_ms=1, anchor_regime=Regime.CHOP_BALANCED
        )
        state_a2 = _make_state(
            symbol="A", engine_timestamp_ms=2, anchor_regime=Regime.TREND_BUILD_UP
        )
        state_b = _make_state(
            symbol="B", engine_timestamp_ms=5, anchor_regime=Regime.SQUEEZE_UP
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "hysteresis.jsonl"
            lines = [
                encode_record(build_record(state_a1)),
                encode_record(build_record(state_a2)),
                encode_record(build_record(state_b)),
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            store_before = restore_store(path=str(path), config=config)
            persistence = HysteresisStatePersistence(store=store_before, path=str(path))

            persistence.compact_atomic()

            store_after = restore_store(path=str(path), config=config)
            self.assertEqual(store_after.states, store_before.states)


if __name__ == "__main__":
    unittest.main()
