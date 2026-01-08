from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from orchestrator.contracts import (
    ENGINE_MODE_HYSTERESIS,
    EngineMode,
    EngineRunCompletedPayload,
    EngineRunFailedPayload,
    HysteresisStatePayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.state import HysteresisState

from .contracts import INPUT_EVENT_TYPES, InputEventType


@dataclass(frozen=True)
class AssembledRunInput:
    run_id: str
    symbol: str
    engine_timestamp_ms: int
    engine_mode: EngineMode | None
    input_event_type: InputEventType
    regime_output: RegimeOutput | None = None
    hysteresis_state: HysteresisState | None = None


class RunAssembler:
    def __init__(
        self,
        *,
        processed_run_ids: Iterable[str] | None = None,
        latest_engine_timestamp_ms: Mapping[str, int] | None = None,
    ) -> None:
        self._assemblies: dict[str, _RunAssembly] = {}
        self._processed_run_ids: set[str] = set(processed_run_ids or ())
        self._latest_engine_timestamp_ms: dict[str, int] = dict(latest_engine_timestamp_ms or {})

    def ingest(self, event: OrchestratorEvent) -> AssembledRunInput | None:
        if event.event_type not in INPUT_EVENT_TYPES:
            return None
        if event.run_id in self._processed_run_ids:
            return None

        last_ts = self._latest_engine_timestamp_ms.get(event.symbol)
        if last_ts is not None and event.engine_timestamp_ms <= last_ts:
            self._processed_run_ids.add(event.run_id)
            return None

        assembly = self._assemblies.get(event.run_id)
        if assembly is None:
            assembly = _RunAssembly(
                symbol=event.symbol,
                engine_timestamp_ms=event.engine_timestamp_ms,
                engine_mode=cast(EngineMode | None, event.engine_mode),
            )
            self._assemblies[event.run_id] = assembly
        else:
            assembly.ensure_consistent(
                symbol=event.symbol,
                engine_timestamp_ms=event.engine_timestamp_ms,
            )
            assembly.update_engine_mode(event.engine_mode)

        assembly.apply_event(event)
        ready_event = assembly.ready_event_type()
        if ready_event is None:
            return None

        assembled = AssembledRunInput(
            run_id=event.run_id,
            symbol=assembly.symbol,
            engine_timestamp_ms=assembly.engine_timestamp_ms,
            engine_mode=cast(EngineMode | None, assembly.engine_mode),
            input_event_type=ready_event,
            regime_output=assembly.regime_output
            if ready_event in ("EngineRunCompleted", "HysteresisStatePublished")
            else None,
            hysteresis_state=assembly.hysteresis_state
            if ready_event == "HysteresisStatePublished"
            else None,
        )
        self._processed_run_ids.add(event.run_id)
        self._assemblies.pop(event.run_id, None)
        self._latest_engine_timestamp_ms[assembly.symbol] = assembly.engine_timestamp_ms
        return assembled

    def processed_run_ids(self) -> Sequence[str]:
        return tuple(self._processed_run_ids)

    def latest_engine_timestamp_ms(self, symbol: str) -> int | None:
        return self._latest_engine_timestamp_ms.get(symbol)


class _RunAssembly:
    def __init__(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        engine_mode: EngineMode | None,
    ) -> None:
        self.symbol = symbol
        self.engine_timestamp_ms = engine_timestamp_ms
        self.engine_mode = engine_mode
        self.regime_output: RegimeOutput | None = None
        self.hysteresis_state: HysteresisState | None = None
        self.failed = False

    def ensure_consistent(self, *, symbol: str, engine_timestamp_ms: int) -> None:
        if symbol != self.symbol:
            raise ValueError(
                f"inconsistent symbol for run_id: expected {self.symbol}, got {symbol}"
            )
        if engine_timestamp_ms != self.engine_timestamp_ms:
            raise ValueError(
                f"inconsistent engine_timestamp_ms for run_id: expected "
                f"{self.engine_timestamp_ms}, got {engine_timestamp_ms}"
            )

    def update_engine_mode(self, engine_mode: EngineMode | None) -> None:
        if engine_mode is None:
            return None
        if self.engine_mode is None:
            self.engine_mode = engine_mode
            return None
        if self.engine_mode != engine_mode:
            raise ValueError(
                f"inconsistent engine_mode for run_id: expected {self.engine_mode}, got "
                f"{engine_mode}"
            )

    def apply_event(self, event: OrchestratorEvent) -> None:
        payload = event.payload
        if event.event_type == "EngineRunCompleted":
            if isinstance(payload, EngineRunCompletedPayload):
                self.regime_output = payload.regime_output
            else:
                raise ValueError("EngineRunCompleted payload must be EngineRunCompletedPayload")
        elif event.event_type == "EngineRunFailed":
            if payload is not None and not isinstance(payload, EngineRunFailedPayload):
                raise ValueError(
                    "EngineRunFailed payload must be EngineRunFailedPayload or None"
                )
            self.failed = True
        elif event.event_type == "HysteresisStatePublished":
            if isinstance(payload, HysteresisStatePayload):
                self.hysteresis_state = payload.hysteresis_state
            else:
                raise ValueError(
                    "HysteresisStatePublished payload must be HysteresisStatePayload"
                )

    def ready_event_type(self) -> InputEventType | None:
        if self.hysteresis_state is not None:
            return "HysteresisStatePublished"
        if self.failed:
            return "EngineRunFailed"
        if self.regime_output is not None and self.engine_mode != ENGINE_MODE_HYSTERESIS:
            return "EngineRunCompleted"
        return None
