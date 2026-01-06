import unittest

from consumers.analysis_engine import (
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleDependency,
    ModuleRegistry,
    ModuleResult,
    SignalModule,
    build_module_definition,
)
from consumers.analysis_engine.contracts import RunContext


class _StubSignal(SignalModule):
    def __init__(self, module_id: str, dependencies: list[ModuleDependency]) -> None:
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
            dependencies=dependencies,
            config_schema_id=f"config.{module_id}",
            config_schema_version="1",
        )
        super().__init__(definition=definition)

    def execute(self, *, context: RunContext, dependencies, state=None):
        return ModuleResult(
            artifacts=[
                ArtifactEmittedPayload(
                    artifact_kind="signal",
                    module_id=self.definition.module_id,
                    artifact_name="value",
                    artifact_schema=f"schema.{self.definition.module_id}.value",
                    artifact_schema_version="1",
                    payload={"x": 1, "symbol": context.symbol},
                )
            ]
        )


class TestModuleRegistry(unittest.TestCase):
    def test_registry_is_deterministic_and_unique(self) -> None:
        a = _StubSignal("a", dependencies=[])
        b = _StubSignal("b", dependencies=[])
        registry = ModuleRegistry([b, a])
        definitions = registry.definitions()
        self.assertEqual([d.module_id for d in definitions], ["a", "b"])

    def test_missing_dependency_fails_validation(self) -> None:
        dependent = _StubSignal(
            "dep",
            dependencies=[ModuleDependency(module_id="missing", artifact_name="value")],
        )
        registry = ModuleRegistry([dependent])
        with self.assertRaises(ValueError):
            registry.validate_dependencies(["dep"])

    def test_cycle_detection(self) -> None:
        a = _StubSignal("a", dependencies=[ModuleDependency(module_id="b", artifact_name="value")])
        b = _StubSignal("b", dependencies=[ModuleDependency(module_id="a", artifact_name="value")])
        registry = ModuleRegistry([a, b])
        with self.assertRaises(ValueError):
            registry.validate_dependencies(["a", "b"])


if __name__ == "__main__":
    unittest.main()
