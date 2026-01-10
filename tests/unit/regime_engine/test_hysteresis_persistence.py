from __future__ import annotations

import json
from pathlib import Path

import pytest

from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.persistence import (
    HysteresisStoreRecord,
    encode_record,
    parse_record,
    restore_store,
)
from regime_engine.hysteresis.state import HysteresisConfig


def test_parse_record_rejects_invalid_schema() -> None:
    with pytest.raises(ValueError):
        parse_record({"schema": "bad", "schema_version": "1"})


def test_restore_selects_latest_record_by_timestamp_and_file_order(tmp_path: Path) -> None:
    path = tmp_path / "state.jsonl"
    record_a = HysteresisStoreRecord(
        symbol="BTCUSDT",
        engine_timestamp_ms=100,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=None,
        progress_current=1,
        last_commit_timestamp_ms=None,
    )
    record_b = HysteresisStoreRecord(
        symbol="BTCUSDT",
        engine_timestamp_ms=100,
        anchor_regime=Regime.TREND_BUILD_UP,
        candidate_regime=None,
        progress_current=2,
        last_commit_timestamp_ms=None,
    )
    record_c = HysteresisStoreRecord(
        symbol="ETHUSDT",
        engine_timestamp_ms=50,
        anchor_regime=Regime.SQUEEZE_DOWN,
        candidate_regime=Regime.TREND_BUILD_DOWN,
        progress_current=0,
        last_commit_timestamp_ms=25,
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(encode_record(record_a))
        handle.write("\n")
        handle.write(encode_record(record_b))
        handle.write("\n")
        handle.write("not-json\n")
        handle.write(encode_record(record_c))
        handle.write("\n")

    store = restore_store(path=str(path), config=HysteresisConfig(window_updates=3))
    btc_state = store.state_for("BTCUSDT")
    eth_state = store.state_for("ETHUSDT")

    assert btc_state is not None
    assert btc_state.anchor_regime == Regime.TREND_BUILD_UP
    assert btc_state.progress_current == 2
    assert eth_state is not None
    assert eth_state.candidate_regime == Regime.TREND_BUILD_DOWN


def test_restore_maps_state_fields(tmp_path: Path) -> None:
    path = tmp_path / "state.jsonl"
    record = HysteresisStoreRecord(
        symbol="BTCUSDT",
        engine_timestamp_ms=123,
        anchor_regime=Regime.CHOP_STOPHUNT,
        candidate_regime=Regime.TREND_EXHAUSTION,
        progress_current=1,
        last_commit_timestamp_ms=50,
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(encode_record(record))
        handle.write("\n")

    store = restore_store(path=str(path), config=HysteresisConfig(window_updates=7))
    state = store.state_for("BTCUSDT")

    assert state is not None
    assert state.progress_required == 7
    assert state.reason_codes == ()
    assert state.debug is None


def test_encode_record_is_compact_json() -> None:
    record = HysteresisStoreRecord(
        symbol="BTCUSDT",
        engine_timestamp_ms=1,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=None,
        progress_current=0,
        last_commit_timestamp_ms=None,
    )
    encoded = encode_record(record)
    decoded = json.loads(encoded)
    assert decoded["schema"] == "hysteresis_store_record"


def test_restore_unreadable_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "state.jsonl"
    path.write_text(encode_record(
        HysteresisStoreRecord(
            symbol="BTCUSDT",
            engine_timestamp_ms=1,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            last_commit_timestamp_ms=None,
        )
    ), encoding="utf-8")
    path.chmod(0)
    try:
        with pytest.raises(OSError):
            restore_store(path=str(path), config=HysteresisConfig(window_updates=3))
    finally:
        path.chmod(0o644)
