import unittest

from consumers.analysis_engine import (
    AnalysisEngineConfig,
    ModuleConfig,
    ModuleRegistry,
    ModuleResult,
    SignalModule,
    SymbolConfig,
    build_module_definition,
    validate_config,
)
from consumers.analysis_engine.contracts import ArtifactSchema


class _StubSignal(SignalModule):
    def __init__(self, module_id: str):
        definition = build_module_definition(
            module_id=module_id,
            module_kind="signal",
            module_version="1",
            artifact_schemas=[
                ArtifactSchema(
                    artifact_name="value",
                    artifact_schema=f"schema.{module_id}.value",
                    artifact_schema_version="1",
                )
            ],
            dependencies=[],
            config_schema_id=f"config.{module_id}",
            config_schema_version="1",
        )
        super().__init__(definition=definition)

    def execute(self, *, context, dependencies, state=None):  # pragma: no cover - not used in config tests
        return ModuleResult(artifacts=[])


class TestConfigValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ModuleRegistry([_StubSignal("signal.a")])

    def test_valid_config_passes(self) -> None:
        config = AnalysisEngineConfig(
            enabled_modules=["signal.a"],
            module_configs=[ModuleConfig(module_id="signal.a", config={"threshold": 1})],
            symbols=[SymbolConfig(symbol="TEST", enabled_modules=["signal.a"])],
        )
        validate_config(config, self.registry)

    def test_unknown_enabled_module_fails(self) -> None:
        config = AnalysisEngineConfig(enabled_modules=["missing"], module_configs=[])
        with self.assertRaises(ValueError):
            validate_config(config, self.registry)

    def test_duplicate_module_config_fails(self) -> None:
        config = AnalysisEngineConfig(
            enabled_modules=["signal.a"],
            module_configs=[
                ModuleConfig(module_id="signal.a", config={"a": 1}),
                ModuleConfig(module_id="signal.a", config={"a": 2}),
            ],
        )
        with self.assertRaises(ValueError):
            validate_config(config, self.registry)

    def test_symbol_config_unknown_module_fails(self) -> None:
        config = AnalysisEngineConfig(
            enabled_modules=["signal.a"],
            module_configs=[],
            symbols=[SymbolConfig(symbol="TEST", enabled_modules=["missing"])],
        )
        with self.assertRaises(ValueError):
            validate_config(config, self.registry)

    def test_non_mapping_module_config_fails(self) -> None:
        config = AnalysisEngineConfig(
            enabled_modules=["signal.a"],
            module_configs=[ModuleConfig(module_id="signal.a", config=123)],  # type: ignore[arg-type]
        )
        with self.assertRaises(ValueError):
            validate_config(config, self.registry)


if __name__ == "__main__":
    unittest.main()
