import unittest

from consumers.analysis_engine import (
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleDependency,
    ModuleRegistry,
    ModuleResult,
    OutputModule,
    RuleModule,
    SignalModule,
    build_module_definition,
)
from consumers.analysis_engine.contracts import RunContext
from consumers.analysis_engine.planning import artifact_ordering, build_execution_plan


def _definition(module_id: str, module_kind: str, dependencies: list[ModuleDependency]):
    return build_module_definition(
        module_id=module_id,
        module_kind=module_kind,
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


class _Signal(SignalModule):
    def __init__(self, module_id: str, dependencies: list[ModuleDependency]):
        super().__init__(definition=_definition(module_id, "signal", dependencies))  # type: ignore[arg-type]

    def execute(self, *, context: RunContext, dependencies, state=None):
        return ModuleResult(
            artifacts=[
                ArtifactEmittedPayload(
                    artifact_kind="signal",
                    module_id=self.definition.module_id,
                    artifact_name="value",
                    artifact_schema=f"schema.{self.definition.module_id}.value",
                    artifact_schema_version="1",
                    payload={"symbol": context.symbol},
                )
            ]
        )


class _Rule(RuleModule):
    def __init__(self, module_id: str, dependencies: list[ModuleDependency]):
        super().__init__(definition=_definition(module_id, "rule", dependencies))  # type: ignore[arg-type]

    def execute(self, *, context: RunContext, dependencies, state=None):
        return ModuleResult(
            artifacts=[
                ArtifactEmittedPayload(
                    artifact_kind="evaluation",
                    module_id=self.definition.module_id,
                    artifact_name="value",
                    artifact_schema=f"schema.{self.definition.module_id}.value",
                    artifact_schema_version="1",
                    payload={"symbol": context.symbol},
                )
            ]
        )


class _Output(OutputModule):
    def __init__(self, module_id: str, dependencies: list[ModuleDependency]):
        super().__init__(definition=_definition(module_id, "output", dependencies))  # type: ignore[arg-type]

    def execute(self, *, context: RunContext, dependencies, state=None):
        return ModuleResult(
            artifacts=[
                ArtifactEmittedPayload(
                    artifact_kind="output",
                    module_id=self.definition.module_id,
                    artifact_name="value",
                    artifact_schema=f"schema.{self.definition.module_id}.value",
                    artifact_schema_version="1",
                    payload={"symbol": context.symbol},
                )
            ]
        )


class TestExecutionPlan(unittest.TestCase):
    def test_deterministic_plan_ordering(self) -> None:
        signal_a = _Signal("signal.a", dependencies=[])
        signal_b = _Signal("signal.b", dependencies=[ModuleDependency(module_id="signal.a", artifact_name="value")])
        rule_r = _Rule("rule.r", dependencies=[ModuleDependency(module_id="signal.b", artifact_name="value")])
        output_o = _Output("output.o", dependencies=[ModuleDependency(module_id="rule.r", artifact_name="value")])

        registry = ModuleRegistry([output_o, rule_r, signal_b, signal_a])
        plan = build_execution_plan(registry, enabled_module_ids=["signal.a", "signal.b", "rule.r", "output.o"])
        self.assertEqual(
            [step.module_id for step in plan.steps_by_stage["signal"]],
            ["signal.a", "signal.b"],
        )
        self.assertEqual(
            [step.module_id for step in plan.steps_by_stage["rule"]],
            ["rule.r"],
        )
        self.assertEqual(
            [step.module_id for step in plan.steps_by_stage["output"]],
            ["output.o"],
        )

    def test_stage_dependency_violation_fails(self) -> None:
        signal_a = _Signal("signal.a", dependencies=[])
        rule_r = _Rule("rule.r", dependencies=[])
        output_o = _Output("output.o", dependencies=[ModuleDependency(module_id="rule.r", artifact_name="value")])
        bad_rule = _Rule("rule.bad", dependencies=[ModuleDependency(module_id="output.o", artifact_name="value")])

        registry = ModuleRegistry([signal_a, rule_r, output_o, bad_rule])
        with self.assertRaises(ValueError):
            build_execution_plan(registry, enabled_module_ids=["signal.a", "rule.r", "output.o", "rule.bad"])

    def test_artifact_ordering_is_lexicographic(self) -> None:
        schemas = [
            ArtifactSchema(artifact_name="b", artifact_schema="schema.b", artifact_schema_version="1"),
            ArtifactSchema(artifact_name="a", artifact_schema="schema.a", artifact_schema_version="1"),
        ]
        ordered = artifact_ordering(schemas)
        self.assertEqual([schema.artifact_name for schema in ordered], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
