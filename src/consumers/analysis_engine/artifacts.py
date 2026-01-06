from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from .contracts import ArtifactEmittedPayload, ModuleDependency


Key = Tuple[str, str]


@dataclass
class ArtifactStore:
    artifacts: Dict[Key, ArtifactEmittedPayload] = field(default_factory=dict)

    def add(self, artifact: ArtifactEmittedPayload) -> None:
        key = (artifact.module_id, artifact.artifact_name)
        self.artifacts[key] = artifact

    def get(self, module_id: str, artifact_name: str) -> ArtifactEmittedPayload | None:
        return self.artifacts.get((module_id, artifact_name))

    def dependencies_available(self, dependencies: Iterable[ModuleDependency]) -> bool:
        return all(self.get(dep.module_id, dep.artifact_name) is not None for dep in dependencies)

    def dependency_payloads(self, dependencies: Sequence[ModuleDependency]) -> Dict[str, ArtifactEmittedPayload]:
        available: Dict[str, ArtifactEmittedPayload] = {}
        for dependency in dependencies:
            artifact = self.get(dependency.module_id, dependency.artifact_name)
            if artifact is not None:
                available[f"{dependency.module_id}:{dependency.artifact_name}"] = artifact
        return available
