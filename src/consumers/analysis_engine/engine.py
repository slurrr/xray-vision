from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from consumers.state_gate.contracts import (
    EVENT_TYPE_GATE_EVALUATED,
    EVENT_TYPE_STATE_GATE_HALTED,
    GATE_STATUS_OPEN,
    GateEvaluatedPayload,
    StateGateEvent,
)

from .artifacts import ArtifactStore
from .config import AnalysisEngineConfig, validate_config
from .contracts import (
    ANALYSIS_EVENT_TYPES,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    AnalysisEngineEvent,
    AnalysisModuleStateRecord,
    AnalysisRunStatusPayload,
    ArtifactEmittedPayload,
    ModuleFailedPayload,
    RunContext,
    RunStatus,
)
from .modules import ModuleResult
from .observability import NullLogger, NullMetrics, Observability
from .persistence import IdempotencyStore, ModuleStateStore
from .planning import STAGE_ORDER, ExecutionPlan, build_execution_plan
from .registry import ModuleRegistry


@dataclass
class EngineState:
    idempotency: IdempotencyStore
    module_state_store: ModuleStateStore
    halted_symbols: set[str]


class AnalysisEngine:
    def __init__(
        self,
        *,
        registry: ModuleRegistry,
        config: AnalysisEngineConfig,
        idempotency_store: IdempotencyStore | None = None,
        module_state_store: ModuleStateStore | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._registry = registry
        self._config = config
        validate_config(self._config, self._registry)
        self._plan_by_symbol = self._build_plans()
        self._state = EngineState(
            idempotency=idempotency_store or IdempotencyStore(),
            module_state_store=module_state_store or ModuleStateStore(),
            halted_symbols=set(),
        )
        self._observability = observability or Observability(
            logger=NullLogger(), metrics=NullMetrics()
        )

    def consume(self, event: StateGateEvent) -> list[AnalysisEngineEvent]:
        if event.symbol in self._state.halted_symbols:
            return []

        if event.event_type == EVENT_TYPE_STATE_GATE_HALTED:
            self._state.halted_symbols.add(event.symbol)
            self._observability.mark_halted()
            failed_event = _analysis_event(
                event_type="AnalysisRunFailed",
                symbol=event.symbol,
                run_id=event.run_id,
                engine_timestamp_ms=event.engine_timestamp_ms,
                engine_mode=event.engine_mode,
                source_gate_reasons=event.reasons,
                payload=AnalysisRunStatusPayload(status="FAILED", module_failures=[]),
            )
            self._log_event(failed_event)
            return [failed_event]

        if event.event_type != EVENT_TYPE_GATE_EVALUATED:
            return []

        if self._state.idempotency.has_processed(event.run_id):
            self._observability.record_idempotency_skip()
            return []

        self._state.idempotency.mark_processed(event.run_id)

        if event.gate_status != GATE_STATUS_OPEN:
            skipped = _analysis_event(
                event_type="AnalysisRunSkipped",
                symbol=event.symbol,
                run_id=event.run_id,
                engine_timestamp_ms=event.engine_timestamp_ms,
                engine_mode=event.engine_mode,
                source_gate_reasons=event.reasons,
            )
            self._log_event(skipped)
            return [skipped]

        try:
            plan = self._plan_for_symbol(event.symbol)
        except ValueError:
            failed_event = _analysis_event(
                event_type="AnalysisRunFailed",
                symbol=event.symbol,
                run_id=event.run_id,
                engine_timestamp_ms=event.engine_timestamp_ms,
                engine_mode=event.engine_mode,
                source_gate_reasons=event.reasons,
                payload=AnalysisRunStatusPayload(status="FAILED", module_failures=[]),
            )
            self._log_event(failed_event)
            return [failed_event]

        context = _build_run_context(event)
        artifact_store = ArtifactStore()
        module_failures: list[str] = []
        events: list[AnalysisEngineEvent] = []
        started = _analysis_event(
            event_type="AnalysisRunStarted",
            symbol=event.symbol,
            run_id=event.run_id,
            engine_timestamp_ms=event.engine_timestamp_ms,
            engine_mode=event.engine_mode,
            source_gate_reasons=event.reasons,
        )
        events.append(started)
        self._log_event(started)

        for stage in STAGE_ORDER:
            steps = plan.steps_by_stage.get(stage, ())
            for step in steps:
                module = self._registry.modules[step.module_id]
                if not artifact_store.dependencies_available(module.definition.dependencies):
                    module_failures.append(module.definition.module_id)
                    failed = _analysis_event(
                        event_type="ModuleFailed",
                        symbol=event.symbol,
                        run_id=event.run_id,
                        engine_timestamp_ms=event.engine_timestamp_ms,
                        engine_mode=event.engine_mode,
                        source_gate_reasons=event.reasons,
                        payload=ModuleFailedPayload(
                            module_id=module.definition.module_id,
                            module_kind=module.definition.module_kind,
                            error_kind="missing_dependency",
                            error_detail="dependency not available",
                        ),
                    )
                    events.append(failed)
                    self._log_event(failed)
                    continue
                dependency_payloads = artifact_store.dependency_payloads(
                    module.definition.dependencies
                )
                state_payload = None
                latest_state = self._state.module_state_store.latest_by_symbol_and_module(
                    symbol=event.symbol, module_id=module.definition.module_id
                )
                if latest_state is not None:
                    state_payload = latest_state.state_payload

                try:
                    result: ModuleResult = module.execute(
                        context=context,
                        dependencies=dependency_payloads,
                        state=state_payload,
                    )
                    self._validate_artifacts(stage, result.artifacts, module.definition.module_id)
                except Exception as exc:  # pragma: no cover - defensive
                    module_failures.append(module.definition.module_id)
                    failed = _analysis_event(
                        event_type="ModuleFailed",
                        symbol=event.symbol,
                        run_id=event.run_id,
                        engine_timestamp_ms=event.engine_timestamp_ms,
                        engine_mode=event.engine_mode,
                        source_gate_reasons=event.reasons,
                        payload=ModuleFailedPayload(
                            module_id=module.definition.module_id,
                            module_kind=module.definition.module_kind,
                            error_kind="exception",
                            error_detail=str(exc),
                        ),
                    )
                    events.append(failed)
                    self._log_event(failed)
                    continue

                ordered_artifacts = sorted(
                    result.artifacts, key=lambda artifact: artifact.artifact_name
                )
                for artifact in ordered_artifacts:
                    artifact_store.add(artifact)
                    emitted = _analysis_event(
                        event_type="ArtifactEmitted",
                        symbol=event.symbol,
                        run_id=event.run_id,
                        engine_timestamp_ms=event.engine_timestamp_ms,
                        engine_mode=event.engine_mode,
                        source_gate_reasons=event.reasons,
                        payload=artifact,
                    )
                    events.append(emitted)
                    self._log_event(emitted)

                if (
                    module.definition.state_schema_id is not None
                    and result.state_payload is not None
                ):
                    state_record = AnalysisModuleStateRecord(
                        symbol=event.symbol,
                        module_id=module.definition.module_id,
                        run_id=event.run_id,
                        engine_timestamp_ms=event.engine_timestamp_ms,
                        state_schema_id=module.definition.state_schema_id,
                        state_schema_version=module.definition.state_schema_version or "",
                        state_payload=result.state_payload,
                    )
                    self._state.module_state_store.append(state_record)

        status: RunStatus = "SUCCESS" if not module_failures else "PARTIAL"
        completed = _analysis_event(
            event_type="AnalysisRunCompleted",
            symbol=event.symbol,
            run_id=event.run_id,
            engine_timestamp_ms=event.engine_timestamp_ms,
            engine_mode=event.engine_mode,
            source_gate_reasons=event.reasons,
            payload=AnalysisRunStatusPayload(
                status=status, module_failures=tuple(sorted(module_failures))
            ),
        )
        events.append(completed)
        self._log_event(completed)
        return events

    @property
    def idempotency_store(self) -> IdempotencyStore:
        return self._state.idempotency

    @property
    def module_state_store(self) -> ModuleStateStore:
        return self._state.module_state_store

    @property
    def halted_symbols(self) -> set[str]:
        return set(self._state.halted_symbols)

    def health_status(self):
        return self._observability.health_status()

    def _build_plans(self) -> dict[str, ExecutionPlan]:
        plans: dict[str, ExecutionPlan] = {}
        default_enabled = list(self._config.enabled_modules)
        if not default_enabled:
            default_enabled = [
                module_id
                for module_id, module in self._registry.modules.items()
                if module.definition.enabled_by_default
            ]
        plans["__default__"] = build_execution_plan(
            self._registry, enabled_module_ids=default_enabled
        )
        if self._config.symbols:
            for symbol_config in self._config.symbols:
                plans[symbol_config.symbol] = build_execution_plan(
                    self._registry, enabled_module_ids=list(symbol_config.enabled_modules)
                )
        return plans

    def _plan_for_symbol(self, symbol: str) -> ExecutionPlan:
        if symbol in self._plan_by_symbol:
            return self._plan_by_symbol[symbol]
        if "__default__" in self._plan_by_symbol:
            return self._plan_by_symbol["__default__"]
        raise ValueError("no execution plan available")

    def _validate_artifacts(
        self,
        stage: str,
        artifacts: Sequence[ArtifactEmittedPayload],
        module_id: str,
    ) -> None:
        expected_kind = _expected_artifact_kind(stage)
        for artifact in artifacts:
            if artifact.artifact_kind not in expected_kind:
                raise ValueError(
                    f"invalid artifact kind for {module_id}: {artifact.artifact_kind} "
                    f"(expected {expected_kind})"
                )

    def _log_event(self, event: AnalysisEngineEvent) -> None:
        self._observability.log_event(event)
        self._observability.record_metrics(event)


def _analysis_event(
    *,
    event_type: str,
    symbol: str,
    run_id: str,
    engine_timestamp_ms: int,
    engine_mode: str | None,
    source_gate_reasons: Sequence[str] | None,
    payload: AnalysisRunStatusPayload | ModuleFailedPayload | ArtifactEmittedPayload | None = None,
) -> AnalysisEngineEvent:
    if event_type not in ANALYSIS_EVENT_TYPES:
        raise ValueError(f"unsupported analysis_engine_event type: {event_type}")
    return AnalysisEngineEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type=event_type,  # type: ignore[arg-type]
        symbol=symbol,
        run_id=run_id,
        engine_timestamp_ms=engine_timestamp_ms,
        payload=payload,
        engine_mode=engine_mode,
        source_gate_reasons=tuple(source_gate_reasons) if source_gate_reasons is not None else None,
    )


def _build_run_context(event: StateGateEvent) -> RunContext:
    regime_output = None
    hysteresis_state = None
    if isinstance(event.payload, GateEvaluatedPayload):
        regime_output = event.payload.regime_output
        hysteresis_state = event.payload.hysteresis_state
    return RunContext(
        symbol=event.symbol,
        run_id=event.run_id,
        engine_timestamp_ms=event.engine_timestamp_ms,
        engine_mode=event.engine_mode,
        gate_status=event.gate_status,
        gate_reasons=event.reasons,
        regime_output=regime_output,
        hysteresis_state=hysteresis_state,
    )


def _expected_artifact_kind(stage: str) -> Sequence[str]:
    if stage == "signal":
        return ("signal",)
    if stage == "detector":
        return ("detection",)
    if stage == "rule":
        return ("evaluation",)
    return ("output",)
