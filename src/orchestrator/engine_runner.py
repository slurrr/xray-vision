from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field

from orchestrator.contracts import ENGINE_MODE_HYSTERESIS, ENGINE_MODE_TRUTH
from orchestrator.observability import NullLogger, NullMetrics, Observability
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.engine import run, run_with_hysteresis
from regime_engine.hysteresis import HysteresisConfig, HysteresisState, HysteresisStore
from regime_engine.hysteresis.persistence import build_record, encode_record, restore_store

_EMBEDDED_EVIDENCE_KEY = "composer_evidence_snapshot_v1"
_COMPACTION_INTERVAL = 5000 # number of appends between compactions (total)


def _embedded_evidence_present(snapshot: RegimeInputSnapshot) -> bool:
    structure_levels = snapshot.market.structure_levels
    if not isinstance(structure_levels, Mapping):
        return False
    return _EMBEDDED_EVIDENCE_KEY in structure_levels


@dataclass
class HysteresisStatePersistence:
    store: HysteresisStore
    path: str
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _append_count: int = field(default=0, init=False, repr=False)

    @classmethod
    def restore(
        cls, *, path: str, config: HysteresisConfig | None
    ) -> HysteresisStatePersistence:
        active_config = config or HysteresisConfig()
        store = restore_store(path=path, config=active_config)
        return cls(store=store, path=path)

    def append(self, state: HysteresisState) -> None:
        with self._lock:
            self._append_record(state)
            self._append_count += 1
            if self._append_count % _COMPACTION_INTERVAL == 0:
                self._compact_locked()

    def compact_atomic(self) -> None:
        with self._lock:
            self._compact_locked()

    def _append_record(self, state: HysteresisState) -> None:
        record = build_record(state)
        payload = encode_record(record)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _compact_locked(self) -> None:
        if not self.store.states:
            return
        dir_path = os.path.dirname(self.path) or "."
        os.makedirs(dir_path, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".hysteresis_compact_", dir=dir_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for symbol in sorted(self.store.states):
                    record = build_record(self.store.states[symbol])
                    handle.write(encode_record(record))
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            _fsync_directory(dir_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class HysteresisPersistenceError(RuntimeError):
    error_kind = "hysteresis_persistence_failure"


class HysteresisMonotonicityError(RuntimeError):
    error_kind = "hysteresis_monotonicity_violation"


@dataclass
class EngineRunner:
    engine_mode: str
    hysteresis_store: HysteresisStatePersistence | None = None
    hysteresis_config: HysteresisConfig | None = None
    observability: Observability = Observability(
        logger=NullLogger(), metrics=NullMetrics()
    )

    def run_engine(self, snapshot: RegimeInputSnapshot) -> EngineRunResult:
        if self.engine_mode == ENGINE_MODE_HYSTERESIS:
            if self.hysteresis_store is None:
                raise RuntimeError("hysteresis_store is required for hysteresis mode")
            self._guard_monotonic(snapshot)
        self.observability.log_engine_invocation(
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
            embedded_evidence_present=_embedded_evidence_present(snapshot),
        )
        if self.engine_mode == ENGINE_MODE_TRUTH:
            return EngineRunResult(regime_output=run(snapshot), hysteresis_state=None)
        if self.engine_mode == ENGINE_MODE_HYSTERESIS:
            store = self.hysteresis_store
            assert store is not None
            prev_state = store.store.state_for(snapshot.symbol)
            regime_output = run(snapshot)
            hysteresis_state = run_with_hysteresis(
                snapshot, state=store.store, config=self.hysteresis_config
            )
            if _state_advanced(prev_state, hysteresis_state):
                try:
                    store.append(hysteresis_state)
                except Exception as exc:
                    _restore_state(store.store, snapshot.symbol, prev_state)
                    raise HysteresisPersistenceError(str(exc)) from exc
            return EngineRunResult(
                regime_output=regime_output,
                hysteresis_state=hysteresis_state,
            )
        raise ValueError("unsupported engine_mode")

    def _guard_monotonic(self, snapshot: RegimeInputSnapshot) -> None:
        store = self.hysteresis_store
        if store is None:
            return
        prev_state = store.store.state_for(snapshot.symbol)
        if prev_state is None:
            return
        if snapshot.timestamp < prev_state.engine_timestamp_ms:
            raise HysteresisMonotonicityError("hysteresis monotonicity violation")


def _state_advanced(
    prev_state: HysteresisState | None, next_state: HysteresisState
) -> bool:
    if prev_state is None:
        return True
    if next_state.engine_timestamp_ms > prev_state.engine_timestamp_ms:
        return True
    if prev_state.anchor_regime != next_state.anchor_regime:
        return True
    if prev_state.candidate_regime != next_state.candidate_regime:
        return True
    if prev_state.progress_current != next_state.progress_current:
        return True
    return False


def _restore_state(
    store: HysteresisStore,
    symbol: str,
    prev_state: HysteresisState | None,
) -> None:
    if prev_state is None:
        store.states.pop(symbol, None)
    else:
        store.update(symbol, prev_state)


def _fsync_directory(path: str) -> None:
    dir_fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


@dataclass(frozen=True)
class EngineRunResult:
    regime_output: RegimeOutput
    hysteresis_state: HysteresisState | None
