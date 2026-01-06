from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set

from .contracts import ArtifactSchema, ModuleDefinition, ModuleDependency
from .modules import AnalysisModule


@dataclass
class ModuleRegistry:
    modules: Dict[str, AnalysisModule]

    def __init__(self, modules: Iterable[AnalysisModule]) -> None:
        self.modules = {}
        for module in modules:
            definition = module.definition
            if definition.module_id in self.modules:
                raise ValueError(f"duplicate module_id: {definition.module_id}")
            self.modules[definition.module_id] = module
        self.modules = {module_id: self.modules[module_id] for module_id in sorted(self.modules)}

    def definitions(self) -> Sequence[ModuleDefinition]:
        return tuple(module.definition for module in self.modules.values())

    def enabled_definitions(self, enabled_module_ids: Sequence[str] | None = None) -> Sequence[ModuleDefinition]:
        if enabled_module_ids is None:
            enabled = [module_id for module_id, module in self.modules.items() if module.definition.enabled_by_default]
        else:
            enabled = list(enabled_module_ids)
        return tuple(self.modules[module_id].definition for module_id in sorted(enabled))

    def validate_dependencies(self, enabled_module_ids: Sequence[str]) -> None:
        enabled_set = set(enabled_module_ids)
        self._validate_missing_dependencies(enabled_set)
        self._validate_cycles(enabled_set)

    def _validate_missing_dependencies(self, enabled_set: Set[str]) -> None:
        for module_id in enabled_set:
            module = self.modules.get(module_id)
            if module is None:
                raise ValueError(f"unknown module_id: {module_id}")
            for dependency in module.definition.dependencies:
                if dependency.module_id not in enabled_set:
                    raise ValueError(
                        f"missing dependency for {module_id}: {dependency.module_id}.{dependency.artifact_name}"
                    )

    def _validate_cycles(self, enabled_set: Set[str]) -> None:
        visiting: Set[str] = set()
        visited: Set[str] = set()

        def dfs(current: str) -> None:
            if current in visited:
                return
            if current in visiting:
                raise ValueError(f"dependency cycle detected at {current}")
            visiting.add(current)
            module = self.modules[current]
            for dep in module.definition.dependencies:
                if dep.module_id in enabled_set:
                    dfs(dep.module_id)
            visiting.remove(current)
            visited.add(current)

        for module_id in sorted(enabled_set):
            dfs(module_id)


def build_module_definition(
    *,
    module_id: str,
    module_kind: str,
    module_version: str,
    artifact_schemas: Sequence[ArtifactSchema],
    dependencies: Sequence[ModuleDependency],
    config_schema_id: str,
    config_schema_version: str,
    enabled_by_default: bool = False,
    state_schema_id: str | None = None,
    state_schema_version: str | None = None,
) -> ModuleDefinition:
    return ModuleDefinition(
        module_id=module_id,
        module_kind=module_kind,  # type: ignore[arg-type]
        module_version=module_version,
        dependencies=dependencies,  # type: ignore[arg-type]
        artifact_schemas=artifact_schemas,
        config_schema_id=config_schema_id,
        config_schema_version=config_schema_version,
        enabled_by_default=enabled_by_default,
        state_schema_id=state_schema_id,
        state_schema_version=state_schema_version,
    )
