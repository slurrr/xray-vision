from __future__ import annotations

from dataclasses import dataclass

from orchestrator.contracts import ENGINE_MODE_HYSTERESIS, ENGINE_MODE_TRUTH
from regime_engine.engine import run, run_with_hysteresis
from regime_engine.hysteresis import HysteresisConfig, HysteresisDecision, HysteresisStore
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot


@dataclass
class HysteresisStateLog:
    store: HysteresisStore
    records: list[tuple[str, int]]

    def __init__(self) -> None:
        self.store = HysteresisStore(states={})
        self.records = []

    def update(self, symbol: str, timestamp_ms: int) -> None:
        self.records.append((symbol, timestamp_ms))


@dataclass
class EngineRunner:
    engine_mode: str
    hysteresis_store: HysteresisStateLog | None = None
    hysteresis_config: HysteresisConfig | None = None

    def run_engine(self, snapshot: RegimeInputSnapshot) -> RegimeOutput | HysteresisDecision:
        if self.engine_mode == ENGINE_MODE_TRUTH:
            return run(snapshot)
        if self.engine_mode == ENGINE_MODE_HYSTERESIS:
            if self.hysteresis_store is None:
                raise RuntimeError("hysteresis_store is required for hysteresis mode")
            decision = run_with_hysteresis(
                snapshot, state=self.hysteresis_store.store, config=self.hysteresis_config
            )
            self.hysteresis_store.update(snapshot.symbol, snapshot.timestamp)
            return decision
        raise ValueError("unsupported engine_mode")
