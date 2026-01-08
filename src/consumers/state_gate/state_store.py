from __future__ import annotations

from collections.abc import Iterable, Sequence

from .contracts import (
    GATE_STATUS_CLOSED,
    STATE_STATUS_BOOTSTRAP,
    GateEvaluatedPayload,
    StateGateEvent,
    StateGateSnapshot,
    StateGateStateRecord,
    StateResetPayload,
)


class StateGateStateStore:
    def __init__(self, records: Sequence[StateGateStateRecord] | None = None) -> None:
        self._records: list[StateGateStateRecord] = list(records or [])
        self._snapshots: dict[str, StateGateSnapshot] = {}
        for record in self._records:
            self._update_snapshot(record)

    def append_record(self, record: StateGateStateRecord) -> None:
        self._records.append(record)
        self._update_snapshot(record)

    def append_event(self, event: StateGateEvent) -> StateGateStateRecord:
        record = _record_from_event(event)
        self.append_record(record)
        return record

    def records(self) -> Sequence[StateGateStateRecord]:
        return tuple(self._records)

    def snapshot_for(self, symbol: str) -> StateGateSnapshot:
        return self._snapshots.get(symbol, _bootstrap_snapshot(symbol=symbol))

    def snapshots(self) -> dict[str, StateGateSnapshot]:
        return dict(self._snapshots)

    def processed_run_ids(self) -> Iterable[str]:
        return (record.run_id for record in self._records)

    def latest_engine_timestamps(self) -> dict[str, int]:
        timestamps: dict[str, int] = {}
        for symbol, snapshot in self._snapshots.items():
            if snapshot.last_engine_timestamp_ms is not None:
                timestamps[symbol] = snapshot.last_engine_timestamp_ms
        return timestamps

    def _update_snapshot(self, record: StateGateStateRecord) -> None:
        self._snapshots[record.symbol] = StateGateSnapshot(
            symbol=record.symbol,
            last_run_id=record.run_id,
            last_engine_timestamp_ms=record.engine_timestamp_ms,
            state_status=record.state_status,
            gate_status=record.gate_status,
            reasons=record.reasons,
            engine_mode=record.engine_mode,
            source_event_type=record.source_event_type,
        )


def _record_from_event(event: StateGateEvent) -> StateGateStateRecord:
    payload = event.payload
    if event.event_type == "GateEvaluated":
        return StateGateStateRecord(
            symbol=event.symbol,
            engine_timestamp_ms=event.engine_timestamp_ms,
            run_id=event.run_id,
            state_status=event.state_status,
            gate_status=event.gate_status,
            reasons=list(event.reasons),
            engine_mode=event.engine_mode,
            source_event_type=event.input_event_type,
            regime_output=payload.regime_output
            if isinstance(payload, GateEvaluatedPayload)
            else None,
            hysteresis_state=payload.hysteresis_state
            if isinstance(payload, GateEvaluatedPayload)
            else None,
        )
    if event.event_type == "StateReset":
        reset_reason = payload.reset_reason if isinstance(payload, StateResetPayload) else None
        return StateGateStateRecord(
            symbol=event.symbol,
            engine_timestamp_ms=event.engine_timestamp_ms,
            run_id=event.run_id,
            state_status=STATE_STATUS_BOOTSTRAP,
            gate_status=GATE_STATUS_CLOSED,
            reasons=list(event.reasons),
            engine_mode=event.engine_mode,
            source_event_type=event.input_event_type,
            reset_reason=reset_reason,
        )
    if event.event_type == "StateGateHalted":
        return StateGateStateRecord(
            symbol=event.symbol,
            engine_timestamp_ms=event.engine_timestamp_ms,
            run_id=event.run_id,
            state_status=event.state_status,
            gate_status=event.gate_status,
            reasons=list(event.reasons),
            engine_mode=event.engine_mode,
            source_event_type=event.input_event_type,
            error_kind=getattr(payload, "error_kind", None),
            error_detail=getattr(payload, "error_detail", None),
        )
    raise ValueError(f"unsupported event_type for persistence: {event.event_type}")


def _bootstrap_snapshot(*, symbol: str) -> StateGateSnapshot:
    return StateGateSnapshot(
        symbol=symbol,
        last_run_id=None,
        last_engine_timestamp_ms=None,
        state_status=STATE_STATUS_BOOTSTRAP,
        gate_status=GATE_STATUS_CLOSED,
        reasons=[],
        engine_mode=None,
        source_event_type=None,
    )
