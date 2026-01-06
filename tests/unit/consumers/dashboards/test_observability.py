import unittest
from collections.abc import Mapping
from io import TextIOBase

from consumers.dashboards import DashboardBuilder, Observability, TuiRenderer
from consumers.dashboards.contracts import DashboardViewModel
from orchestrator.contracts import OrchestratorEvent


class _RecordingLogger:
    def __init__(self) -> None:
        self.entries: list[tuple[int, str, Mapping[str, object]]] = []

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.entries.append((level, message, fields))


class _RecordingMetrics:
    def __init__(self) -> None:
        self.increments: list[tuple[str, int, Mapping[str, str] | None]] = []
        self.observations: list[tuple[str, float, Mapping[str, str] | None]] = []
        self.gauges: list[tuple[str, float, Mapping[str, str] | None]] = []

    def increment(self, name: str, value: int = 1, tags: Mapping[str, str] | None = None) -> None:
        self.increments.append((name, value, tags))

    def observe(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
        self.observations.append((name, value, tags))

    def gauge(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
        self.gauges.append((name, value, tags))


class _MonotonicTime:
    def __init__(self, start: int = 0) -> None:
        self._now = start

    def __call__(self) -> int:
        self._now += 1
        return self._now


class _ExplodingWriter(TextIOBase):
    def write(self, data: str) -> int:  # pragma: no cover - exercised in tests
        raise RuntimeError("writer unavailable")


class TestObservability(unittest.TestCase):
    def test_snapshot_logging_and_metrics(self) -> None:
        logger = _RecordingLogger()
        metrics = _RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        builder = DashboardBuilder(time_fn=_MonotonicTime(start=100), observability=obs)

        snapshot = builder.build_snapshot()
        self.assertIsInstance(snapshot, DashboardViewModel)
        self.assertTrue(
            any(entry[1] == "dashboards.snapshot_produced" for entry in logger.entries)
        )
        self.assertTrue(
            any(metric[0] == "dashboards.snapshots.produced" for metric in metrics.increments)
        )
        self.assertTrue(
            any(metric[0] == "dashboards.snapshot_latency_ms" for metric in metrics.observations)
        )

    def test_ingest_failure_sets_stale_flag_and_logs(self) -> None:
        logger = _RecordingLogger()
        metrics = _RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        builder = DashboardBuilder(time_fn=_MonotonicTime(start=10), observability=obs)

        bad_event = OrchestratorEvent(
            schema="bad",
            schema_version="0",
            event_type="EngineRunCompleted",  # type: ignore[arg-type]
            run_id="run-x",
            symbol="TEST",
            engine_timestamp_ms=1,
            cut_start_ingest_seq=0,
            cut_end_ingest_seq=0,
            cut_kind="timer",
        )
        builder.ingest_orchestrator_event(bad_event)
        snapshot = builder.build_snapshot()
        self.assertIn("ingest_failure", snapshot.telemetry.staleness.stale_reasons)
        self.assertTrue(any(entry[1] == "dashboards.ingest_failure" for entry in logger.entries))
        failure_metrics = [
            inc for inc in metrics.increments if inc[0] == "dashboards.failures"
        ]
        self.assertTrue(
            any("builder" == (tags or {}).get("component") for _, _, tags in failure_metrics)
        )

    def test_renderer_failure_isolated_and_logged(self) -> None:
        logger = _RecordingLogger()
        metrics = _RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        builder = DashboardBuilder(time_fn=_MonotonicTime(start=50))
        snapshot = builder.build_snapshot()
        renderer = TuiRenderer(writer=_ExplodingWriter(), observability=obs)

        renderer.render(snapshot)

        self.assertTrue(any(entry[1] == "dashboards.renderer_failure" for entry in logger.entries))
        failure_metrics = [
            inc for inc in metrics.increments if inc[0] == "dashboards.failures"
        ]
        self.assertTrue(
            any("renderer" == (tags or {}).get("component") for _, _, tags in failure_metrics)
        )


if __name__ == "__main__":
    unittest.main()
