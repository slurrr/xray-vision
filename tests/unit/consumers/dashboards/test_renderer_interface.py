import inspect
import unittest

from consumers.dashboards import (
    DashboardBuilder,
    DashboardRenderer,
    DashboardViewModel,
    validate_renderer_input,
)


class _DummyRenderer(DashboardRenderer):
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.rendered: DashboardViewModel | None = None

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def render(self, snapshot: DashboardViewModel) -> None:
        validate_renderer_input(snapshot)
        self.rendered = snapshot


class TestRendererInterface(unittest.TestCase):
    def test_renderer_accepts_only_dvm_snapshots(self) -> None:
        builder = DashboardBuilder(time_fn=lambda: 1)
        snapshot = builder.build_snapshot(as_of_ts_ms=1)
        renderer = _DummyRenderer()
        renderer.start()
        renderer.render(snapshot)
        self.assertIs(renderer.rendered, snapshot)
        renderer.stop()
        with self.assertRaises(TypeError):
            validate_renderer_input(object())

    def test_renderer_signature_is_dvm_only(self) -> None:
        parameters = inspect.signature(_DummyRenderer.render).parameters
        annotation = parameters["snapshot"].annotation
        self.assertIs(annotation, DashboardViewModel)
        self.assertTrue(issubclass(_DummyRenderer, DashboardRenderer))


if __name__ == "__main__":
    unittest.main()
