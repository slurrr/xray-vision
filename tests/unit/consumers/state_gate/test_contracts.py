import unittest
from dataclasses import FrozenInstanceError

from consumers.state_gate import (
    EVENT_TYPES,
    GATE_STATUS_CLOSED,
    GATE_STATUS_OPEN,
    INPUT_EVENT_TYPES,
    INPUT_IDEMPOTENCY_FIELDS,
    OUTPUT_IDEMPOTENCY_FIELDS,
    REASON_CODE_INTERNAL_FAILURE,
    REASON_CODE_RUN_FAILED,
    REASON_CODE_TRANSITION_ACTIVE,
    REASON_CODES,
    REASON_PREFIX_DENYLISTED_INVALIDATION,
    RESET_REASON_ENGINE_GAP,
    RESET_REASON_TIMESTAMP_GAP,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    GateEvaluatedPayload,
    OperationLimits,
    StateGateConfig,
    StateGateEvent,
    StateGateHaltedPayload,
    StateGateSnapshot,
    StateGateStateRecord,
    StateResetPayload,
    input_idempotency_key,
    output_idempotency_key,
    validate_config,
)


class TestStateGateContracts(unittest.TestCase):
    def test_state_gate_event_is_frozen(self) -> None:
        payload = GateEvaluatedPayload()
        event = StateGateEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="GateEvaluated",
            symbol="TEST",
            engine_timestamp_ms=123,
            run_id="run-1",
            state_status="READY",
            gate_status="OPEN",
            reasons=[],
            payload=payload,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
        )
        with self.assertRaises(FrozenInstanceError):
            event.symbol = "OTHER"  # type: ignore[misc]

    def test_state_gate_payloads_are_frozen(self) -> None:
        reset = StateResetPayload(reset_reason="reset_timestamp_gap")
        halted = StateGateHaltedPayload(error_kind="persistence_failure", error_detail="full")
        with self.assertRaises(FrozenInstanceError):
            reset.reset_reason = "reset_engine_gap"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            halted.error_kind = "other"  # type: ignore[misc]

    def test_state_record_and_snapshot_are_frozen(self) -> None:
        record = StateGateStateRecord(
            symbol="TEST",
            engine_timestamp_ms=123,
            run_id="run-1",
            state_status="READY",
            gate_status="OPEN",
            reasons=["reset_timestamp_gap"],
            engine_mode="truth",
            source_event_type="EngineRunCompleted",
        )
        snapshot = StateGateSnapshot(
            symbol="TEST",
            last_run_id="run-1",
            last_engine_timestamp_ms=123,
            state_status="READY",
            gate_status="OPEN",
            reasons=["reset_timestamp_gap"],
            engine_mode="truth",
            source_event_type="EngineRunCompleted",
        )
        with self.assertRaises(FrozenInstanceError):
            record.run_id = "run-2"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            snapshot.state_status = "HOLD"  # type: ignore[misc]

    def test_event_types_and_reason_codes_are_declared(self) -> None:
        self.assertEqual(
            EVENT_TYPES,
            ("GateEvaluated", "StateReset", "StateGateHalted"),
        )
        self.assertEqual(
            INPUT_EVENT_TYPES,
            ("EngineRunCompleted", "EngineRunFailed", "HysteresisStatePublished"),
        )
        self.assertIn(REASON_CODE_RUN_FAILED, REASON_CODES)
        self.assertIn(REASON_CODE_TRANSITION_ACTIVE, REASON_CODES)
        self.assertIn(REASON_PREFIX_DENYLISTED_INVALIDATION, REASON_CODES)
        self.assertIn(REASON_CODE_INTERNAL_FAILURE, REASON_CODES)
        self.assertIn(RESET_REASON_TIMESTAMP_GAP, REASON_CODES)
        self.assertIn(RESET_REASON_ENGINE_GAP, REASON_CODES)

    def test_schema_name_and_versions(self) -> None:
        self.assertEqual(SCHEMA_NAME, "state_gate_event")
        self.assertEqual(SCHEMA_VERSION, "1")
        self.assertEqual(GATE_STATUS_OPEN, "OPEN")
        self.assertEqual(GATE_STATUS_CLOSED, "CLOSED")

    def test_idempotency_keys(self) -> None:
        self.assertEqual(INPUT_IDEMPOTENCY_FIELDS, ("run_id", "input_event_type"))
        self.assertEqual(OUTPUT_IDEMPOTENCY_FIELDS, ("run_id", "event_type"))
        self.assertEqual(input_idempotency_key("run-1", "EngineRunFailed"), "run-1:EngineRunFailed")
        self.assertEqual(output_idempotency_key("run-1", "GateEvaluated"), "run-1:GateEvaluated")

    def test_config_validation_accepts_positive_values(self) -> None:
        config = StateGateConfig(
            max_gap_ms=1000,
            denylisted_invalidations=["liquidation_spike"],
            block_during_transition=True,
            input_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
            persistence_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
            publish_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
        )
        validate_config(config)

    def test_config_validation_rejects_non_positive_values(self) -> None:
        with self.assertRaises(ValueError):
            validate_config(
                StateGateConfig(
                    max_gap_ms=0,
                    denylisted_invalidations=[],
                    block_during_transition=False,
                    input_limits=OperationLimits(
                        max_pending=0, max_block_ms=None, max_failures=None
                    ),
                    persistence_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                    publish_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                )
            )
        with self.assertRaises(ValueError):
            validate_config(
                StateGateConfig(
                    max_gap_ms=1,
                    denylisted_invalidations=[],
                    block_during_transition=False,
                    input_limits=OperationLimits(
                        max_pending=1, max_block_ms=0, max_failures=None
                    ),
                    persistence_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                    publish_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                )
            )
        with self.assertRaises(ValueError):
            validate_config(
                StateGateConfig(
                    max_gap_ms=1,
                    denylisted_invalidations=[],
                    block_during_transition=False,
                    input_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=0
                    ),
                    persistence_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                    publish_limits=OperationLimits(
                        max_pending=1, max_block_ms=None, max_failures=None
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
