from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from .contracts import ArtifactSchema, ModuleDefinition, ModuleKind
from .modules import AnalysisModule
from .registry import ModuleRegistry

STAGE_ORDER: Sequence[ModuleKind] = ("signal", "detector", "rule", "output")


@dataclass(frozen=True)
class ExecutionStep:
    module_id: str
    module_kind: ModuleKind
    artifact_schemas: Sequence[ArtifactSchema]
    dependencies: Sequence[str]


@dataclass(frozen=True)
class ExecutionPlan:
    steps_by_stage: Dict[ModuleKind, Sequence[ExecutionStep]]


def build_execution_plan(registry: ModuleRegistry, enabled_module_ids: Sequence[str]) -> ExecutionPlan:
    registry.validate_dependencies(enabled_module_ids)
    modules: Dict[str, AnalysisModule] = {module_id: registry.modules[module_id] for module_id in enabled_module_ids}
    _validate_stage_dependencies(modules)

    steps_by_stage: Dict[ModuleKind, Sequence[ExecutionStep]] = {}
    for stage in STAGE_ORDER:
        stage_modules = [
            module
            for module in modules.values()
            if module.definition.module_kind == stage
        ]
        ordered_definitions = _order_stage(stage_modules)
        steps_by_stage[stage] = tuple(
            ExecutionStep(
                module_id=definition.module_id,
                module_kind=definition.module_kind,
                artifact_schemas=definition.artifact_schemas,
                dependencies=tuple(dep.module_id for dep in definition.dependencies),
            )
            for definition in ordered_definitions
        )
    return ExecutionPlan(steps_by_stage=steps_by_stage)


def artifact_ordering(artifact_schemas: Sequence[ArtifactSchema]) -> Sequence[ArtifactSchema]:
    return tuple(sorted(artifact_schemas, key=lambda schema: schema.artifact_name))


def _validate_stage_dependencies(modules: Dict[str, AnalysisModule]) -> None:
    kind_precedence = {kind: index for index, kind in enumerate(STAGE_ORDER)}
    for module in modules.values():
        module_stage = kind_precedence[module.definition.module_kind]
        for dependency in module.definition.dependencies:
            dep_module = modules.get(dependency.module_id)
            if dep_module is None:
                continue
            dep_stage = kind_precedence[dep_module.definition.module_kind]
            if dep_stage > module_stage:
                raise ValueError(
                    f"invalid dependency ordering: {module.definition.module_id} depends on later stage "
                    f"{dep_module.definition.module_id}"
                )


def _order_stage(stage_modules: Sequence[AnalysisModule]) -> List[ModuleDefinition]:
    definitions = {module.definition.module_id: module.definition for module in stage_modules}
    dependencies: Dict[str, set[str]] = {
        module_id: set(dep.module_id for dep in definition.dependencies if dep.module_id in definitions)
        for module_id, definition in definitions.items()
    }
    indegree: Dict[str, int] = {module_id: len(deps) for module_id, deps in dependencies.items()}
    dependents: Dict[str, set[str]] = {module_id: set() for module_id in definitions}
    for module_id, deps in dependencies.items():
        for dep in deps:
            dependents[dep].add(module_id)

    queue = sorted([module_id for module_id, degree in indegree.items() if degree == 0])
    ordered: List[ModuleDefinition] = []
    while queue:
        current = queue.pop(0)
        ordered.append(definitions[current])
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
        queue.sort()

    if len(ordered) != len(definitions):
        raise ValueError("cycle detected within stage")
    return ordered
