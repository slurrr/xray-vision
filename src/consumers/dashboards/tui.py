from __future__ import annotations

import sys
from collections.abc import Iterable
from io import TextIOBase

from .contracts import (
    BeliefSnapshot,
    DashboardViewModel,
    HysteresisSnapshot,
    SymbolSnapshot,
)
from .observability import NullLogger, NullMetrics, Observability
from .renderer import DashboardRenderer, validate_renderer_input


class TuiRenderer(DashboardRenderer):
    """Minimal TUI renderer that consumes only DVM snapshots.

    Tolerates absent or future optional fields.
    """

    def __init__(
        self, *, writer: TextIOBase | None = None, observability: Observability | None = None
    ) -> None:
        self._writer = writer or sys.stdout
        self._started = False
        self._observability = observability or Observability(
            logger=NullLogger(), metrics=NullMetrics()
        )

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def render(self, snapshot: DashboardViewModel) -> None:
        try:
            validated = validate_renderer_input(snapshot)
        except Exception as exc:
            self._observability.log_renderer_failure(
                error_kind="invalid_snapshot", error_detail=str(exc)
            )
            return

        try:
            lines = list(_render_header(validated))
            lines.extend(_render_system(validated))
            lines.extend(_render_telemetry(validated))
            for symbol in validated.symbols:
                lines.extend(_render_symbol(symbol))
            output = "\n".join(lines) + "\n"
            self._writer.write(output)
            if hasattr(self._writer, "flush"):
                try:
                    self._writer.flush()  # type: ignore[call-arg]
                except Exception:
                    pass
        except Exception as exc:  # pragma: no cover - defensive guard
            self._observability.log_renderer_failure(
                error_kind="render_failure", error_detail=str(exc)
            )
            return

        self._observability.record_renderer_frame()


def _render_header(snapshot: DashboardViewModel) -> Iterable[str]:
    yield f"DVM {snapshot.dvm_schema} v{snapshot.dvm_schema_version} as_of={snapshot.as_of_ts_ms}"
    yield (
        f"source_run_id={snapshot.source_run_id} "
        f"source_engine_ts_ms={snapshot.source_engine_timestamp_ms}"
    )


def _render_system(snapshot: DashboardViewModel) -> Iterable[str]:
    yield f"system_status={snapshot.system.status}"
    for component in snapshot.system.components:
        detail_suffix = f" ({'; '.join(component.details)})" if component.details else ""
        yield f" component={component.component_id} status={component.status}{detail_suffix}"


def _render_telemetry(snapshot: DashboardViewModel) -> Iterable[str]:
    staleness = snapshot.telemetry.staleness
    reasons = ", ".join(staleness.stale_reasons)
    yield f"stale={staleness.is_stale} reasons={reasons}"


def _render_symbol(symbol: SymbolSnapshot) -> Iterable[str]:
    yield (
        f"[{symbol.symbol}] run_id={symbol.last_run_id} "
        f"engine_ts_ms={symbol.last_engine_timestamp_ms}"
    )
    reasons = ", ".join(symbol.gate.reasons)
    yield f" gate={symbol.gate.status} reasons={reasons}"

    if symbol.regime_effective is not None:
        eff = symbol.regime_effective
        yield f" regime_effective={eff.regime_name} ({eff.source}) confidence={eff.confidence}"

    if symbol.regime_truth is not None:
        truth = symbol.regime_truth
        yield f" regime_truth={truth.regime_name} confidence={truth.confidence}"
        if truth.drivers:
            yield f"  drivers={', '.join(truth.drivers)}"
        if truth.invalidations:
            yield f"  invalidations={', '.join(truth.invalidations)}"
        if truth.permissions:
            yield f"  permissions={', '.join(truth.permissions)}"

    if symbol.hysteresis is not None:
        yield from _render_hysteresis(symbol.hysteresis)
    if symbol.belief is not None:
        yield from _render_belief(symbol.belief)

    if symbol.analysis is not None:
        analysis = symbol.analysis
        yield f" analysis_status={analysis.status}"
        if analysis.highlights:
            yield f"  highlights={', '.join(analysis.highlights)}"
        if analysis.artifacts:
            for artifact in analysis.artifacts:
                yield (
                    f"  artifact={artifact.module_id}:{artifact.artifact_name} "
                    f"kind={artifact.artifact_kind} summary={artifact.summary}"
                )

    if symbol.metrics is not None:
        metrics_parts = []
        for field in (
            "atr_pct",
            "atr_rank",
            "range_24h_pct",
            "range_session_pct",
            "volume_24h",
            "volume_rank",
            "relative_volume",
            "relative_strength",
        ):
            value = getattr(symbol.metrics, field)
            if value is not None:
                metrics_parts.append(f"{field}={value}")
        if metrics_parts:
            yield f" metrics: {'; '.join(metrics_parts)}"


def _render_hysteresis(hysteresis: HysteresisSnapshot) -> Iterable[str]:
    yield f" hysteresis_confidence={hysteresis.effective_confidence}"
    if hysteresis.summary is not None:
        summary = hysteresis.summary
        yield (
            f"  phase={summary.phase} anchor={summary.anchor_regime} "
            f"candidate={summary.candidate_regime}"
        )
        yield (
            f"  progress={summary.progress.current}/{summary.progress.required} "
            f"trend={summary.confidence_trend}"
        )
        if summary.notes:
            yield f"  notes={', '.join(summary.notes)}"


def _render_belief(belief: BeliefSnapshot) -> Iterable[str]:
    yield f" belief_anchor={belief.anchor_regime}"
    yield f" belief_trend={belief.trend.status} delta={belief.trend.anchor_mass_delta}"
    if belief.distribution:
        parts = [
            f"{entry.regime_name}={entry.mass:.4f}" for entry in belief.distribution
        ]
        yield f" belief_distribution={'; '.join(parts)}"
