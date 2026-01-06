from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .contracts import ArtifactEmittedPayload, ModuleDefinition, ModuleKind, RunContext


class AnalysisModule(Protocol):
    @property
    @abstractmethod
    def definition(self) -> ModuleDefinition: ...  # pragma: no cover - interface

    @abstractmethod
    def execute(
        self,
        *,
        context: RunContext,
        dependencies: Mapping[str, ArtifactEmittedPayload],
        state: object | None = None,
    ) -> "ModuleResult": ...  # pragma: no cover - interface


@dataclass(frozen=True)
class ModuleResult:
    artifacts: Sequence[ArtifactEmittedPayload]
    state_payload: object | None = None


class BaseModule(ABC):
    module_kind: ModuleKind

    def __init__(self, definition: ModuleDefinition) -> None:
        self._definition = definition
        if self._definition.module_kind != self.module_kind:
            raise ValueError("module_kind does not match definition")

    @property
    def definition(self) -> ModuleDefinition:
        return self._definition

    @abstractmethod
    def execute(
        self,
        *,
        context: RunContext,
        dependencies: Mapping[str, ArtifactEmittedPayload],
        state: object | None = None,
    ) -> ModuleResult:
        raise NotImplementedError


class SignalModule(BaseModule):
    module_kind: ModuleKind = "signal"


class DetectorModule(BaseModule):
    module_kind: ModuleKind = "detector"


class RuleModule(BaseModule):
    module_kind: ModuleKind = "rule"


class OutputModule(BaseModule):
    module_kind: ModuleKind = "output"
