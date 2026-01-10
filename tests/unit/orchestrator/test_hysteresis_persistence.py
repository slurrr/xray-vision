from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from orchestrator.engine_runner import (
    EngineRunner,
    HysteresisMonotonicityError,
    HysteresisPersistenceError,
    HysteresisStatePersistence,
)
from orchestrator.observability import NullMetrics, Observability
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.hysteresis import advance_hysteresis
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState, HysteresisStore
from regime_engine.state.state import RegimeState


def _snapshot(*, symbol: str, timestamp: int) -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels={},
            acceptance_score=0.0,
            sweep_score=0.0,
        ),
        derivatives=DerivativesSnapshot(
            open_interest=1.0,
            oi_slope_short=0.0,
            oi_slope_med=0.0,
            oi_accel=0.0,
            funding_rate=0.0,
            funding_slope=0.0,
            funding_z=0.0,
            liquidation_intensity=None,
        ),
        flow=FlowSnapshot(
            cvd=0.0,
            cvd_slope=0.0,
            cvd_efficiency=0.0,
            aggressive_volume_ratio=0.0,
        ),
        context=ContextSnapshot(
            rs_vs_btc=0.0,
            beta_to_btc=0.0,
            alt_breadth=0.0,
            btc_regime=None,
            eth_regime=None,
        ),
    )


def _state(*, symbol: str, timestamp: int) -> HysteresisState:
    return HysteresisState(
        schema="hysteresis_state",
        schema_version="1",
        symbol=symbol,
        engine_timestamp_ms=timestamp,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=None,
        progress_current=0,
        progress_required=3,
        last_commit_timestamp_ms=None,
        reason_codes=(),
        debug=None,
    )


def test_engine_runner_guards_monotonicity(tmp_path: Path) -> None:
    store = HysteresisStore(states={"BTCUSDT": _state(symbol="BTCUSDT", timestamp=200)})
    persistence = HysteresisStatePersistence(store=store, path=str(tmp_path / "state.jsonl"))
    logger = _RecordingLogger()
    runner = EngineRunner(
        engine_mode="hysteresis",
        hysteresis_store=persistence,
        observability=Observability(logger=logger, metrics=NullMetrics()),
    )

    with pytest.raises(HysteresisMonotonicityError):
        runner.run_engine(_snapshot(symbol="BTCUSDT", timestamp=100))
    assert logger.messages == []


def test_engine_runner_noop_does_not_append(monkeypatch: pytest.MonkeyPatch) -> None:
    store = HysteresisStore(states={"BTCUSDT": _state(symbol="BTCUSDT", timestamp=90)})
    persistence = HysteresisStatePersistence(store=store, path="ignored")
    runner = EngineRunner(engine_mode="hysteresis", hysteresis_store=persistence)

    append_calls: list[HysteresisState] = []

    def fake_append_record(path: str, state: HysteresisState) -> None:
        append_calls.append(state)

    def fake_run(snapshot: RegimeInputSnapshot) -> RegimeOutput:
        return RegimeOutput(
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            regime=Regime.CHOP_BALANCED,
            confidence=0.0,
            drivers=[],
            invalidations=[],
            permissions=[],
        )

    def fake_run_with_hysteresis(
        snapshot: RegimeInputSnapshot, *, state: HysteresisStore, config: object | None = None
    ) -> HysteresisState:
        prev_state = state.state_for(snapshot.symbol)
        regime_state = RegimeState(
            schema="regime_state",
            schema_version="1",
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
            belief_by_regime={Regime.CHOP_BALANCED: 1.0},
            anchor_regime=Regime.CHOP_BALANCED,
        )
        active_config = HysteresisConfig()
        next_state = advance_hysteresis(prev_state, regime_state, active_config)
        state.update(snapshot.symbol, next_state)
        return next_state

    monkeypatch.setattr("orchestrator.engine_runner.run", fake_run)
    monkeypatch.setattr("orchestrator.engine_runner.run_with_hysteresis", fake_run_with_hysteresis)
    monkeypatch.setattr("orchestrator.engine_runner.append_record", fake_append_record)

    runner.run_engine(_snapshot(symbol="BTCUSDT", timestamp=100))
    assert append_calls == []


def test_engine_runner_persistence_failure_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    persistence = HysteresisStatePersistence(store=HysteresisStore(states={}), path="ignored")
    runner = EngineRunner(engine_mode="hysteresis", hysteresis_store=persistence)

    def fake_run(snapshot: RegimeInputSnapshot) -> RegimeOutput:
        return RegimeOutput(
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            regime=Regime.CHOP_BALANCED,
            confidence=0.0,
            drivers=[],
            invalidations=[],
            permissions=[],
        )

    def fake_run_with_hysteresis(
        snapshot: RegimeInputSnapshot, *, state: HysteresisStore, config: object | None = None
    ) -> HysteresisState:
        prev_state = state.state_for(snapshot.symbol)
        regime_state = RegimeState(
            schema="regime_state",
            schema_version="1",
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
            belief_by_regime={
                Regime.CHOP_BALANCED: 0.1,
                Regime.TREND_BUILD_UP: 0.9,
            },
            anchor_regime=Regime.CHOP_BALANCED,
        )
        active_config = HysteresisConfig()
        next_state = advance_hysteresis(prev_state, regime_state, active_config)
        state.update(snapshot.symbol, next_state)
        return next_state

    def fake_append_record(path: str, state: HysteresisState) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr("orchestrator.engine_runner.run", fake_run)
    monkeypatch.setattr("orchestrator.engine_runner.run_with_hysteresis", fake_run_with_hysteresis)
    monkeypatch.setattr("orchestrator.engine_runner.append_record", fake_append_record)

    with pytest.raises(HysteresisPersistenceError):
        runner.run_engine(_snapshot(symbol="BTCUSDT", timestamp=100))
    assert persistence.store.state_for("BTCUSDT") is None


class _RecordingLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.messages.append(message)
